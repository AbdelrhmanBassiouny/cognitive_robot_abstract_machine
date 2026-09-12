"""
Stand what a look found in the world the robot publishes: the board, and the loose
pieces on the table.

That world is kept in step with every process watching it -- Giskard among them -- by a
:class:`~semantic_digital_twin.adapters.ros.world_synchronizer.WorldSynchronizer`, so a
board stood in it is a board the whole system then holds, and a later fetch of that
world reads the board's lid rather than having to find it again. A piece stood in it is
what a plan picks up: the plan reaches for the body, and the body stands where the look
saw the piece.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace

from typing_extensions import List, Optional

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.detections import (
    DetectedMontessoriShape,
    MontessoriScene,
)
from experiments.montessori.perception.exceptions import NoBoardInView
from experiments.montessori.perception.imagination import piece_mesh
from experiments.montessori.perception.scene_source import (
    MontessoriSceneSource,
    RepeatedLook,
)
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.pieces import KnownPieceSet
from experiments.montessori.semantics import (
    MONTESSORI_SHAPE_CLASSES,
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

PUBLISHED_PREFIX = "perceived"
"""
What a board stood in the published world, its holes, and the pieces stood there are
named under.
"""

BOARD_SEARCH_PERIOD_SECONDS = 1.0
"""
How long is waited before looking for the described board again, while no board
answering the description is in view.
"""

LOOKS_FOR_THE_BOARD = 30
"""
How many looks a camera watching the table is given to show the board before a run gives
up on finding it.
"""

# %% the board


def look_for_board(
    look: MontessoriSceneSource, described: DescribedBoard
) -> Optional[ShapeSortingBoard]:
    """
    Take one look for a board answering a description.

    :param look: The source to look through.
    :param described: The board to look for.
    :return: The board, standing where it was found in the world the look brought its
        findings into, or None where no board answering the description is in view.
    """
    found = list(
        described.statement().evaluate(backend=MontessoriPerceptionBackend(source=look))
    )
    return found[0] if found else None


def hold_board(
    world: World,
    look: RepeatedLook,
    described: DescribedBoard,
    looks: int = 1,
    period: float = BOARD_SEARCH_PERIOD_SECONDS,
) -> ShapeSortingBoard:
    """
    Have the world the robot publishes hold the shape-sorting board on this table where
    a look finds it now, and the look read that board's lid from then on.

    The board is looked for by its description. A world holding no board has the board
    found stood in it; a world already holding one has that board moved to where it is
    found now, or kept where it was if no look shows it. The look's pipeline is then
    handed one reading the lid of the board the world holds.

    :param world: The world the robot publishes.
    :param look: The source to look through, which is handed the pipeline reading the
        lid.
    :param described: The board on this table, as a look is asked for it.
    :param looks: How many looks are taken for the board before giving up -- one for a
        look that shows the whole scene at once, more for a camera whose first frames
        may not show the board yet.
    :param period: Seconds between two looks for the board.
    :return: The board the world holds.
    :raises NoBoardInView: If the world holds no board and none is in view.
    """
    board = ShapeSortingBoard.held_by(world)
    publisher = BoardPublisher(world=world)
    for look_taken in range(looks):
        found = look_for_board(look, described)
        if found is not None:
            board = publisher.publish(described, found)
            logger.info("Found the board and published it as %s.", board.name)
            break
        logger.info("No board answering the description is in view yet.")
        if look_taken + 1 < looks:
            time.sleep(period)
    if board is None:
        raise NoBoardInView(looks=looks)
    look.read_with(
        replace(
            look.pipeline,
            lid=WorkspaceSurface.of(board, look.pipeline.reference_frame),
        )
    )
    return board


@dataclass
class BoardPublisher:
    """
    Stands the board a look found in the world the robot publishes, or, where that world
    already holds one, moves it to where the look found it now.
    """

    world: World
    """
    The world the robot publishes.
    """

    def publish(
        self, described: DescribedBoard, found: ShapeSortingBoard
    ) -> ShapeSortingBoard:
        """
        :param described: The board the look was asked for.
        :param found: That board, as the look stood it where it was found.
        :return: The board the published world holds: the one it already held, now
            standing where the look found it, or the found one newly stood there.
        """
        lid_pose = self.lid_pose_of(found)
        held = ShapeSortingBoard.held_by(self.world)
        if held is None:
            return described.stand_in(self.world, lid_pose, PUBLISHED_PREFIX)
        described.move_in(self.world, held, lid_pose)
        return held

    @staticmethod
    def lid_pose_of(found: ShapeSortingBoard) -> Pose:
        """
        :param found: A board stood from its description, whose root is a solid as tall
            as the board with its origin at the middle.
        :return: Where the lid's centre stands, in the frame the board was stood in.
        """
        up_to_the_lid = HomogeneousTransformationMatrix.from_xyz_rpy(z=found.height / 2)
        return (found.root.global_transform @ up_to_the_lid).to_pose()


# %% the pieces


@dataclass
class PiecePublisher:
    """
    Stands the loose pieces a look found in the world the robot publishes, each where it
    was seen.

    A piece is stood as the body the set says it is -- the known piece's own outline
    standing as tall as it does -- fixed to the world root where the look reported it on
    the surface, turned as the look reported it, and resting on that surface. The look's
    own reading of how tall the piece stands is not used: a depth image that barely
    resolves a piece reads it far shorter than it is, and a body stood on that reading
    would sink into the table.

    A piece taken down before a look and found again by it is stood as the body it
    already was, so whatever kept it -- a monitor watching it, a question about it --
    keeps the piece the new look found.
    """

    world: World
    """
    The world the robot publishes.
    """

    published: List[MontessoriShape] = field(init=False, default_factory=list)
    """
    Every piece this publisher has stood and not taken down again, in the order they
    were stood.
    """

    taken_down: List[MontessoriShape] = field(init=False, default_factory=list)
    """
    The pieces taken down since the last look, each waiting to be stood again if that
    look finds a piece of its kind.
    """

    stood: int = field(init=False, default=0)
    """
    How many pieces have ever been stood anew, which is what gives each its own name.
    """

    def publish(
        self, scene: MontessoriScene, resting_on: PrefixedName
    ) -> List[MontessoriShape]:
        """
        Stand every piece one look put on one surface; a piece taken down and not found
        again is gone for good.

        :param scene: What the look found.
        :param resting_on: What the look calls the surface a piece must rest on to be
            stood; a piece on any other surface is left out.
        :return: The pieces stood, in the order the look reported them.
        """
        stood = [
            self.publish_piece(shape)
            for shape in scene.shapes
            if shape.supporting_surface == resting_on
        ]
        self.taken_down = []
        return stood

    def take_down(self) -> None:
        """
        Take every piece a look stood out of the world again, so a fresh look can stand
        the pieces as it finds them.

        Every piece stood by a look, not only this publisher's own: the world fetched
        from the robot still holds what earlier runs stood in it, and each of them is
        waiting to be stood again as the piece it was.
        """
        stood_by_a_look = self.stood_by_a_look()
        with self.world.modify_world():
            for piece in stood_by_a_look:
                self.world.remove_semantic_annotation(piece)
                self.world.remove_kinematic_structure_entity(piece.root)
        self.taken_down = stood_by_a_look
        self.published = []

    def stood_by_a_look(self) -> List[MontessoriShape]:
        """
        Every piece the world holds that a look stood, this run's or an earlier one's.
        """
        return [
            piece
            for piece in self.world.get_semantic_annotations_by_type(MontessoriShape)
            if piece.name.prefix == PUBLISHED_PREFIX
        ]

    def publish_piece(self, shape: DetectedMontessoriShape) -> MontessoriShape:
        """
        Stand one piece where a look saw it: the piece of its kind taken down before the
        look, if there is one, or a new one.

        :param shape: The piece as the look found it.
        :return: The piece as the published world now holds it.
        """
        piece = self._taken_down_piece_of(shape.category)
        if piece is None:
            piece = self._new_piece(shape)
        known = shape.hypothesis.piece_of(shape.category)
        seen_at = self.world.transform(shape.pose, self.world.root).to_position()
        with self.world.modify_world():
            self.world.add_connection(
                FixedConnection(
                    parent=self.world.root,
                    child=piece.root,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=float(seen_at.x),
                        y=float(seen_at.y),
                        z=shape.surface_height + known.height / 2,
                        yaw=shape.yaw,
                        reference_frame=self.world.root,
                    ),
                )
            )
            self.world.add_semantic_annotation(piece)
        self.published.append(piece)
        return piece

    def _taken_down_piece_of(
        self, category: MontessoriShapeCategory
    ) -> Optional[MontessoriShape]:
        """
        The piece of a kind taken down before the look, taken out of the waiting ones.

        :param category: The kind of piece.
        :return: The piece, or None where none of that kind is waiting.
        """
        for piece in self.taken_down:
            if piece.shape_category is category:
                self.taken_down.remove(piece)
                return piece
        return None

    def _new_piece(self, shape: DetectedMontessoriShape) -> MontessoriShape:
        """
        A piece never stood before, under a name of its own.

        :param shape: The piece as the look found it.
        """
        name = PrefixedName(f"{shape.category}_{self.stood}", PUBLISHED_PREFIX)
        self.stood += 1
        known = shape.hypothesis.piece_of(shape.category)
        body = Body.from_shape_collection(name, ShapeCollection([piece_mesh(known)]))
        return MONTESSORI_SHAPE_CLASSES[shape.category](name=name, root=body)


# %% the scene a look stands


@dataclass
class PerceivedScene:
    """
    The Montessori scene as the camera finds it, stood in the world the robot publishes.

    That world holds the robot and its table; the board and the loose pieces are stood
    in it by looking. Every look stands them where the camera finds them now, so a scene
    perceived again after the table was changed holds the same board and the same pieces
    where they stand now.
    """

    world: World
    """
    The world the robot publishes, and the board and pieces are stood in.
    """

    look: RepeatedLook
    """
    The camera, as something a look is taken through.

    Its pipeline is handed one reading the board's lid once the world holds the board.
    """

    described_board: DescribedBoard
    """
    The board on this table, as a look is asked for it.
    """

    looks_for_board: int = 1
    """
    How many looks are taken for the board before giving up, one every
    :attr:`board_search_period` seconds.

    One for a look that shows the whole scene at once; more for a camera whose first
    frames may not show the board yet.
    """

    board_search_period: float = BOARD_SEARCH_PERIOD_SECONDS
    """
    Seconds between two looks for the board.
    """

    board: ShapeSortingBoard = field(init=False)
    """
    The board as the world holds it, once :meth:`perceive` has run.
    """

    pieces: List[MontessoriShape] = field(init=False, default_factory=list)
    """
    The pieces the last look put on the table, as the world holds them.
    """

    _publisher: PiecePublisher = field(init=False)
    """
    What stands the pieces, and takes them down again before the next look.
    """

    def __post_init__(self) -> None:
        self._publisher = PiecePublisher(world=self.world)

    @property
    def piece_set(self) -> KnownPieceSet:
        """
        The set of loose pieces the look is told stands on the table.
        """
        return self.look.pipeline.pieces

    @property
    def table_height(self) -> float:
        """
        How high the surface the pieces rest on stands, in the world root frame.
        """
        return self.look.pipeline.table.height

    def perceive(self) -> None:
        """
        Have the world hold the board and the pieces on the table as the camera finds
        them now.

        The pieces an earlier look stood are taken down first, so the look is not told
        to expect them where they stood; the board is then looked for by its description
        and stood, or moved to, where it is found; and once the pipeline is handed the
        board's lid, one look stands every piece resting on the bare table -- each piece
        found again as the body it already was.

        :raises NoBoardInView: If the world holds no board and none is in view.
        """
        self._publisher.take_down()
        self.board = hold_board(
            self.world,
            self.look,
            self.described_board,
            looks=self.looks_for_board,
            period=self.board_search_period,
        )
        self.pieces = self._publisher.publish(
            self.look.scene(), resting_on=self.look.pipeline.table.name
        )
        logger.info(
            "Perceived %s and %d piece(s) on the table: %s.",
            self.board.name,
            len(self.pieces),
            ", ".join(self.describe(piece) for piece in self.pieces),
        )

    @staticmethod
    def describe(piece: MontessoriShape) -> str:
        """
        :param piece: A piece the world holds.
        :return: Its kind and where it stands, for a log line.
        """
        position = piece.root.global_transform.to_position()
        return (
            f"{piece.shape_category} at ({float(position.x):.3f}, "
            f"{float(position.y):.3f})"
        )
