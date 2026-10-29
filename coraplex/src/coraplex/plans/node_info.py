from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, is_dataclass
from enum import Enum

from typing_extensions import Any, Generic, TypeVar

from coraplex.datastructures.enums import NodeDetailNotation
from krrood.class_diagrams.attribute_introspector import DataclassOnlyIntrospector
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.query.match import Match
from krrood.patterns.specificity_ranking import SpecificityRule
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from semantic_digital_twin.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import (
    Body,
    SemanticAnnotation,
)

DetailValueType = TypeVar("DetailValueType")

# %% readable values


@dataclass
class NodeDetailRenderer:
    """
    Writes the value of a plan node's detail as short text to read at a glance.
    """

    def render(self, value: Any, nested: bool = False) -> str:
        """
        :param value: The value of a detail.
        :param nested: Whether the value sits in a description nested in the detail; a
            match or a description nested there is named by its class.
        :return: The value as the most specific :class:`NodeDetailRule` that applies to
            it writes it; without such a rule, a description by
            :meth:`render_description` and anything else by its text.
        """
        rule = NodeDetailRule.most_applicable(value)
        if rule is not None:
            return rule.render(value, nested, self)
        if is_dataclass(value):
            return self.render_description(value, nested)
        return str(value)

    def render_description(self, description: Any, nested: bool) -> str:
        """
        :param description: A dataclass instance, such as a sub-action of a composite
            action.
        :param nested: Whether the description sits in a description nested in the
            detail.
        :return: The class of the description if it is nested, else each of its
            fields that holds a value.
        """
        if nested:
            return type(description).__name__
        attributes = vars(description)
        return self.render_field_values(
            {
                discovered.field.name: attributes[discovered.field.name]
                for discovered in DataclassOnlyIntrospector().discover(
                    type(description)
                )
                if attributes[discovered.field.name] is not None
            }
        )

    def render_field_values(self, field_values: dict[str, Any]) -> str:
        """
        :param field_values: The values of a description's fields, by field name.
        :return: Each field's name followed by its value, rendered as nested in the
            description, one field per line.
        """
        return NodeDetailNotation.FIELD_SEPARATOR.join(
            f"{name} {self.render(value, nested=True)}"
            for name, value in field_values.items()
        )


# %% kinds of values


class NodeDetailRule(
    Generic[DetailValueType], SubClassSafeGeneric, SpecificityRule, ABC
):
    """
    How one kind of value of a plan node's detail is written, for the values of the type
    a subclass binds.
    """

    @classmethod
    def applies(cls, value: Any) -> bool:
        """
        :param value: The value of a detail.
        :return: True if this rule writes the value.
        """
        return isinstance(value, cls.get_type_of_generic_parameter(DetailValueType))

    @classmethod
    @abstractmethod
    def render(
        cls, value: DetailValueType, nested: bool, renderer: NodeDetailRenderer
    ) -> str:
        """
        :param value: A value this rule writes.
        :param nested: Whether the value sits in a description nested in the detail.
        :param renderer: The renderer writing the detail, which writes the parts of the
            value.
        :return: The value as short text.
        """


class ClassDetailRule(NodeDetailRule[type]):
    """
    A class, such as the type a designator parameter asks for, reads as its name.
    """

    @classmethod
    def render(cls, value: type, nested: bool, renderer: NodeDetailRenderer) -> str:
        return value.__name__


class EnumMemberDetailRule(NodeDetailRule[Enum]):
    """
    An enumeration member reads as its name.
    """

    @classmethod
    def render(cls, value: Enum, nested: bool, renderer: NodeDetailRenderer) -> str:
        return value.name


class BodyOrSemanticAnnotationDetailRule(NodeDetailRule[Body | SemanticAnnotation]):
    """
    A body or a semantic annotation reads as its name.
    """

    @classmethod
    def render(
        cls,
        value: Body | SemanticAnnotation,
        nested: bool,
        renderer: NodeDetailRenderer,
    ) -> str:
        return str(value.name)


class PoseDetailRule(NodeDetailRule[Pose]):
    """
    A pose reads as the coordinates of its position, to the millimetre.
    """

    @classmethod
    def render(cls, value: Pose, nested: bool, renderer: NodeDetailRenderer) -> str:
        position = value.position
        return NodeDetailNotation.PART_SEPARATOR.join(
            NodeDetailNotation.COORDINATE_FORMAT.format(float(coordinate))
            for coordinate in (position.x, position.y, position.z)
        )


