"""
The colour cycle loose scene objects are drawn in.

Both the onboarder (which bakes colours into a scene bundle) and the live bridge (which
assigns them on the fly) use this one cycle, so the same object keeps its colour whether
the viewer renders the recording or the running world.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from semantic_digital_twin.world_description.geometry import Color
from typing_extensions import List, Optional, TYPE_CHECKING

from cramera.body_geometry import shape_collections_of

if TYPE_CHECKING:
    from semantic_digital_twin.world_description.world_entity import (
        KinematicStructureEntity,
    )

OBJECT_COLORS = (
    "#f3f0ea",
    "#cf5b3a",
    "#b8bcc4",
    "#e7c26a",
    "#7fb069",
    "#5b8cff",
    "#c98bdb",
    "#ff9d6b",
    "#6bd0c0",
    "#d0c86b",
)
"""
Distinct, muted colours that read well against the viewer's dark stage.
"""


@dataclass(frozen=True)
class ObjectPalette:
    """
    Assigns object colours by position, wrapping around when it runs out.
    """

    colors: List[Color] = field(
        default_factory=lambda: [
            # by name, not ``cls``: the factory runs after the class exists
            ObjectPalette._color_from_hex(hex_value)
            for hex_value in OBJECT_COLORS
        ]
    )
    """
    The colour cycle, in assignment order.
    """

    def color_for(self, index: int) -> str:
        """
        The colour of the object at the given position in the scene, as ``#rrggbb``.
        """
        return self.css_color(self.colors[index % len(self.colors)])

    def color_of(self, entity: Optional[KinematicStructureEntity], index: int) -> str:
        """
        The colour an entity is shown in, as ``#rrggbb``: the one its world authored
        onto a shape of it, or its position's cycle colour when no shape declares one.

        :param entity: The body or region to colour, or None for one only known by key.
        :param index: The entity's position in the scene, picking its fallback colour.
        """
        authored = self._authored_color(entity) if entity is not None else None
        return self.css_color(authored) if authored else self.color_for(index)

    @staticmethod
    def _authored_color(entity: KinematicStructureEntity) -> Optional[Color]:
        """
        The first colour an entity's shapes declare, or None when every shape keeps the
        default white.

        ..note:: A shape deliberately authored in the default white is indistinguishable
           from one that was never coloured, and falls back to the cycle.

        :param entity: The body or region whose shapes are read.
        """
        white = Color()
        for shape_collection in shape_collections_of(entity):
            for shape in shape_collection.shapes:
                if shape.color != white:
                    return shape.color
        return None

    @staticmethod
    def _color_from_hex(hex_value: str) -> Color:
        """
        Parse a ``#rrggbb`` string into a :class:`Color`.

        :param hex_value: The colour, as a leading-``#`` hex triplet.
        """
        hex_value = hex_value.lstrip("#")
        red, green, blue = (
            int(hex_value[channel : channel + 2], 16) / 255 for channel in (0, 2, 4)
        )
        return Color(R=red, G=green, B=blue)

    @staticmethod
    def css_color(color: Color) -> str:
        """
        Render a :class:`Color` as the ``#rrggbb`` string the viewer uses directly.

        :param color: The colour to render.
        """
        return "#%02x%02x%02x" % (
            round(color.R * 255),
            round(color.G * 255),
            round(color.B * 255),
        )
