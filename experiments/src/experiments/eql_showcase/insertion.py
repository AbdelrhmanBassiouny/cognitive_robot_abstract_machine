"""
A piece is put into a hole: the hand lowers it over the hole and lets go, and the piece
falls in.

The twin is moved by the robot alone and has no physics, so a piece let go over a hole
would stay where the hand let go of it. The fall is played in a few small steps the
moment the hand opens, so that it is seen to fall.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from typing_extensions import List

from coraplex.plans.executables import Executable, GiskardExecutable
from coraplex.plans.plan_node import ExecutionBoundaryNode, PlanNode
from coraplex.robot_plans.actions.core.placing import PlaceAction
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix

from experiments.eql_showcase.perceived_twin import SeenHole, SeenPiece

# %% the fall


@dataclass
class FallIntoHoleExecutable(Executable):
    """
    Lets a piece hanging over a hole fall into it, in small steps.
    """

    piece: SeenPiece = field(kw_only=True)
    """
    The piece that falls.
    """

    hole: SeenHole = field(kw_only=True)
    """
    The hole it falls into.
    """

    sunk_below_lid: float = field(default=0.006, kw_only=True)
    """
    How far below the lid a fallen piece's top comes to rest, in metres.
    """

    steps: int = field(default=10, kw_only=True)
    """
    How many steps a fall is shown in.
    """

    seconds: float = field(default=0.3, kw_only=True)
    """
    How long a fall takes.
    """

    @property
    def real_time_factor(self) -> float:
        """
        :return: How much faster than the clock the fall plays, as fast as the motions
            around it.
        """
        return GiskardExecutable.real_time_factor or 1.0

    def execute(self) -> None:
        body = self.piece.root
        [box] = body.collision.shapes
        resting_height = self.hole.lid_height - box.scale.z / 2 - self.sunk_below_lid
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
            time.sleep(self.seconds / self.steps / self.real_time_factor)


@dataclass(eq=False, repr=False)
class FallIntoHoleNode(ExecutionBoundaryNode):
    """
    Lets a piece let go over a hole fall into it.
    """

    piece: SeenPiece = field(kw_only=True)
    """
    The piece that falls.
    """

    hole: SeenHole = field(kw_only=True)
    """
    The hole it falls into.
    """

    def notify(self) -> None:
        pass

    def parse(self) -> FallIntoHoleExecutable:
        return FallIntoHoleExecutable(
            context=self.context, piece=self.piece, hole=self.hole
        )

    def __repr__(self) -> str:
        return "Fall into hole"


# %% putting a piece into a hole


@dataclass
class InsertAction(PlaceAction):
    """
    Puts a held piece into a hole: lowers it just over the hole, lets go, and the piece
    falls in before the hand withdraws.
    """

    hole: SeenHole = field(kw_only=True)
    """
    The hole the piece goes into.
    """

    def _after_release(self) -> List[PlanNode]:
        """
        The piece falls into :attr:`hole`.
        """
        return [FallIntoHoleNode(piece=self.object_designator, hole=self.hole)]