class BooleanDetailRule(NodeDetailRule[bool]):
    """
    A boolean reads as on or off.
    """

    @classmethod
    def render(cls, value: bool, nested: bool, renderer: NodeDetailRenderer) -> str:
        return (
            NodeDetailNotation.SWITCHED_ON if value else NodeDetailNotation.SWITCHED_OFF
        )


class NumberDetailRule(NodeDetailRule[int | float]):
    """
    A number that is neither a boolean nor an enumeration member reads without the
    digits that carry nothing.
    """

    @classmethod
    def applies(cls, value: Any) -> bool:
        return super().applies(value) and not isinstance(value, (bool, Enum))

    @classmethod
    def render(
        cls, value: int | float, nested: bool, renderer: NodeDetailRenderer
    ) -> str:
        return NodeDetailNotation.NUMBER_FORMAT.format(value)


class TextDetailRule(NodeDetailRule[str]):
    """
    A text that is no enumeration member reads as it is.
    """

    @classmethod
    def applies(cls, value: Any) -> bool:
        return super().applies(value) and not isinstance(value, Enum)

    @classmethod
    def render(cls, value: str, nested: bool, renderer: NodeDetailRenderer) -> str:
        return value


class SequenceDetailRule(NodeDetailRule[list | tuple]):
    """
    A list or tuple that is no enumeration member reads as its items in brackets.
    """

    @classmethod
    def applies(cls, value: Any) -> bool:
        return super().applies(value) and not isinstance(value, Enum)

    @classmethod
    def render(
        cls, value: list | tuple, nested: bool, renderer: NodeDetailRenderer
    ) -> str:
        return NodeDetailNotation.SEQUENCE_FORMAT.format(
            NodeDetailNotation.PART_SEPARATOR.join(
                renderer.render(item, nested) for item in value
            )
        )


class MatchDetailRule(NodeDetailRule[Match]):
    """
    A match, a description a designator leaves to be found such as a sub-action of a
    composite action, reads as the class it matches, followed by what it states about
    each field unless it is nested or states nothing.
    """

    @classmethod
    def render(cls, value: Match, nested: bool, renderer: NodeDetailRenderer) -> str:
        matched_class = value._type_.__name__
        if nested or not value._kwargs_:
            return matched_class
        return (
            f"{matched_class}{NodeDetailNotation.MATCH_SEPARATOR}"
            f"{renderer.render_field_values(value._kwargs_)}"
        )


class VariableDetailRule(NodeDetailRule[Variable]):
    """
    A value a designator leaves open reads as any value of its type.
    """

    @classmethod
    def render(cls, value: Variable, nested: bool, renderer: NodeDetailRenderer) -> str:
        return f"{NodeDetailNotation.OPEN_VALUE} {value._name_}"


class ExceptionDetailRule(NodeDetailRule[BaseException]):
    """
    An exception, such as a plan failure, reads as its message.
    """

    @classmethod
    def render(
        cls, value: BaseException, nested: bool, renderer: NodeDetailRenderer
    ) -> str:
        return str(value)


# %% node details


@dataclass
class NodeInfoSection:
    """
    A group of details of a plan node, shown under one heading.
    """

    heading: str
    """
    The name the group is shown under.
    """

    entries: dict[str, Any] = field(default_factory=dict)
    """
    The details of the group, keyed by the name each is shown under.
    """

    def to_lines(self) -> list[str]:
        """
        :return: The heading followed by the lines of each detail, its value written by
            :class:`NodeDetailRenderer`.
        """
        renderer = NodeDetailRenderer()
        return [f"--- {self.heading} ---"] + [
            line
            for name, value in self.entries.items()
            for line in f"{name}: {renderer.render(value)}".splitlines()
        ]


@dataclass
class NodeInfo:
    """
    The details of a plan node, shown when it is clicked in the plan visualization.
    """

    sections: list[NodeInfoSection] = field(default_factory=list)
    """
    The groups of details, in the order they are shown.
    """

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """
        :return: The details of each section, keyed by the heading of that section.
        """
        return {section.heading: section.entries for section in self.sections}

    def to_lines(self) -> list[str]:
        """
        :return: All sections rendered as the lines the visualization displays.
        """
        return [line for section in self.sections for line in section.to_lines()]
