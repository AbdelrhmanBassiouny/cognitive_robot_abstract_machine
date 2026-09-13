"""
An opening something is posted through, standing in for any
:class:`~semantic_digital_twin.semantic_annotations.semantic_annotations.Aperture` an
insertion targets: it carries the space behind it and one field telling one slot from
another, which is all a query needs to pick the slot a body belongs in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from typing_extensions import Optional

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Region

SLOT_OPENING_SCALE = Scale(0.06, 0.06, 0.002)
"""
How wide the opening reaches and how thin it is cut, in metres.
"""

SLOT_SPACE_BEHIND_SCALE = Scale(0.06, 0.06, 0.1)
"""
How far the space behind an opening reaches, in metres: as wide as the opening and deep
enough to swallow a posted body whole.
"""


class PostedShape(StrEnum):
    """
    The shape of a slot, and of the bodies it takes.
    """

    ROUND = "round"
    SQUARE = "square"


@dataclass(eq=False)
class PostingSlot(Aperture):
    """
    An opening a body of one shape is posted through.
    """

    posted_shape: Optional[PostedShape] = field(kw_only=True, default=None)
    """
    The shape of body this slot takes.
    """

    @classmethod
    def cut_into(
        cls, world: World, posted_shape: PostedShape, opening_at: Point3
    ) -> PostingSlot:
        """
        Stand a slot in a world, with the space behind it hanging directly below its
        opening.

        :param world: The world the slot is stood in.
        :param posted_shape: The shape of body this slot takes.
        :param opening_at: Where the opening stands, in the world root frame.
        """
        opening = Region(
            name=PrefixedName(f"{posted_shape}_opening"),
            area=ShapeCollection([Box(scale=SLOT_OPENING_SCALE)]),
        )
        space_behind = Region(
            name=PrefixedName(f"{posted_shape}_space_behind"),
            area=ShapeCollection([Box(scale=SLOT_SPACE_BEHIND_SCALE)]),
        )
        behind_at = Point3(
            float(opening_at.x),
            float(opening_at.y),
            float(opening_at.z) - SLOT_SPACE_BEHIND_SCALE.z / 2,
        )
        for region, stands_at in ((opening, opening_at), (space_behind, behind_at)):
            world.add_connection(
                FixedConnection(
                    parent=world.root,
                    child=region,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        float(stands_at.x), float(stands_at.y), float(stands_at.z)
                    ),
                )
            )
        slot = cls(
            name=PrefixedName(f"{posted_shape}_slot"),
            root=opening,
            landing_region=space_behind,
            posted_shape=posted_shape,
        )
        world.add_semantic_annotation(slot)
        return slot
