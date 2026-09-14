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
from experiments.montessori.semantics import (
    MontessoriShape,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

PLACE_HOVER = 0.04
"""
Height above the board's lid, in metres, at which a piece's underside is released over
its hole.
"""

# %% where a piece is let go


@dataclass(frozen=True)
class Insertion:
    """
    Where a piece is let go of so that it goes through the hole it belongs in.
    """

    hole: ShapeSortingHole
    """
    The hole the piece goes through.
    """

    hover_height: float
    """
    How far above :attr:`hole`'s own origin, along its own axis, the piece's centre is
    let go of.
    """

    def release_pose(self, world: World) -> Pose:
        """
        :param world: The world holding the hole.
        :return: Where the piece's centre is let go, in the world root frame.
        """
        return world.transform(
            Pose.from_xyz_rpy(
                0.0, 0.0, self.hover_height, reference_frame=self.hole.root
            ),
            world.root,
        )


# %% what does the sorting


class ShapeSorter(ABC):
    """
    Whatever picks one piece off the table and lets it go somewhere else.
    """

    @abstractmethod
    def sort(self, piece: MontessoriShape, insertion: Insertion) -> None:
        """
        Pick a piece off the table and let it go through a hole.

        :param piece: The piece, standing in the world where the look saw it.
        :param insertion: The hole it goes through and how far above it it is let go.
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

    def insertion_for(self, piece: MontessoriShape) -> Insertion:
        """
        :param piece: A piece the world holds.
        :return: The hole it goes through and how far above that hole's own origin
            :meth:`release_pose_for` lets it go, so the two say the same thing whichever
            frame a sorter works in.
        :raises NoMatchingHoleError: If the piece fits through none of the board's holes.
        """
        hole = self.board.hole_for(piece)
        released_at = self.release_pose_for(piece).to_position()
        hole_at = hole.root.global_transform.to_position()
        return Insertion(
            hole=hole, hover_height=float(released_at.z) - float(hole_at.z)
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
            self.sorter.sort(piece, self.insertion_for(piece))
