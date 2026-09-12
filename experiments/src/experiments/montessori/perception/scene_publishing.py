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
from experiments.montessori.semantics import (
    MONTESSORI_SHAPE_CLASSES,
    MontessoriShape,
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
    Have the world the robot publishes hold the shape-sorting board on this table, and
    the look read that board's lid from then on.

    A world holding no board has the board looked for by its description, and the board
    found stood in the world where it was found; the look's pipeline is then handed one
    reading the lid of the board the world holds, whichever way it came to hold it.

    :param world: The world the robot publishes.
    :param look: The source to look through, whose pipeline is replaced.
    :param described: The board on this table, as a look is asked for it.
    :param looks: How many looks are taken for the board before giving up -- one for a
        look that shows the whole scene at once, more for a camera whose first frames
        may not show the board yet.
    :param period: Seconds between two looks for the board.
    :return: The board the world holds.
    :raises NoBoardInView: If the world holds no board and none is in view.
    """
    board = ShapeSortingBoard.held_by(world)
    for look_taken in range(looks if board is None else 0):
        found = look_for_board(look, described)
        if found is not None:
            board = BoardPublisher(world=world).publish(described, found)
            logger.info("Found the board and published it as %s.", board.name)
            break
        logger.info("No board answering the description is in view yet.")
        if look_taken + 1 < looks:
            time.sleep(period)
    if board is None:
        raise NoBoardInView(looks=looks)
    look.pipeline = replace(
        look.pipeline, lid=WorkspaceSurface.of(board, look.pipeline.reference_frame)
    )
    return board


@dataclass
class BoardPublisher:
    """
    Stands the board a look found in the world the robot publishes, unless that world
    already holds one.
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
        :return: The board the published world holds: the one it already held, or the
            found one newly stood there.
        """
        held = ShapeSortingBoard.held_by(self.world)
        if held is not None:
            return held
        return described.stand_in(self.world, self.lid_pose_of(found), PUBLISHED_PREFIX)

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
    """

    world: World
    """
    The world the robot publishes.
    """

    published: int = field(init=False, default=0)
    """
    How many pieces have been stood, which is what gives each its own name.
    """

    def publish(
        self, scene: MontessoriScene, resting_on: PrefixedName
    ) -> List[MontessoriShape]:
        """
        Stand every piece one look put on one surface.

        :param scene: What the look found.
        :param resting_on: What the look calls the surface a piece must rest on to be
            stood; a piece on any other surface is left out.
        :return: The pieces stood, in the order the look reported them.
        """
        return [
            self.publish_piece(shape)
            for shape in scene.shapes
            if shape.supporting_surface == resting_on
        ]

    def publish_piece(self, shape: DetectedMontessoriShape) -> MontessoriShape:
        """
        Stand one piece where a look saw it.

        :param shape: The piece as the look found it.
        :return: The piece as the published world now holds it.
        """
        name = PrefixedName(f"{shape.category}_{self.published}", PUBLISHED_PREFIX)
        self.published += 1
        known = shape.hypothesis.piece_of(shape.category)
        body = Body.from_shape_collection(name, ShapeCollection([piece_mesh(known)]))
        seen_at = self.world.transform(shape.pose, self.world.root).to_position()
        with self.world.modify_world():
            self.world.add_connection(
                FixedConnection(
                    parent=self.world.root,
                    child=body,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=float(seen_at.x),
                        y=float(seen_at.y),
                        z=shape.surface_height + known.height / 2,
                        yaw=shape.yaw,
                        reference_frame=self.world.root,
                    ),
                )
            )
            piece = MONTESSORI_SHAPE_CLASSES[shape.category](name=name, root=body)
            self.world.add_semantic_annotation(piece)
        return piece
