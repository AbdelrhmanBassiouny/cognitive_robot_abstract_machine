from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import assert_never, Any

from probabilistic_model.probabilistic_circuit.rx.helper import fully_factorized
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
)
from random_events.set import Set
from random_events.variable import Continuous, Integer, Symbolic, Variable
from sqlalchemy import inspect, Column
from sqlalchemy.orm import Relationship
from typing_extensions import List, Optional, Dict

from krrood.adapters.json_serializer import list_like_classes
from krrood.class_diagrams.class_diagram import WrappedClass, ClassDiagram
from krrood.class_diagrams.wrapped_field import WrappedField
from krrood.ormatic.dao import DataAccessObject, get_dao_class

SKIPPED_FIELD_TYPES = (datetime,)


@dataclass
class Parameterizer:
    """
    Parameterizer for creating random event variables from WrappedClass instances.

    This class provides methods to recursively inspect a class structure (via WrappedClass)
    and generate corresponding random variables for probabilistic modeling.
    """

    def __call__(self, wrapped_class: WrappedClass) -> List[Variable]:
        """
        Create random event variables from a WrappedClass.

        """
        return self.parameterize(wrapped_class, prefix=wrapped_class.clazz.__name__)

    def parameterize(self, wrapped_class: WrappedClass, prefix: str) -> List[Variable]:
        """
        Create variables for all fields of a WrappedClass.

        :return: A list of random event variables.
        """

        variables_by_name: Dict[str, Variable] = {}

        for wrapped_field in wrapped_class.fields:
            for var in self._parameterize_wrapped_field(wrapped_field, prefix):
                variables_by_name.setdefault(var.name, var)

        return list(variables_by_name.values())

    def _parameterize_wrapped_field(
        self, wrapped_field: WrappedField, prefix: str
    ) -> List[Variable]:
        """
        Create variables for a single WrappedField.

        :return: A list of variables
        """
        field_name = f"{prefix}.{wrapped_field.name}"

        if self.skip_field(wrapped_field):
            return []

        if wrapped_field.is_one_to_one_relationship and not wrapped_field.is_enum:
            return self._parameterize_relationship(wrapped_field, field_name)

        variable = self._create_variable_from_field(wrapped_field, field_name)

        return [variable]

    def skip_field(self, wrapped_field: WrappedField) -> bool:
        """
        Skip fields listed in SKIPPED_FIELD_TYPES.
        """
        return wrapped_field.type_endpoint in SKIPPED_FIELD_TYPES

    def _parameterize_relationship(
        self, wrapped_field: WrappedField, field_name: str
    ) -> List[Variable]:
        """
        Create variables for a one-to-one relationship field.

        :return: A list of variables from the related class.
        """
        class_diagram = getattr(wrapped_field.clazz, "_class_diagram", None)
        if not class_diagram:
            return []

        target_type = wrapped_field.type_endpoint
        if target_type not in class_diagram._cls_wrapped_cls_map:
            return []

        target_wrapped_class = class_diagram.get_wrapped_class(target_type)
        return self.parameterize(target_wrapped_class, prefix=field_name)

    def _create_variable_from_field(
        self, wrapped_field: WrappedField, field_name: str
    ) -> Optional[Variable]:
        """
        Create a random event variable from a WrappedField based on its type.

        :return: A random event variable or raise error if the type is not supported.
        """
        endpoint_type = wrapped_field.type_endpoint

        if wrapped_field.is_enum:
            return Symbolic(field_name, Set.from_iterable(list(endpoint_type)))

        elif endpoint_type is int:
            return Integer(field_name)

        elif endpoint_type is float:
            return Continuous(field_name)

        elif endpoint_type is bool:
            return Symbolic(field_name, Set.from_iterable([True, False]))

        else:
            raise NotImplementedError(
                f"No conversion between {endpoint_type} and random_events.Variable is known."
            )

    def create_fully_factorized_distribution(
        self,
        variables: List[Variable],
    ) -> ProbabilisticCircuit:
        """
        Create a fully factorized probabilistic circuit over the given variables.

        :return: A fully factorized probabilistic circuit.
        """
        distribution_variables = [v for v in variables if not isinstance(v, Integer)]

        return fully_factorized(
            distribution_variables,
            means={v: 0.0 for v in distribution_variables if isinstance(v, Continuous)},
            variances={
                v: 1.0 for v in distribution_variables if isinstance(v, Continuous)
            },
        )


