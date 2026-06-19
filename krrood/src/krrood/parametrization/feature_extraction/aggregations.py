from __future__ import annotations

import inspect
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property

from typing_extensions import Any, Optional, Type

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import MappedVariable
from krrood.entity_query_language.factories import variable


class AggregationRegistry:
    """
    Class-level registry mapping ``(owner_class, attribute_name)`` pairs to
    their ``AggregationStatistic`` subclass.

    The registry is write-protected from outside this module: all entries are
    created exclusively through the ``@aggregation_for`` decorator.
    """

    _registry: dict[tuple[Type, str], Type[AggregationStatistic]] = {}
    """
    The registry mapping ``(owner_class, attribute_name)`` pairs to their
    ``AggregationStatistic`` subclass.
    """

    @classmethod
    def _register(
        cls,
        owner: Type,
        attribute_name: str,
        aggregation_cls: Type[AggregationStatistic],
    ) -> None:
        """
        Registers an aggregation class for the given owner field.
        :param owner: The domain class that owns the exchangeable-part field.
        :param attribute_name: The field name on ``owner``.
        :param aggregation_cls: The ``AggregationStatistic`` subclass to register for the pair.
        """
        cls._registry[(owner, attribute_name)] = aggregation_cls

    @classmethod
    def get(
        cls, owner: Type, attribute_name: str
    ) -> Optional[Type[AggregationStatistic]]:
        """
        Returns the aggregation class registered for the given owner field.

        :param owner: The domain class that owns the exchangeable-part field.
        :param attribute_name: The field name on ``owner``.
        :return: The registered ``AggregationStatistic`` subclass.
        :raises KeyError: If no aggregation class has been registered for the pair.
        """
        key = (owner, attribute_name)
        if key not in cls._registry:
            return None
        return cls._registry[key]

    @classmethod
    def get_fields_for(cls, owner: Type) -> list[str]:
        """
        Returns the names of all fields on ``owner`` that have a registered aggregation class.

        :param owner: The domain class to query.
        :return: Field names registered for ``owner``, in insertion order.
        """
        return [attr for (owner_cls, attr) in cls._registry if owner_cls is owner]


def aggregation_for(*owner_attribute_pairs: tuple[Type, str]):
    """
    Class decorator that registers an ``AggregationStatistic`` subclass in the
    ``AggregationRegistry`` for one or more ``(owner, attribute_name)`` pairs.

    :param owner_attribute_pairs: One or more ``(owner_class, attribute_name)`` tuples.
    """

    def wrapper(
        aggregation_cls: Type[AggregationStatistic],
    ) -> Type[AggregationStatistic]:
        for owner, attribute_name in owner_attribute_pairs:
            AggregationRegistry._register(owner, attribute_name, aggregation_cls)
        return aggregation_cls

    return wrapper


@dataclass
class AggregationStatistic(ABC):
    """
    Base class for aggregation statistics over a list of exchangeable domain objects.

    Subclasses declare one field holding the list of items to aggregate and
    expose one public method per statistic. Each method receives ``self`` and
    returns a scalar value.
    """

    objects_to_aggregate_on: list[Any]
    """
    The items over which statistics are to be computed.
    """

    def __post_init__(self):
        if not self.objects_to_aggregate_on:
            raise ValueError("Aggregation object must not be empty")

    @abstractmethod
    @cached_property
    def _eql_variable(self) -> SymbolicExpression:
        """
        The symbolic variable that is used to compute aggregations on.
        """

    @property
    def symbolic_aggregation_features(self) -> list[MappedVariable]:
        """
        Symbolic variables corresponding to each aggregation statistic method.

        Dict-returning methods are expanded into one variable per key.
        :return: One ``MappedVariable`` per scalar statistic, typed as ``float``.
        """
        symbolic_aggregations = []
        aggregation_variable = variable(type(self), [])
        for function in self.aggregation_features:
            function_variable = getattr(aggregation_variable, function.__name__)()
            symbolic_aggregations.append(function_variable)
        return symbolic_aggregations

    @property
    def aggregation_features(self) -> list[Any]:
        """
        All public, non-base statistic methods defined on the concrete subclass.

        Dict-returning methods are flattened into per-key entries and recorded
        in ``_internal_aggregation_mapping`` so symbolic lookup can recover
        the original method name.
        :return: A list of bound or flattened statistic callables.
        """
        cls_functions = inspect.getmembers(self.__class__, predicate=inspect.isfunction)
        aggregations = []
        for name, function in cls_functions:
            if (
                name.startswith("__")
                or name.startswith("_")
                or function is AggregationStatistic.apply_mapping
            ):
                continue
            else:
                aggregations.append(function)

        if not aggregations:
            warnings.warn(
                f"No aggregation features found for exchangeable part {self.objects_to_aggregate_on} of type {type(self.objects_to_aggregate_on)}"
            )
        return aggregations

    def apply_mapping(self) -> list:
        """
        Evaluates every symbolic aggregation feature against this instance.

        :return: One concrete value per entry in ``symbolic_aggregation_features``.
        """
        return [
            feature.apply_mapping_on_external_root(self)
            for feature in self.symbolic_aggregation_features
        ]


@dataclass
class HasExchangeablePartAggregations(ABC):
    """
    Mixin for domain classes whose exchangeable-part fields have aggregation
    classes registered via ``@aggregation_for``.

    Subclasses must be dataclasses. Any field whose ``(owner, name)`` pair
    appears in the ``AggregationRegistry`` is validated to be a list at
    instance creation time.
    """

    def __post_init__(self) -> None:
        """
        Validates that every registered exchangeable-part field holds a list.

        :raises TypeError: If a registered field is not a list at instance creation.
        """
        for field_name in AggregationRegistry.get_fields_for(type(self)):
            value = getattr(self, field_name)
            if not isinstance(value, list):
                raise TypeError(
                    f"{self.__class__.__name__}.{field_name} must be a list, "
                    f"got {type(value).__name__}."
                )

    def get_aggregation_class_by_part_name(
        self, part_name: str
    ) -> Optional[AggregationStatistic]:
        """
        Instantiates and returns the aggregation class registered for the named field.

        :param part_name: The name of the exchangeable-part field.
        :return: An ``AggregationStatistic`` initialised with the field's current value.
        :raises KeyError: If no aggregation class is registered for ``part_name``.
        """
        aggregation_cls = AggregationRegistry.get(type(self), part_name)
        if aggregation_cls is None:
            return None
        return aggregation_cls(getattr(self, part_name))
