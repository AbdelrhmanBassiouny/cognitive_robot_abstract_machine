from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import assert_never, Any, Tuple

from random_events.interval import Bound
from random_events.interval import SimpleInterval
from random_events.product_algebra import SimpleEvent
from random_events.set import Set
from random_events.variable import Continuous, Integer, Symbolic, Variable
from sqlalchemy import inspect, Column
from sqlalchemy.orm import Relationship
from typing_extensions import List, Optional

from krrood.adapters.json_serializer import list_like_classes
from krrood.class_diagrams.class_diagram import WrappedClass
from krrood.class_diagrams.wrapped_field import WrappedField
from krrood.ormatic.dao import DataAccessObject, get_dao_class
from probabilistic_model.probabilistic_circuit.rx.helper import fully_factorized
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
)

SKIPPED_FIELD_TYPES = (datetime,)


@dataclass
class Parameterizer:

    variables: List[Variable] = field(default_factory=list)
    simple_event: SimpleEvent = field(default_factory=lambda: SimpleEvent({}))

    def parameterize_dao(
        self, dao: DataAccessObject, prefix: str
    ) -> Tuple[List[Variable], Optional[SimpleEvent]]:
        """
        Create variables for all fields of a DataAccessObject.

        :return: A list of random event variables and a SimpleEvent containing the values.
        """

        original_class = dao.original_class()
        wrapped_class = WrappedClass(original_class)
        mapper = inspect(dao).mapper

        for wrapped_field in wrapped_class.fields:
            if wrapped_field.type_endpoint in SKIPPED_FIELD_TYPES:
                continue

            for column in mapper.columns:
                vars, vals = self._process_column(column, wrapped_field, dao, prefix)

                for val, var in zip(vals, vars):
                    if var is None:
                        continue
                    self.variables.append(var)
                    if val is None:
                        continue

                    event = self._create_simple_event_singleton_from_set_attribute(
                        var, val
                    )
                    self.simple_event.update(event)

            for relationship in mapper.relationships:
                self._process_relationship(relationship, wrapped_field, dao, prefix)

        self.simple_event.fill_missing_variables(self.variables)
        return self.variables, self.simple_event

    def _process_column(
        self,
        column: Column,
        wrapped_field: WrappedField,
        dao: DataAccessObject,
        prefix: str,
    ) -> Tuple[List[Variable], List[Any]]:
        attribute_name = self.column_attribute_name(column)
        if not self.is_attribute_of_interest(attribute_name, wrapped_field):
            return [], []

        attribute = getattr(dao, attribute_name)
        if wrapped_field.is_optional and attribute is None:
            return [], []

        if wrapped_field.is_collection_of_builtins:
            variables = [
                self._create_variable_from_type(
                    wrapped_field.type_endpoint, f"{prefix}.{value}"
                )
                for value in attribute
            ]
            return variables, attribute

        if attribute is None:
            if wrapped_field.type_endpoint is str:
                return [], []
            var = self._create_variable_from_type(
                wrapped_field.type_endpoint, f"{prefix}.{attribute_name}"
            )
            return [var], [None]
        elif isinstance(attribute, list_like_classes):
            # skip attributes that are not None, and not list-like. those are already set correctly, and by not
            # adding the variable we dont clutter the model
            return [], []
        else:
            var = self._create_variable_from_type(
                wrapped_field.type_endpoint, f"{prefix}.{attribute_name}"
            )
            return [var], [attribute]

    def _create_simple_event_singleton_from_set_attribute(
        self, variable: Variable, attribute: Any
    ):
        """
        Create a SimpleEvent containing a single value for the given variable, based on the type of the attribute.

        :param variable: The variable for which to create the event.
        :param attribute: The attribute value to create the event from.

        :return: A SimpleEvent containing the given value.
        """
        if isinstance(attribute, bool) or isinstance(attribute, enum.Enum):
            return SimpleEvent({variable: Set.from_iterable([attribute])})
        elif isinstance(attribute, int) or isinstance(attribute, float):
            return SimpleEvent(
                {
                    variable: SimpleInterval(
                        attribute, attribute, Bound.CLOSED, Bound.CLOSED
                    )
                }
            )
        else:
            assert_never(attribute)

    def _process_relationship(
        self,
        relationship: Relationship,
        wrapped_field: WrappedField,
        dao: DataAccessObject,
        prefix: str,
    ):
        """
        Process a SQLAlchemy relationship and add variables and events for it.

        ..Note:: This method is recursive and will process all relationships of a relationship. Optional relationships that are None will be skipped, as we decided that they should not be included in the model.

        :param relationship: The SQLAlchemy relationship to process.
        :param wrapped_field: The WrappedField corresponding to the relationship.
        :param dao: The DataAccessObject containing the relationship.
        :param prefix: The prefix to use for variable names.
        """
        attribute_name = relationship.key
        attribute_dao = getattr(dao, attribute_name)

        # %% Skip attributes that are not of interest.
        if not self.is_attribute_of_interest(attribute_name, wrapped_field):
            return
        if wrapped_field.is_optional and attribute_dao is None:
            return

        # %% one to many relationships
        if wrapped_field.is_one_to_many_relationship:
            for value in attribute_dao:
                self.parameterize_dao(dao=value, prefix=f"{prefix}.{attribute_name}")
            return

        # %% one to one relationships
        if wrapped_field.is_one_to_one_relationship:
            if attribute_dao is None:
                attribute_dao = get_dao_class(wrapped_field.type_endpoint)()
            self.parameterize_dao(
                dao=attribute_dao,
                prefix=f"{prefix}.{attribute_name}",
            )
            return

        else:
            assert_never(wrapped_field)

    def is_attribute_of_interest(
        self, attribute_name: Optional[str], wrapped_field: WrappedField
    ) -> bool:
        """
        Check if the given attribute name corresponds to the given WrappedField and is not a UUID.
        """
        return (
            attribute_name
            and wrapped_field.public_name == attribute_name
            and not wrapped_field.type_endpoint is uuid.UUID
        )

    def column_attribute_name(self, column: Column) -> Optional[str]:
        """
        Get the attribute name corresponding to a SQLAlchemy Column, if it is not a primary key, foreign key, or polymorphic type.

        :return: The attribute name or None if the column is not of interest.
        """
        if (
            column.key == "polymorphic_type"
            or column.primary_key
            or column.foreign_keys
        ):
            return None

        return column.name

    def _create_variable_from_type(self, field_type: type, name: str) -> Variable:
        """
        Create a random event variable based on its type.

        :param field_type: The type of the field for which to create the variable. Usually accessed through WrappedField.type_endpoint.
        :param name: The name of the variable.

        :return: A random event variable or raise error if the type is not supported.
        """

        if issubclass(field_type, enum.Enum):
            return Symbolic(name, Set.from_iterable(list(field_type)))
        elif field_type is int:
            return Integer(name)
        elif field_type is float:
            return Continuous(name)
        elif field_type is bool:
            return Symbolic(name, Set.from_iterable([True, False]))
        else:
            raise NotImplementedError(
                f"No conversion between {field_type} and random_events.Variable is known."
            )

    def create_fully_factorized_distribution(
        self,
    ) -> ProbabilisticCircuit:
        """
        Create a fully factorized probabilistic circuit over the given variables.

        :return: A fully factorized probabilistic circuit.
        """
        distribution_variables = [
            v for v in self.variables if not isinstance(v, Integer)
        ]

        return fully_factorized(
            distribution_variables,
            means={v: 0.0 for v in distribution_variables if isinstance(v, Continuous)},
            variances={
                v: 1.0 for v in distribution_variables if isinstance(v, Continuous)
            },
        )