@dataclass
class DAOParameterizer:

    def parameterize_dao(self, dao: DataAccessObject, prefix: str) -> List[Variable]:
        """
        Create variables for all fields of a WrappedClass.

        :return: A list of random event variables.
        """

        original_class = dao.original_class()
        class_diagram = ClassDiagram([original_class])
        mapper = inspect(dao).mapper

        variables = []

        for wrapped_field in class_diagram.get_wrapped_class(original_class).fields:
            if wrapped_field.type_endpoint in SKIPPED_FIELD_TYPES:
                continue

            column_variables = [
                self._process_column(column, wrapped_field, dao, prefix)
                for column in mapper.columns
            ]
            variables.extend(
                [
                    column_variable
                    for column_variable in column_variables
                    if column_variable is not None
                ]
            )

            for relationship in mapper.relationships:
                variables.extend(
                    self._process_relationship(relationship, wrapped_field, prefix)
                )

        return variables

    def _process_column(
        self,
        column: Column,
        wrapped_field: WrappedField,
        dao: DataAccessObject,
        prefix: str,
    ) -> Optional[Variable]:
        attribute_name = self.column_attribute_name(column)
        if not self.is_attribute_of_interest(attribute_name, wrapped_field):
            return None

        # one to one relationships are handled through relationships, they should never appear here
        if (
            wrapped_field.is_one_to_one_relationship
            and not wrapped_field.is_enum
            and not wrapped_field.type_endpoint is uuid.UUID
        ):
            assert_never(wrapped_field)

        # Not sure how we want to handle one to many relationships. We dont know how long the container should be
        # so does it really make sense to parameterize it?
        if wrapped_field.is_one_to_many_relationship:
            assert_never(wrapped_field)

        attribute = getattr(dao, attribute_name)
        if not attribute:
            if wrapped_field.type_endpoint in (str, uuid.UUID):
                return None
            var = self._create_variable_from_wrapped_field(
                wrapped_field, f"{prefix}.{attribute_name}"
            )
        elif not isinstance(attribute, list_like_classes):
            # skip attributes that are not None, and not lists. those are already set correctly, and by not
            # adding the variable we dont clutter the model
            return None
        else:
            var = self._create_variable_from_list_attribute(
                attribute, f"{prefix}.{attribute_name}"
            )
        return var

    def _process_relationship(
        self, relationship: Relationship, wrapped_field: WrappedField, prefix: str
    ):
        attribute_name = relationship.key

        if not self.is_attribute_of_interest(attribute_name, wrapped_field):
            return []
        elif wrapped_field.is_one_to_many_relationship:
            # Here again, we dont know how long the container should be. Not sure how to handle this yet.
            return []
        elif wrapped_field.is_one_to_one_relationship:
            dao_class = get_dao_class(wrapped_field.type_endpoint)
            variables = self.parameterize_dao(
                dao=dao_class(),
                prefix=f"{prefix}.{attribute_name}",
            )
            return variables
        else:
            assert_never(wrapped_field)

    def is_attribute_of_interest(
        self, attribute_name: Optional[str], wrapped_field: WrappedField
    ):
        """
        If its optional, we dont care. My assumption for now is, that the plan resolves this
        """
        return (
            attribute_name
            and wrapped_field.public_name == attribute_name
            and not wrapped_field.is_optional
        )

    def column_attribute_name(self, column: Column) -> Optional[str]:
        if (
            column.key == "polymorphic_type"
            or column.primary_key
            or column.foreign_keys
        ):
            return None

        return column.name

    def _create_variable_from_wrapped_field(
        self, wrapped_field: WrappedField, name: str
    ) -> Variable:
        """
        Create a random event variable from a WrappedField based on its type.

        :return: A random event variable or raise error if the type is not supported.
        """
        type_endpoint = wrapped_field.type_endpoint

        if wrapped_field.is_enum:
            return Symbolic(name, Set.from_iterable(list(type_endpoint)))
        elif type_endpoint is int:
            return Integer(name)
        elif type_endpoint is float:
            return Continuous(name)
        elif type_endpoint is bool:
            return Symbolic(name, Set.from_iterable([True, False]))
        else:
            raise NotImplementedError(
                f"No conversion between {type_endpoint} and random_events.Variable is known."
            )

    def _create_variable_from_list_attribute(
        self, list_attribute: List[Any], name: str
    ) -> Symbolic:
        """
        Creates a random event variable from a list attribute. That variable is the union of all elements in the list.
        """
        return Symbolic(name, Set.from_iterable(list_attribute))
