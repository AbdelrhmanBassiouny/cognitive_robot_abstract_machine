"""
The Montessori scene as the scenarios run it on Tracy: the board and the pieces stand on
Tracy's own table, since Tracy carries one and cannot be bolted beside another.

Two scenes stand there. :class:`TracyOnItsOwnTable` builds the board and the pieces from
Tracy's description, for a simulated run; :class:`TracyLookingAtItsOwnTable` has the
robot's own camera find them in the world the robot publishes, for a run on the robot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types import Point3
from semantic_digital_twin.world import World
from typing_extensions import Type

from experiments.montessori.exceptions import WorldHoldsNoSuchRobot
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.montessori.pieces import FULL_SIZE_PIECES, KnownPieceSet
from experiments.montessori.scenarios import (
    LayoutArea,
    MontessoriWorldBuilder,
    PerceivingWorldBuilder,
    WIDEST_PIECE_REACH,
)
from experiments.montessori.world import BOARD_SCALE
from experiments.tracy_experiments.equipment import (
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.montessori.world import (
    BOARD_POSITION_TRACY,
    SHAPE_ROW_SPACING,
    SHAPE_ROW_START_Y,
    SHAPE_ROW_X,
    TracyMontessoriWorld,
)

TRACY_MOUNT_X = 0.0
"""
Where Tracy's root is bolted along x, in the world root frame.
"""

TRACY_MOUNT_Y = 0.0
"""
Where Tracy's root is bolted along y, in the world root frame.
"""

WHERE_TRACY_LOOKS_FROM = Point3(0.41, -0.02, 1.79)
"""
Where Tracy's own camera looks at its table from, in the world root frame: the position
its ``camera_link`` ends up at once Tracy is bolted at :data:`TRACY_MOUNT_X` and
:data:`TRACY_MOUNT_Y`, read off the description and rounded to the centimetre.
"""

PIECES_IN_THE_ROW = 4
"""
How many pieces the demo stands in its row on Tracy's table, which is how far along y
the area a layout draws from reaches.
"""


def layout_area_on_tracys_table() -> LayoutArea:
    """
    The patch of Tracy's own table a layout stands its pieces on: the row the demo
    stands its pieces in, widened to a rectangle reaching from that row up to the board
    and inset by the reach of the widest piece.
    """
    board_near_x = float(BOARD_POSITION_TRACY.x) - BOARD_SCALE.x / 2
    return LayoutArea(
        minimum_x=SHAPE_ROW_X,
        maximum_x=board_near_x - WIDEST_PIECE_REACH,
        minimum_y=SHAPE_ROW_START_Y,
        maximum_y=SHAPE_ROW_START_Y + (PIECES_IN_THE_ROW - 1) * SHAPE_ROW_SPACING,
    )


@dataclass
class TracyOnItsOwnTable(MontessoriWorldBuilder):
    """
    Builds the board and the pieces on Tracy's own table, with Tracy bolted so that its
    table's legs rest on the floor.
    """

    piece_set: KnownPieceSet = FULL_SIZE_PIECES
    """
    The set of loose pieces the scene is built with.
    """

    _table_top_z: float = field(init=False, default=0.0)
    """
    The height Tracy's table top ended up at in the scene built most recently.
    """

    def build(self, robot_type: Type[AbstractRobot]) -> World:
        """
        Build the scene on Tracy's own table.

        Tracy's root body is its table, so once Tracy is mounted that body is annotated
        as the scene's :class:`~semantic_digital_twin.semantic_annotations.semantic_annotations.Table`,
        which is where the scenarios look the table up.

        :param robot_type: The robot the scenario runs on, as its own binding names it.
        :return: The world holding the scene.
        """
        tracy = parse_tracy()
        mount_position, self._table_top_z = tracy_table_mount_position(
            tracy, x=TRACY_MOUNT_X, y=TRACY_MOUNT_Y
        )
        montessori = TracyMontessoriWorld(
            shapes_are_movable=True,
            table_top_z=self._table_top_z,
            pieces=self.piece_set,
        )
        mounted = montessori.mount_stationary_robot(
            robot_type, tracy, mount_position, 0.0
        )
        with montessori.world.modify_world():
            montessori.world.add_semantic_annotation(
                Table(name=mounted.root.name, root=mounted.root)
            )
        return montessori.world

    @property
    def table_top_z(self) -> float:
        return self._table_top_z


@dataclass
class TracyLookingAtItsOwnTable(PerceivingWorldBuilder):
    """
    The scene as Tracy's own camera finds it: the world the robot publishes, which
    already holds Tracy and its table, with the board and the pieces stood in it by
    looking.

    Every trial looks afresh, and a trial looks again once the person at the table has
    changed the scene, so what the world holds is the table as it stands now.
    """

    scene: PerceivedScene
    """
    The board and the pieces as the camera finds them, in the world the robot publishes.
    """

    def build(self, robot_type: Type[AbstractRobot]) -> World:
        """
        Have the camera stand the board and the pieces in the world the robot publishes,
        and hand that world over.

        :param robot_type: The robot the scenario runs on, which the world has to hold.
        :raises WorldHoldsNoSuchRobot: If the world does not hold exactly one robot of
            that kind.
        :raises NoBoardInView: If the world holds no board and none is in view.
        """
        world = self.scene.world
        if len(world.get_semantic_annotations_by_type(robot_type)) != 1:
            raise WorldHoldsNoSuchRobot(robot_type=robot_type, world=world)
        self.perceive()
        return world

    def perceive(self) -> None:
        self.scene.perceive()

    @property
    def table_top_z(self) -> float:
        return self.scene.table_height

    @property
    def piece_set(self) -> KnownPieceSet:
        return self.scene.piece_set
