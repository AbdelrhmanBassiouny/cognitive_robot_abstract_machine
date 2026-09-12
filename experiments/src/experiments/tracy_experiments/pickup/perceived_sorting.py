"""
Sorting the loose Montessori pieces into the board by looking: the camera finds the
board and the pieces (:class:`~experiments.montessori.perception.scene_publishing.
PerceivedScene`), both are stood in the world the robot plans in, and each piece is
picked from where it was seen and released over the hole of the perceived board it fits
through.

What is done with a piece once it is stood in the world -- Giskard driving the real arm
and the Robotiq gripper, or MuJoCo actuators driving a simulated one -- is a
:class:`ShapeSorter`'s own affair; this module settles what is sorted and where each
piece is let go.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import List

from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from semantic_digital_twin.spatial_types.spatial_types import Pose

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
    One sorting run whose scene comes from the camera: every piece the look stood on the
    table is sorted into the perceived board.
    """

    scene: PerceivedScene
    """
    The board and the pieces, as the camera finds them and the world holds them.
    """

    sorter: ShapeSorter
    """
    What picks each piece up and lets it go.
    """

    hover: float = PLACE_HOVER
    """
    How far above the lid a piece's underside is released.
    """

    @property
    def board(self) -> ShapeSortingBoard:
        """
        The board as the world holds it, once the scene has been perceived.
        """
        return self.scene.board

    @property
    def pieces(self) -> List[MontessoriShape]:
        """
        The pieces the look put on the table, as the world holds them, once the scene
        has been perceived.
        """
        return self.scene.pieces

    def perceive(self) -> None:
        """
        Have the world hold the board and the pieces on the table.

        :raises NoBoardInView: If the world holds no board and none is in view.
        """
        self.scene.perceive()

    def release_pose_for(self, piece: MontessoriShape) -> Pose:
        """
        :param piece: A piece the world holds.
        :return: Where the piece's centre is let go: :attr:`hover` above the lid over
            the centre of the hole of :attr:`board` it fits through, in the world root
            frame.
        :raises NoMatchingHoleError: If the piece fits through none of the board's holes.
        """
        world = self.scene.world
        hole_position = self.board.hole_for(piece).root.global_transform.to_position()
        lid_height = WorkspaceSurface.of(self.board, world.root).height
        return Pose.from_xyz_rpy(
            float(hole_position.x),
            float(hole_position.y),
            lid_height + self.hover + self.half_height_of(piece),
            reference_frame=world.root,
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
