from __future__ import annotations

import enum
import itertools
from collections import defaultdict, deque
from dataclasses import dataclass, field

import pandas as pd
import sqlalchemy
from sqlalchemy.orm import MANYTOONE, ONETOMANY
from typing_extensions import TYPE_CHECKING, Any, Optional, Type
from krrood.entity_query_language.core.mapped_variable import MappedVariable
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import variable
from krrood.ormatic.data_access_objects.from_dao import FromDataAccessObjectState
from krrood.ormatic.utils import get_python_type_from_sqlalchemy_column, is_data_column
from krrood.parametrization.feature_extraction.aggregations import (
    HasExchangeablePartAggregations,
)
from random_events.variable import compatible_types

if TYPE_CHECKING:
    from krrood.ormatic.data_access_objects.dao import DataAccessObject


@dataclass
class FeatureExtractor:
    """
    Extracts symbolic features from DAO instances, including scalar attributes,
    unique-part sub-trees, and aggregation statistics over exchangeable parts.

    Prefer ``FeatureExtractor.from_instances`` for construction; the direct
    constructor is for cases where the feature list is already known.
    """

    features: list[MappedVariable]
    """
    Symbolic variables representing every extractable feature, in traversal order.
    """

    exchangeable_features: dict[str, list[MappedVariable]] = field(
        default_factory=lambda: defaultdict(list), init=False
    )
    """
    Mapping from each exchangeable-part field name to its discovered aggregation variables.
    """

    def __post_init__(self):
        if not self.features:
            raise ValueError(
                "No features provided. If list of instances available, use `FeatureExtractor.from_instances` for instantiation."
            )

    @classmethod
    def from_instances(
        cls, instances: list[DataAccessObject]
    ) -> Optional[FeatureExtractor]:
        """
        Create a new feature extractor from the given instances.

        Returns ``None`` when the root domain class has exchangeable parts but does
        not inherit from :class:`HasExchangeablePartAggregations`.

        :param instances: The instances to create the feature extractor from.
        :return: A new feature extractor, or ``None`` if the class is not compatible.
        """
        if not instances:
            raise ValueError("No instances provided")

        dao_state = FromDataAccessObjectState()
        first_instance = instances[0]
        domain_object = first_instance.from_dao(dao_state)
        composition = EntityCompositionDescriptor(type(first_instance))

        if composition.exchangeable_parts and not isinstance(
            domain_object, HasExchangeablePartAggregations
        ):
            return None

        root = variable(type(domain_object), [])
        extractor = cls.__new__(cls)
        extractor.exchangeable_features = defaultdict(list)
        extractor.features = extractor._extract_features(first_instance, root)
        return extractor

    def _extract_features(
        self, example_instance: DataAccessObject, symbolic_root: Variable
    ) -> list[MappedVariable]:
        """
        Traverses the DAO object graph breadth-first and collects all features.

        :param example_instance: A representative DAO instance that defines the schema.
        :param symbolic_root: The root symbolic variable for the traversal.
        :return: All discovered feature variables in traversal order.
        """
        result = []
        seen = set()
        exchangeable_features = defaultdict(list)
        queue = deque()
        queue.append((example_instance, symbolic_root))

        while queue:
            current_instance, current_symbolic = queue.popleft()

            if id(current_instance) in seen:
                continue
            seen.add(id(current_instance))

            instance_composition = EntityCompositionDescriptor(type(current_instance))

            result.extend(
                self._process_attributes(
                    current_instance, current_symbolic, instance_composition.attributes
                )
            )

            exchangeable_features.update(
                self._process_exchangeable_parts(
                    current_instance, instance_composition.exchangeable_parts
                )
            )
            queue.extend(
                self._process_unique_parts(
                    current_instance,
                    current_symbolic,
                    instance_composition.unique_parts,
                )
            )

        result.extend(itertools.chain.from_iterable(exchangeable_features.values()))
        self.exchangeable_features = exchangeable_features
        return result

    @staticmethod
    def _process_attributes(
        instance: DataAccessObject,
        symbolic_root: Variable,
        attributes: list[sqlalchemy.Column],
    ) -> list[MappedVariable]:
        """
        Collects symbolic variables for all scalar data columns of ``instance``.

        Columns whose value is not a compatible primitive type are skipped.
        :param instance: The DAO instance to inspect.
        :param symbolic_root: The symbolic variable rooted at ``instance``.
        :param attributes: The RSPN specification describing the instance's schema.
        :return: One typed ``MappedVariable`` per compatible scalar attribute.
        """
        result = []
        for attribute in attributes:
            value = getattr(instance, attribute.key)

            if not isinstance(value, compatible_types):
                continue

            symbolic_attribute = getattr(symbolic_root, attribute.name)
            symbolic_attribute._type_ = get_python_type_from_sqlalchemy_column(
                attribute
            )
            result.append(symbolic_attribute)
        return result

    @staticmethod
    def _process_unique_parts(
        instance: DataAccessObject,
        symbolic_root: Variable,
        unique_parts: list[str],
    ) -> deque[Any]:
        """
        Enqueues non-null unique-part (many-to-one) relations for further traversal.

        :param instance: The DAO instance to inspect.
        :param symbolic_root: The symbolic variable rooted at ``instance``.
        :param unique_parts: The RSPN specification describing the instance's schema.
        :return: ``(child_instance, child_symbolic)`` pairs ready for BFS expansion.
        """
        queue = deque()
        for part in unique_parts:
            value = getattr(instance, part)

            if value is None:
                continue

            queue.append((value, getattr(symbolic_root, part)))
        return queue

    @staticmethod
    def _process_exchangeable_parts(current_instance, exchangeable_parts):
        """
        Collects aggregation statistic variables for all one-to-many relations of ``current_instance``.

        :param current_instance: The DAO instance to inspect.
        :param exchangeable_parts: The RSPN specification describing the instance's schema.
        :return: A mapping from each discovered aggregation variable to the exchangeable-part field name it
        """
        result = defaultdict(list)
        dao_state = FromDataAccessObjectState()
        domain_object = current_instance.from_dao(dao_state)

        for exchangeable_part in exchangeable_parts:
            if not isinstance(domain_object, HasExchangeablePartAggregations):
                continue
            aggregation_instance = domain_object.get_aggregation_class_by_part_name(
                exchangeable_part
            )
            if aggregation_instance is None:
                continue
            for aggregation in aggregation_instance.symbolic_aggregation_features:
                result[exchangeable_part].append(aggregation)

        return result

    def apply_mapping(self, instance: DataAccessObject) -> list:
        """
        Extracts the mapped values for each feature from the given instance.
        :param instance: The instance to extract features from.
        :return: A list of mapped values.
        """
        aggregation_to_part = {
            aggregation: part
            for part, aggregations in self.exchangeable_features.items()
            for aggregation in aggregations
        }
        result = []
        dao_state = FromDataAccessObjectState()
        domain_object = instance.from_dao(dao_state)
        for feature in self.features:
            if feature in aggregation_to_part:
                aggregation_instance = domain_object.get_aggregation_class_by_part_name(
                    aggregation_to_part[feature]
                )
                result.append(
                    feature.apply_mapping_on_external_root(aggregation_instance)
                )
            else:
                result.append(feature.apply_mapping_on_external_root(instance))
        return result

    def create_dataframe(self, instances: list[DataAccessObject]) -> pd.DataFrame:
        """
        Create a dataframe from the given instances.
        :param instances: The instances to create the dataframe from.
        :return: A dataframe containing the mapped values for each feature.
        """
        result = [self.apply_mapping(instance) for instance in instances]
        features_names = [feature._name_ for feature in self.features]
        return pd.DataFrame(columns=features_names, data=result)

    def preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess the dataframe for JointProbabilityTrees by converting boolean columns to integers and enum columns to hashes.
        :param df: The dataframe to preprocess.
        :return: The dataframe in a JPT compatible format.
        """
        feature_map = dict(zip(df.columns, self.features))
        for column in df.columns:
            feature = feature_map[column]
            if feature._type_ is bool:
                df[column] = df[column].astype(int)
            elif isinstance(feature._type_, enum.EnumType):
                df[column] = df[column].apply(lambda x: hash(x))
            elif feature._type_ not in compatible_types and feature._type_ is not None:
                raise TypeError(
                    f"Unsupported type {feature._type_} for column {column}"
                )
        return df


@dataclass
class EntityCompositionDescriptor:
    """
    Describes the composition of a domain class in terms of its scalar attributes, unique-part relations, and exchangeable-part relations.
    It is constructed from a DAO class' SQLAlchemy mapper.
    """

    dao_class: Type[DataAccessObject] = field(init=True)
    """
    The DAO class whose SQLAlchemy mapper is inspected.
    """

    attributes: list[sqlalchemy.Column] = field(init=False, default_factory=list)
    """
    Scalar data columns of the DAO class.
    """

    unique_parts: list[str] = field(init=False, default_factory=list)
    """
    Field names of many-to-one (unique-part) relations.
    """

    exchangeable_parts: list[str] = field(init=False, default_factory=list)
    """
    Field names of one-to-many (exchangeable-part) relations.
    """

    def __post_init__(self):
        mapper = sqlalchemy.inspection.inspect(self.dao_class)

        for relationship in mapper.relationships:
            if relationship.direction == MANYTOONE:
                self.unique_parts.append(relationship.key)
            # not many to many since we have the association table
            elif relationship.direction == ONETOMANY:
                self.exchangeable_parts.append(relationship.key)
        for column in mapper.columns:
            if is_data_column(column) and column not in mapper.relationships:
                self.attributes.append(column)
