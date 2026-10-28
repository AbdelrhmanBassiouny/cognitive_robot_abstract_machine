from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from enum import Enum

from typing_extensions import Any, Dict, List

from coraplex.datastructures.enums import NodeDetailNotation
from krrood.class_diagrams.attribute_introspector import DataclassOnlyIntrospector
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import (
    Body,
    SemanticAnnotation,
)

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
        :return: A class by its name, an enumeration member by its name, a body or a
            semantic annotation by its name, a pose by its position, a boolean as on or
            off, a list by its items, a match by :meth:`render_match`, an open value as
            any value of its type, a failure by its message, a description by
            :meth:`render_description`, and anything else by its text.
        """
        if isinstance(value, type):
            return value.__name__
        if isinstance(value, Enum):
            return value.name
        if isinstance(value, (Body, SemanticAnnotation)):
            return str(value.name)
        if isinstance(value, Pose):
            position = value.position
            return NodeDetailNotation.PART_SEPARATOR.join(
                NodeDetailNotation.COORDINATE_FORMAT.format(float(coordinate))
                for coordinate in (position.x, position.y, position.z)
            )
        if isinstance(value, bool):
            return (
                NodeDetailNotation.SWITCHED_ON
                if value
                else NodeDetailNotation.SWITCHED_OFF
            )
        if isinstance(value, (int, float)):
            return NodeDetailNotation.NUMBER_FORMAT.format(value)
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return NodeDetailNotation.PART_SEPARATOR.join(
                self.render(item, nested) for item in value
            )
        if isinstance(value, Match):
            return self.render_match(value, nested)
        if isinstance(value, Variable):
            return f"{NodeDetailNotation.OPEN_VALUE} {value._name_}"
        if isinstance(value, BaseException):
            return str(value)
        if is_dataclass(value):
            return self.render_description(value, nested)
        return str(value)

    def render_match(self, match: Match, nested: bool) -> str:
        """
        :param match: A description a designator leaves to be found, such as a
            sub-action of a composite action.
        :param nested: Whether the match sits in a description nested in the detail.
        :return: The class the match matches, followed by what it states about each
            field unless it is nested or states nothing.
        """
        matched_class = match._type_.__name__
        if nested or not match._kwargs_:
            return matched_class
        return (
            f"{matched_class}{NodeDetailNotation.MATCH_SEPARATOR}"
            f"{self.render_field_values(match._kwargs_)}"
        )

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
            description.
        """
        return NodeDetailNotation.PART_SEPARATOR.join(
            f"{name} {self.render(value, nested=True)}"
            for name, value in field_values.items()
        )


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
        :return: The heading followed by one line per detail, its value written by
            :class:`NodeDetailRenderer`.
        """
        renderer = NodeDetailRenderer()
        return [f"--- {self.heading} ---"] + [
            f"{name}: {renderer.render(value)}" for name, value in self.entries.items()
        ]


@dataclass
class NodeInfo:
    """
    The details of a plan node, shown when it is clicked in the plan visualization.
    """

    sections: List[NodeInfoSection] = field(default_factory=list)
    """
    The groups of details, in the order they are shown.
    """

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        :return: The details of each section, keyed by the heading of that section.
        """
        return {section.heading: section.entries for section in self.sections}

    def to_lines(self) -> List[str]:
        """
        :return: All sections rendered as the lines the visualization displays.
        """
        return [line for section in self.sections for line in section.to_lines()]
