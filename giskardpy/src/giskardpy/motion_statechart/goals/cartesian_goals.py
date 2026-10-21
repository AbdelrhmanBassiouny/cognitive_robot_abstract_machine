from __future__ import annotations

from dataclasses import dataclass, field

from cramph.composites import Parallel
from cramph.node import StatechartNode
from giskardpy.motion_statechart.binding_policy import GoalBindingPolicy
from giskardpy.motion_statechart.graph_node import MotionStatechartNode
from giskardpy.motion_statechart.weights import DefaultWeights
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianOrientation,
    CartesianPositionStraight,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)


@dataclass(eq=False, repr=False, kw_only=True)
class CartesianPoseStraight(Parallel):
    """
    Like CartesianPose, but constrains the tip link to move in a straight line towards
    the goal.

    This goal is the parallel holding both tasks, together with any node it is handed,
    such as a speed cap or a collision allowance accompanying the motion.
    """

    root_link: KinematicStructureEntity
    """
    Name of the root link of the kin chain.
    """

    tip_link: KinematicStructureEntity
    """
    Name of the tip link of the kin chain.
    """

    goal_pose: Pose
    """
    The goal pose.
    """

    translation_threshold: float = 0.01
    """
    If the position error falls below this threshold (in meters), that half of the goal
    is achieved.
    """

    orientation_threshold: float = 0.01
    """
    If the orientation error falls below this threshold (in rad), that half of the goal
    is achieved.
    """

    weight: float = DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE
    """
    Task priority relative to other tasks.
    """

    binding_policy: GoalBindingPolicy = GoalBindingPolicy.Bind_at_build
    """
    Describes when the goal is computed.

    See GoalBindingPolicy for more information.
    """

    nodes: list[StatechartNode] = field(default_factory=list, init=False)
    """
    The position and the orientation task, followed by the nodes this goal was handed.
    """

    def expand(self) -> None:
        """
        Create the position and the orientation task, then adopt them before the nodes
        this goal was handed, as :meth:`~cramph.composites.ControlStructureNode.expand`
        does.
        """
        self.nodes[:0] = self.create_tasks()
        super().expand()

    def create_tasks(self) -> list[MotionStatechartNode]:
        """
        :return: New position and orientation tasks reaching :attr:`goal_pose`, the
            position along a straight line.
        """
        return [
            CartesianPositionStraight(
                name=self.name + "/position",
                root_link=self.root_link,
                tip_link=self.tip_link,
                goal_point=self.goal_pose.position,
                threshold=self.translation_threshold,
                weight=self.weight,
                binding_policy=self.binding_policy,
            ),
            CartesianOrientation(
                name=self.name + "/orientation",
                root_link=self.root_link,
                tip_link=self.tip_link,
                goal_orientation=self.goal_pose.rotation_matrix,
                threshold=self.orientation_threshold,
                weight=self.weight,
                binding_policy=self.binding_policy,
            ),
        ]
