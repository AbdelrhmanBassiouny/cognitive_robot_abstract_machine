"""
Stand the board a look found in the world the robot publishes.

That world is kept in step with every process watching it -- Giskard among them -- by a
:class:`~semantic_digital_twin.adapters.ros.world_synchronizer.WorldSynchronizer`, so a
board stood in it is a board the whole system then holds, and a later fetch of that
world reads the board's lid rather than having to find it again.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.semantics import ShapeSortingBoard
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World

PUBLISHED_BOARD_PREFIX = "perceived"
"""
What a board stood in the published world, and its holes, are named under.
"""


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
        return described.stand_in(
            self.world, self.lid_pose_of(found), PUBLISHED_BOARD_PREFIX
        )

    @staticmethod
    def lid_pose_of(found: ShapeSortingBoard) -> Pose:
        """
        :param found: A board stood from its description, whose root is a solid as tall
            as the board with its origin at the middle.
        :return: Where the lid's centre stands, in the frame the board was stood in.
        """
        up_to_the_lid = HomogeneousTransformationMatrix.from_xyz_rpy(z=found.height / 2)
        return (found.root.global_transform @ up_to_the_lid).to_pose()
