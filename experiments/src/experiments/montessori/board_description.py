"""
The shape-sorting board stated in the entity query language, and the layout a look lays
over a picture read back out of such a statement.

A board is described in the world's own vocabulary -- a
:class:`~experiments.montessori.semantics.ShapeSortingBoard` whose lid measures so much
and stands so tall, with :class:`~experiments.montessori.semantics.ShapeSortingHole`
apertures of these shapes and sizes at these places on the lid -- so what a look is asked
to find is the statement a query about a board the world already holds would make.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

from typing_extensions import Any, Dict, Optional, Tuple

from experiments.episodes.artifacts import keep_mesh
from experiments.montessori.exceptions import BoardDescriptionIncomplete
from experiments.montessori.hole_geometry import (
    HOLE_MARKER_THICKNESS,
    BoardHoleLayout,
    HoleFootprint,
    hole_names,
)
from experiments.montessori.planar_geometry import PlanarPoint, PlanarSize
from experiments.montessori.semantics import (
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
    Region,
)

BOARD_NAME = "board"
"""
What a board stood in a world from its description is called, under the prefix it is
stood with.
"""


class StatedBoardAttribute(StrEnum):
    """
    The attributes of a :class:`~experiments.montessori.semantics.ShapeSortingBoard` a
    description of one states.
    """

    LID_SIZE = "lid_size"
    """
    How far the lid reaches along the board's own axes.
    """

    HEIGHT = "height"
    """
    How far the lid stands above the surface the board rests on.
    """

    APERTURES = "apertures"
    """
    The holes cut through the lid.
    """


class StatedHoleAttribute(StrEnum):
    """
    The attributes of a :class:`~experiments.montessori.semantics.ShapeSortingHole` a
    description of one states.
    """

    SHAPE_CATEGORY = "shape_category"
    """
    The shape the hole is cut in.
    """

    FOOTPRINT_SIZE = "footprint_size"
    """
    How far the hole reaches along its own axes.
    """

    POSITION_ON_LID = "position_on_lid"
    """
    Where the hole's centre stands on the lid.
    """

    TURN_ON_LID = "turn_on_lid"
    """
    How far the hole is turned on the lid.
    """


# %% one hole


@dataclass(frozen=True)
class DescribedHole:
    """
    One hole of the board, in the values a statement describes it with.
    """

    shape_category: MontessoriShapeCategory
    """
    The shape the hole is cut in.
    """

    footprint_size: PlanarSize
    """
    How far it reaches along its own axes; see
    :attr:`~experiments.montessori.semantics.ShapeSortingHole.footprint_size`.
    """

    position_on_lid: PlanarPoint
    """
    Where its centre stands, from the lid's centre along the lid's own axes, in metres.
    """

    turn_on_lid: float
    """
    How far it is turned about the lid's vertical axis, in radians.
    """

    @classmethod
    def of_footprint(cls, footprint: HoleFootprint) -> DescribedHole:
        """
        :param footprint: A hole of a layout.
        :return: The description that hole answers.
        """
        return cls(
            shape_category=footprint.category,
            footprint_size=footprint.own_size,
            position_on_lid=footprint.center,
            turn_on_lid=footprint.turn,
        )

    @property
    def footprint(self) -> HoleFootprint:
        """
        The hole this describes, as a layout holds it.
        """
        return HoleFootprint.of_description(
            self.shape_category,
            size=self.footprint_size,
            center=self.position_on_lid,
            turn=self.turn_on_lid,
        )

    def statement(self) -> Match[ShapeSortingHole]:
        """
        :return: The statement describing this hole.
        """
        return a(ShapeSortingHole)(
            **{
                StatedHoleAttribute.SHAPE_CATEGORY: self.shape_category,
                StatedHoleAttribute.FOOTPRINT_SIZE: self.footprint_size,
                StatedHoleAttribute.POSITION_ON_LID: self.position_on_lid,
                StatedHoleAttribute.TURN_ON_LID: self.turn_on_lid,
            }
        )

    def region_annotation(self, name: PrefixedName) -> ShapeSortingHole:
        """
        The hole this describes, as a thin region shaped after its own outline and
        carrying the values it was stated with, not yet placed in any world.

        :param name: What the hole and its region are called.
        """
        return ShapeSortingHole(
            name=name,
            root=Region(
                name=name,
                area=ShapeCollection(
                    [keep_mesh(self.footprint.extrude(HOLE_MARKER_THICKNESS))]
                ),
            ),
            shape_category=self.shape_category,
            footprint_size=self.footprint_size,
            position_on_lid=self.position_on_lid,
            turn_on_lid=self.turn_on_lid,
        )


# %% the whole board


@dataclass(frozen=True)
class DescribedBoard:
    """
    A shape-sorting board, in the values a statement describes it with: how far its lid
    reaches, how tall it stands, and the holes cut through the lid.
    """

    lid_size: PlanarSize
    """
    How far the lid reaches along the board's own axes, in metres.
    """

    height: float
    """
    How far the lid stands above the surface the board rests on, in metres.
    """

    holes: Tuple[DescribedHole, ...]
    """
    The holes, in the order they were stated.
    """

    @classmethod
    def of_layout(cls, layout: BoardHoleLayout, height: float) -> DescribedBoard:
        """
        :param layout: The holes cut through a lid, and how far that lid reaches.
        :param height: How far the lid stands above the surface the board rests on.
        :return: The description a board of that layout and height answers.
        """
        return cls(
            lid_size=layout.size,
            height=height,
            holes=tuple(DescribedHole.of_footprint(hole) for hole in layout.holes),
        )

    @cached_property
    def layout(self) -> BoardHoleLayout:
        """
        The holes this describes as one rigid layout, which is what a look fits over a
        picture.
        """
        return BoardHoleLayout(
            holes=tuple(hole.footprint for hole in self.holes), size=self.lid_size
        )

    def statement(self) -> Match[ShapeSortingBoard]:
        """
        :return: The statement describing this board, in the world's own vocabulary.
        """
        return a(ShapeSortingBoard)(
            **{
                StatedBoardAttribute.LID_SIZE: self.lid_size,
                StatedBoardAttribute.HEIGHT: self.height,
                StatedBoardAttribute.APERTURES: [
                    hole.statement() for hole in self.holes
                ],
            }
        )

    @classmethod
    def of_statement(cls, statement: Match[ShapeSortingBoard]) -> DescribedBoard:
        """
        Read the board a statement describes.

        :param statement: A statement over
            :class:`~experiments.montessori.semantics.ShapeSortingBoard`.
        :raises BoardDescriptionIncomplete: If it leaves open the lid's size or height,
            or any stated hole's shape, size or place on the lid.
        :return: The board it describes.
        """
        stated = statement._kwargs_
        return cls(
            lid_size=cls._stated(stated, StatedBoardAttribute.LID_SIZE),
            height=cls._stated(stated, StatedBoardAttribute.HEIGHT),
            holes=tuple(
                cls._hole_of(index, hole_statement._kwargs_)
                for index, hole_statement in enumerate(
                    cls._stated(stated, StatedBoardAttribute.APERTURES)
                )
            ),
        )

    def stand_in(self, world: World, lid_pose: Pose, prefix: str) -> ShapeSortingBoard:
        """
        Stand a board answering this description in a world, where it was found.

        The board is a solid as large as its lid and as tall as it stands, and each hole
        a thin region shaped after its own outline, flush with the lid and placed where
        this layout puts it. Board and holes carry the values they were stated with.

        :param world: The world to stand the board in, modified in place.
        :param lid_pose: Where the lid's centre stands, in the world root frame; only
            its position and its turn about the vertical place the board.
        :param prefix: What the board's and its holes' names are prefixed with.
        :return: The board, as the world now holds it.
        """
        center = PlanarPoint(float(lid_pose.x), float(lid_pose.y))
        yaw = float(lid_pose.yaw)
        lid_height = float(lid_pose.z)
        with world.modify_world():
            board = ShapeSortingBoard(
                name=PrefixedName(BOARD_NAME, prefix),
                root=Body.from_shape_collection(
                    PrefixedName(BOARD_NAME, prefix),
                    ShapeCollection(
                        [
                            Box(
                                scale=Scale(
                                    self.lid_size.x, self.lid_size.y, self.height
                                )
                            )
                        ]
                    ),
                ),
                lid_size=self.lid_size,
                height=self.height,
            )
            self._fix_to_root(
                world, board.root, center, yaw, lid_height - self.height / 2
            )
            world.add_semantic_annotation(board)
            names = hole_names([hole.shape_category for hole in self.holes])
            for described, placed, name in zip(
                self.holes, self.layout.placed(center, yaw), names
            ):
                hole = described.region_annotation(PrefixedName(name, prefix))
                self._fix_to_root(
                    world,
                    hole.root,
                    placed.center,
                    yaw,
                    lid_height - HOLE_MARKER_THICKNESS / 2,
                )
                world.add_semantic_annotation(hole)
                board.add(hole)
        return board

    def move_in(self, world: World, board: ShapeSortingBoard, lid_pose: Pose) -> None:
        """
        Move a board this description stood to where a lid pose now says it is.

        :param world: The world holding the board.
        :param board: The board, as :meth:`stand_in` stood it.
        :param lid_pose: Where the lid's centre now stands, in the world root frame;
            only its position and its turn about the vertical place the board.
        """
        world.move_branch_to(
            board.root,
            HomogeneousTransformationMatrix.from_xyz_rpy(
                x=float(lid_pose.x),
                y=float(lid_pose.y),
                z=float(lid_pose.z) - self.height / 2,
                yaw=float(lid_pose.yaw),
                reference_frame=world.root,
            ),
        )

    @staticmethod
    def _fix_to_root(
        world: World,
        entity: KinematicStructureEntity,
        center: PlanarPoint,
        yaw: float,
        height: float,
    ) -> None:
        """
        Fix an entity to the world root at a place on a horizontal plane.

        :param world: The world holding the entity.
        :param entity: The entity to place.
        :param center: Where it stands, in the world root frame.
        :param yaw: How far it is turned about the vertical, in radians.
        :param height: Height of its origin above the world root, in metres.
        """
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=entity,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=center.x,
                    y=center.y,
                    z=height,
                    yaw=yaw,
                    reference_frame=world.root,
                ),
            )
        )

    @classmethod
    def _hole_of(cls, index: int, stated: Dict[str, Any]) -> DescribedHole:
        """
        :param index: Where the hole stands among the stated holes.
        :param stated: What the hole's own statement fixes.
        :return: The hole it describes.
        """
        return DescribedHole(
            shape_category=cls._stated(
                stated, StatedHoleAttribute.SHAPE_CATEGORY, index
            ),
            footprint_size=cls._stated(
                stated, StatedHoleAttribute.FOOTPRINT_SIZE, index
            ),
            position_on_lid=cls._stated(
                stated, StatedHoleAttribute.POSITION_ON_LID, index
            ),
            turn_on_lid=stated.get(
                StatedHoleAttribute.TURN_ON_LID, ShapeSortingHole.turn_on_lid
            ),
        )

    @staticmethod
    def _stated(
        stated: Dict[str, Any], attribute: str, hole_index: Optional[int] = None
    ) -> Any:
        """
        :param stated: What a statement fixes.
        :param attribute: The attribute to read.
        :param hole_index: Which stated hole the statement describes, or None for the
            board itself.
        :raises BoardDescriptionIncomplete: If the statement leaves the attribute open.
        :return: The value the statement fixes the attribute to.
        """
        value = stated.get(attribute)
        if value is None or value is Ellipsis:
            raise BoardDescriptionIncomplete(
                missing_attribute=attribute, hole_index=hole_index
            )
        return value
