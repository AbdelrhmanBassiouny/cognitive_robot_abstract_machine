from __future__ import annotations

from dataclasses import dataclass, field

from cramph.composites import Sequence, Parallel
from cramph.context import StatechartContext
from cramph.node import (
    CompositeNode,
    NodeArtifacts,
    StatechartNode,
    expanded_child_field,
)
from cramph.node import SucceedsOnObservingTrue, FailsOnObservingFalse
from giskardpy.motion_statechart.binding_policy import (
    ForwardKinematicsBinding,
    GoalBindingPolicy,
)
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.exceptions import UnexpectedWorldEntityCountError
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianOrientation,
    CartesianPositionStraight,
)
from giskardpy.motion_statechart.tasks.drive_tasks import (
    BaseHeading,
    BaseOrientation,
    BasePosition,
    BaseTurnTowardsGoalPosition,
)
from krrood.symbolic_math.symbolic_math import (
    Scalar,
    trinary_if_cases,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.connections import DifferentialDrive
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)


@dataclass(eq=False, repr=False, kw_only=True)
class DifferentialDriveBaseGoal(
    SucceedsOnObservingTrue, FailsOnObservingFalse, CompositeNode
):
    """
    Moves the robot to a goal pose using a differential drive, running these steps in
    one :class:`~cramph.composites.Sequence`:

    1. Turn towards the goal position, without driving
    2. Drive to goal position, steering towards it
    3. Orient to goal orientation

    Every step moves the base relative to the drive's parent, as it is whenever the
    steps are built, so the goal follows a base moved under another parent while the
    statechart runs. Where the goal lies is read from its reference frame as
    :attr:`binding_policy` says.
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

    binding_policy: GoalBindingPolicy = GoalBindingPolicy.Bind_on_start
    """
    When the pose of the reference frame of :attr:`goal_pose` is read.
    """

    parent_T_goal_reference_frame: HomogeneousTransformationMatrix = (
        expanded_child_field()
    )
    """
    The pose of the reference frame of :attr:`goal_pose` relative to the drive's parent,
    as :attr:`binding_policy` fixes it; the steps are expressed over it.
    """

    _forward_kinematics_binding: ForwardKinematicsBinding = field(
        init=False, repr=False
    )
    """
    Fixes :attr:`parent_T_goal_reference_frame` to the current pose of the frame.
    """

    @property
    def sequence(self) -> Sequence:
        """
        The sequence running the three steps.
        """
        return self.nodes[0]

    @property
    def _goal_reference_frame_name(self) -> PrefixedName:
        """
        :return: The name the variables of :attr:`parent_T_goal_reference_frame` are
            created under.
        """
        return PrefixedName("parent_T_goal_ref", str(self.name))

    @property
    def _drive_parent(self) -> KinematicStructureEntity:
        """
        :return: The body the drive is attached to now.
        """
        # moving the base under another parent replaces its connection, so the parent
        # is read from the base rather than from the connection
        return self.diff_drive_connection.child.parent_kinematic_structure_entity

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
        self.parent_T_goal_reference_frame = (
            HomogeneousTransformationMatrix.create_with_variables(
                str(self._goal_reference_frame_name)
            )
        )
        task_parameters = dict(
            base=self.diff_drive_connection.child,
            goal_pose=self.goal_pose,
            parent_T_goal_reference_frame=self.parent_T_goal_reference_frame,
            weight=self.weight,
            threshold=self.threshold,
        )
        steps = [
            BaseTurnTowardsGoalPosition(name=f"{self.name}/step1", **task_parameters),
            Parallel(
                name=f"{self.name}/step2",
                nodes=[
                    BasePosition(name=f"{self.name}/step2/position", **task_parameters),
                    BaseHeading(name=f"{self.name}/step2/heading", **task_parameters),
                ],
            ),
            Parallel(
                name=f"{self.name}/step3",
                nodes=[
                    BasePosition(name=f"{self.name}/step3/position", **task_parameters),
                    BaseOrientation(
                        name=f"{self.name}/step3/orientation", **task_parameters
                    ),
                ],
            ),
        ]
        self._add_child_to_statechart(
            Sequence(name=f"{self.name}/sequence", nodes=steps)
        )

    def set_up(self, context: StatechartContext) -> None:
        """
        Bind :attr:`parent_T_goal_reference_frame`, which the steps are expressed over.
        """
        super().set_up(context)
        self._forward_kinematics_binding = ForwardKinematicsBinding(
            name=self._goal_reference_frame_name,
            root=self._drive_parent,
            tip=self.goal_pose.reference_frame,
            float_variable_data=context.float_variable_data,
            root_T_tip=self.parent_T_goal_reference_frame,
        )
        self._forward_kinematics_binding.bind(context.world)

    def on_start(self, context: StatechartContext) -> None:
        if self.binding_policy == GoalBindingPolicy.Bind_on_start:
            self._forward_kinematics_binding.bind(context.world)

    def build_artifacts(self, context: StatechartContext) -> NodeArtifacts:
        """
        Report the outcome of the sequence, and express
        :attr:`parent_T_goal_reference_frame` relative to the drive's new parent if the
        drive was moved under another parent, since the steps are rebuilt against it.

        Where the goal's reference frame was bound is kept.
        """
        if self._forward_kinematics_binding.root is not self._drive_parent:
            self._forward_kinematics_binding.change_root(
                self._drive_parent, context.world
            )
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

    def expand(self, context: StatechartContext) -> None:
        """
        Create the position and the orientation task, then adopt them before the nodes
        this goal was handed, as :meth:`~cramph.composites.CramLanguageNode.expand`
        does.
        """
        self.nodes[:0] = [
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
        super().expand(context)
