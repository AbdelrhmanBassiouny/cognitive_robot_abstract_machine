"""
A piece let go over its hole falls into it.

The twin is moved by the robot alone and has no physics, so a piece released over a hole
would stay where the hand let go of it. This step lets it fall the rest of the way, in a
few small steps so that it is seen to fall.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from coraplex.plans.executables import Executable
from coraplex.plans.plan_node import ExecutionBoundaryNode
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world_description.world_entity import Body

from experiments.eql_showcase.perceived_twin import PerceivedTwin, SeenHole, SeenPiece

# %% the fall


@dataclass
class FallIntoHolesExecutable(Executable):
    """
    Lets every piece that hangs over a hole fall into it, in small steps.
    """

    twin: PerceivedTwin = field(kw_only=True)
    """
    The twin holding the pieces and the holes.
    """

    sunk_below_lid: float = field(default=0.006, kw_only=True)
    """
    How far below the lid a fallen piece's top comes to rest, in metres.
    """

    steps: int = field(default=12, kw_only=True)
    """
    How many steps a fall is shown in.
    """

    seconds: float = field(default=0.45, kw_only=True)
    """
    How long a fall takes.
    """

    def execute(self) -> None:
        for piece in self.twin.world.get_semantic_annotations_by_type(SeenPiece):
            hole = self.hole_under(piece.root)
            if hole is not None:
                self.fall(piece.root, hole)

    def hole_under(self, body: Body) -> SeenHole | None:
        """
        :param body: A piece.
        :return: The hole the piece hangs over above the lid, or None.
        """
        position = body.global_pose.position.to_np()[:3]
        for hole in self.twin.holes:
            [area] = hole.region.area.shapes
            offset = hole.region.global_transform.inverse().to_np() @ np.append(
                position, 1.0
            )
            if (
                abs(offset[0]) <= area.scale.x / 2
                and abs(offset[1]) <= area.scale.y / 2
                and position[2] > hole.lid_height
            ):
                return hole
        return None

    def fall(self, body: Body, hole: SeenHole) -> None:
        """
        Lower a piece into a hole, falling from rest.

        :param body: The piece.
        :param hole: The hole it falls into.
        """
        [box] = body.collision.shapes
        resting_height = hole.lid_height - box.scale.z / 2 - self.sunk_below_lid
        connection = body.parent_connection
        start = connection.origin.to_np()
        drop = start[2, 3] - resting_height
        for step in range(1, self.steps + 1):
            # falling from rest, the distance covered grows with the square of the time
            fallen = start.copy()
            fallen[2, 3] = start[2, 3] - drop * (step / self.steps) ** 2
            connection.origin = HomogeneousTransformationMatrix(
                fallen, reference_frame=connection.parent
            )
            time.sleep(self.seconds / self.steps)


@dataclass(eq=False, repr=False)
class FallIntoHolesNode(ExecutionBoundaryNode):
    """
    Lets every piece released over a hole fall into it.
    """

    twin: PerceivedTwin = field(kw_only=True)
    """
    The twin holding the pieces and the holes.
    """

    def notify(self) -> None:
        pass

    def parse(self) -> FallIntoHolesExecutable:
        return FallIntoHolesExecutable(context=self.context, twin=self.twin)

    def __repr__(self) -> str:
        return "Fall into hole"
