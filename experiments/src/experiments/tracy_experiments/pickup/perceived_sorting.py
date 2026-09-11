"""
Sorting the loose Montessori pieces into the board by looking: the camera finds the
board and the pieces, both are stood in the world the robot plans in, and each piece is
picked from where it was seen and released over the hole of the perceived board it fits
through.

What is done with a piece once it is stood in the world -- Giskard driving the real arm
and the Robotiq gripper, or MuJoCo actuators driving a simulated one -- is a
:class:`ShapeSorter`'s own affair; this module settles what is sorted and where each
piece is let go.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import List

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.perception.scene_publishing import (
    BOARD_SEARCH_PERIOD_SECONDS,
    PiecePublisher,
    hold_board,
)
from experiments.montessori.perception.scene_source import RepeatedLook
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

logger = logging.getLogger(__name__)

PLACE_HOVER = 0.04
"""
Height above the board's lid, in metres, at which a piece's underside is released over
its hole.
"""

# %% what does the sorting


class ShapeSorter(ABC):
    """
    Whatever picks one piece off the table and lets it go somewhere else.
    """

    @abstractmethod
    def sort(self, piece: MontessoriShape, release_pose: Pose) -> None:
        """
        Pick a piece off the table and release it at a pose.

        :param piece: The piece, standing in the world where the look saw it.
        :param release_pose: Where the piece's centre is let go, in the world root
            frame.
        """


# %% the run


@dataclass
class PerceivedSorting:
    """
    One sorting run whose scene comes from the camera.

    The world the robot plans in holds the robot and its table; the board and the pieces
    are stood in it by looking, and every piece stood there is then sorted into the
    board.
    """

    world: World
    """
    The world the robot plans in, and the board and pieces are stood in.
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

    sorter: ShapeSorter
    """
    What picks each piece up and lets it go.
    """

    hover: float = PLACE_HOVER
    """
    How far above the lid a piece's underside is released.
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
    The pieces the look put on the table, as the world holds them, once :meth:`perceive`
    has run.
    """

    def perceive(self) -> None:
        """
        Have the world hold the board and the pieces on the table.

        The board is looked for first, by its description, and stood where it was found
        unless the world already holds one; then the pipeline is handed the board's lid
        and one look stands every piece resting on the bare table.

        :raises NoBoardInView: If the world holds no board and none is in view.
        """
        self.board = hold_board(
            self.world,
            self.look,
            self.described_board,
            looks=self.looks_for_board,
            period=self.board_search_period,
        )
        self.pieces = PiecePublisher(world=self.world).publish(
            self.look.scene(), resting_on=self.look.pipeline.table.name
        )
        logger.info(
            "Sorting into %s: %d piece(s) on the table, %s.",
            self.board.name,
            len(self.pieces),
            ", ".join(self._describe(piece) for piece in self.pieces),
        )

    def release_pose_for(self, piece: MontessoriShape) -> Pose:
        """
        :param piece: A piece the world holds.
        :return: Where the piece's centre is let go: :attr:`hover` above the lid over
            the centre of the hole of :attr:`board` it fits through, in the world root
            frame.
        :raises NoMatchingHoleError: If the piece fits through none of the board's holes.
        """
        hole_position = self.board.hole_for(piece).root.global_transform.to_position()
        lid_height = WorkspaceSurface.of(self.board, self.world.root).height
        return Pose.from_xyz_rpy(
            float(hole_position.x),
            float(hole_position.y),
            lid_height + self.hover + self.half_height_of(piece),
            reference_frame=self.world.root,
        )

    @staticmethod
    def half_height_of(piece: MontessoriShape) -> float:
        """
        :param piece: A piece the world holds.
        :return: How far the piece's centre stands above its underside, in metres.
        """
        bounds = piece.root.collision.combined_mesh.bounds
        return float(bounds[1][2] - bounds[0][2]) / 2

    def sort_every_piece(self) -> None:
        """
        Sort every piece the look put on the table, in the order it reported them.
        """
        for piece in self.pieces:
            self.sorter.sort(piece, self.release_pose_for(piece))

    def _describe(self, piece: MontessoriShape) -> str:
        """
        :param piece: A piece the world holds.
        :return: Its kind and where it stands, for a log line.
        """
        position = piece.root.global_transform.to_position()
        return (
            f"{piece.shape_category} at ({float(position.x):.3f}, "
            f"{float(position.y):.3f})"
        )
