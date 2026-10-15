from __future__ import annotations

from dataclasses import dataclass

from semantic_digital_twin.spatial_types import (
    Vector3,
    RotationMatrix,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.connections import DifferentialDrive
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)
from cramph.node import EndedByOwner, SucceedsOnObservingTrue, FailsOnObservingFalse
from cramph.composites import Sequence, Parallel
from cramph.node import CompositeNode, NodeArtifacts
from krrood.symbolic_math.symbolic_math import (
    Scalar,
    logic_or,
    trinary_if_cases,
)
from giskardpy.motion_statechart.binding_policy import GoalBindingPolicy
from cramph.context import StatechartContext
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.exceptions import UnexpectedWorldEntityCountError
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianOrientation,
    CartesianPositionStraight,
    CartesianPose,
)


@dataclass(eq=False, repr=False, kw_only=True)
class DifferentialDriveBaseGoal(
    SucceedsOnObservingTrue, FailsOnObservingFalse, CompositeNode
):
    """
    Moves the robot to a goal pose using a differential drive, running these steps in
    one :class:`~cramph.composites.Sequence`:

    1. Orient to goal position
    2. Drive to goal position
    3. Orient to goal orientation

    The direction to the goal is an expression over the base's forward kinematics, so
    steps 1 and 2 follow the base as it drives.
    """

    diff_drive_connection: DifferentialDrive | None = None
    """
    Drive connection to use.

    If it is None and there is only one diff drive in the world, it will be used.
    """

    goal_pose: Pose
    """
    Pose to reach.
    """

    weight: float = DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE
    """
    Task priority relative to other tasks.
    """

    threshold: float = 0.01
    """
    Threshold when the drive goals for the base are considered achieved.
    """

    @property
    def sequence(self) -> Sequence:
        """
        The sequence running the three steps.
        """
        return self.nodes[0]

    def expand(self, context: StatechartContext) -> None:
        """
        Add the sequence running the three steps.
        """
        if self.diff_drive_connection is None:
            diff_drives = context.world.get_connections_by_type(DifferentialDrive)
            if len(diff_drives) == 0:
                raise UnexpectedWorldEntityCountError(
                    node=self,
                    expected_count=1,
                    actual_count=0,
                    entity_type=DifferentialDrive,
                )
            if len(diff_drives) > 1:
                raise UnexpectedWorldEntityCountError(
                    node=self,
                    expected_count=1,
                    actual_count=len(diff_drives),
                    entity_type=DifferentialDrive,
                )
            self.diff_drive_connection = diff_drives[0]
        map = context.world.root
        tip = self.diff_drive_connection.child

        root_T_goal = context.world.transform(self.goal_pose, map)
        root_T_current = context.world.compose_forward_kinematics_expression(map, tip)
        root_V_current_to_goal = root_T_goal.position - root_T_current.position
        root_V_current_to_goal.scale(1)
        root_V_z = Vector3.Z(reference_frame=map)
        root_R_first_orientation = RotationMatrix.from_vectors(
            x=root_V_current_to_goal, z=root_V_z, reference_frame=map
        )

        root_T_goal2 = Pose(
            position=root_T_goal.position,
            orientation=root_R_first_orientation.quaternion,
            reference_frame=map,
        )

        steps = [
            CartesianOrientation(
                name=f"{self.name}/step1",
                root_link=map,
                tip_link=tip,
                goal_orientation=root_R_first_orientation,
                weight=self.weight,
                threshold=self.threshold,
            ),
            CartesianPose(
                name=f"{self.name}/step2",
                root_link=map,
                tip_link=tip,
                goal_pose=root_T_goal2,
                weight=self.weight,
                translation_threshold=self.threshold,
                orientation_threshold=self.threshold,
            ),
            CartesianPose(
                name=f"{self.name}/step3",
                root_link=map,
                tip_link=tip,
                goal_pose=root_T_goal,
                weight=self.weight,
                translation_threshold=self.threshold,
                orientation_threshold=self.threshold,
            ),
        ]
        self._add_child_to_statechart(
            Sequence(name=f"{self.name}/sequence", nodes=steps)
        )

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report the outcome of the sequence.
        """
        return NodeArtifacts(
            observation=trinary_if_cases(
                cases=[
                    (self.sequence.is_succeeded, Scalar.const_true()),
                    (self.sequence.is_failed_or_interrupted, Scalar.const_false()),
                ],
                else_result=Scalar.const_trinary_unknown(),
            )
        )


@dataclass(eq=False, repr=False, kw_only=True)
class CartesianPoseStraight(EndedByOwner, CompositeNode):
    """
    Like CartesianPose, but constrains the tip link to move in a straight line towards
    the goal.

    Both tasks run in one :class:`~cramph.composites.Parallel`, and this goal observes
    what that parallel observes.
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

    @property
    def parallel(self) -> Parallel:
        """
        The parallel running the position and the orientation task.
        """
        return self.nodes[0]

    def expand(self, context: StatechartContext) -> None:
        """
        Add the parallel running the position and the orientation task.
        """
        tasks = [
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
        self._add_child_to_statechart(
            Parallel(name=f"{self.name}/parallel", nodes=tasks)
        )

    @property
    def inherent_fail_condition(self) -> Scalar:
        """
        Fails as well once the parallel can no longer arrive, see
        :meth:`~cramph.node.StatechartNode.inherent_fail_condition`.
        """
        return logic_or(
            super().inherent_fail_condition, self.parallel.is_failed_or_interrupted
        )

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Observe what the parallel observes.
        """
        return NodeArtifacts(observation=self.parallel.observation_variable)
