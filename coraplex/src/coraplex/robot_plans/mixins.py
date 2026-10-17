from abc import ABC
from dataclasses import dataclass, field

import numpy as np

from coraplex.plans.context_extensions import MotionToleranceConfig
from coraplex.robot_plans.actions.base import Action
from cramph.context import ContextExtension
from cramph.node import StatechartNode
from cramph.world_modification_nodes import MoveBranch
from krrood.ormatic.utils import classproperty
from cramph.composites import Parallel
from giskardpy.motion_statechart.binding_policy import GoalBindingPolicy
from giskardpy.motion_statechart.goals.cartesian_goals import CartesianPoseStraight
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.graph_node import MotionStatechartNode
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    CartesianPosition,
    CartesianPositionStraight,
    CartesianPositionVelocityLimit,
    CartesianRotationVelocityLimit,
)
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import Arm, EndEffector
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)
from typing_extensions import List, Optional

from coraplex.datastructures.enums import MovementType


@dataclass(kw_only=True)
class HasMaxJointVelocity:
    """
    Adds an optional joint velocity cap to an action or motion.
    """

    max_joint_velocity: Optional[float] = None
    """
    Maximum joint velocity (in rad/s or m/s, per joint), enforced via
    :class:`~giskardpy.motion_statechart.tasks.joint_tasks.JointVelocityLimit`. ``None``
    leaves the speed unconstrained.
    """


@dataclass(kw_only=True)
class HasApproachVelocity:
    """
    Adds an optional pre-approach speed to an action that reaches towards a target
    before its main motion.

    Shared by :class:`~coraplex.robot_plans.actions.core.pick_up.ReachAction` and
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`, since a pick-up's
    reach is itself a :class:`ReachAction` and forwards this same value to it.
    """

    pre_approach_linear_velocity: Optional[float] = None
    """
    Maximum linear speed (in m/s) for the initial pre-pose approach, enforced via
    :class:`~giskardpy.motion_statechart.tasks.cartesian_tasks.CartesianPositionVelocityLimit`.
    ``None`` leaves the speed unconstrained.
    """


@dataclass(kw_only=True)
class HasGraspDetectionThreshold:
    """
    Adds a grasp-detection sensitivity threshold to an action that checks whether an
    object is held between the gripper's fingers.

    Shared by :class:`~coraplex.robot_plans.actions.core.pick_up.ReachAction`,
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction` and
    :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`.
    """

    grasp_detection_threshold: float = 0.9
    """
    Minimum fraction of sampled rays between the gripper's fingers that must hit the
    target object for it to count as grasped/held (see
    :func:`~semantic_digital_twin.reasoning.robot_predicates.is_body_gripped`).
    """


@dataclass(kw_only=True)
class ReachTuningParameters(HasApproachVelocity):
    """
    Tunable approach speeds for :class:`~coraplex.robot_plans.actions.core.pick_up.ReachAction`.
    """

    final_approach_linear_velocity: Optional[float] = None
    """
    Maximum linear speed (in m/s) for the final approach onto the target pose, enforced
    via
    :class:`~giskardpy.motion_statechart.tasks.cartesian_tasks.CartesianPositionVelocityLimit`.
    ``None`` leaves the speed unconstrained.
    """


@dataclass(kw_only=True)
class PickUpTuningParameters(ReachTuningParameters):
    """
    Tunable grasp speeds and target-object friction for
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`.

    Extends :class:`ReachTuningParameters` rather than just :class:`HasApproachVelocity`:
    :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction` forwards both
    ``pre_approach_linear_velocity`` and ``final_approach_linear_velocity`` verbatim to
    the internal :class:`~coraplex.robot_plans.actions.core.pick_up.ReachAction` it
    builds, so both fields are literally the same value under the same name in both
    places rather than two similarly-named-but-distinct fields.
    """

    grasp_closing_velocity: Optional[float] = None
    """
    Maximum finger joint velocity (in m/s) used while closing onto the object, enforced
    via
    :class:`~giskardpy.motion_statechart.tasks.joint_tasks.JointVelocityLimit`. ``None``
    leaves the speed unconstrained.
    """

    lift_linear_velocity: Optional[float] = None
    """
    Maximum linear speed (in m/s) for lifting the object clear of the table after
    grasping, enforced via
    :class:`~giskardpy.motion_statechart.tasks.cartesian_tasks.CartesianPositionVelocityLimit`.
    ``None`` leaves the speed unconstrained.
    """

    grasp_stall_minimum_time: Optional[float] = None
    """
    Minimum stall dwell time (in seconds, see
    :attr:`~giskardpy.motion_statechart.goals.gripper.MoveGripper.stall_minimum_time`)
    for the CLOSE motion. ``None`` keeps the default.
    """

    object_friction: Optional[float] = None
    """
    Sliding friction coefficient to apply to the target object's geom before this pick,
    overriding the world's default. Not consumed by this action itself -- applying it is
    the caller's responsibility (see
    :meth:`~physics_simulators.mujoco_simulator.MujocoSimulator.set_geom_friction`);
    recorded here for persistence. ``None`` leaves the friction untouched.
    """


@dataclass(kw_only=True)
class PlaceTuningParameters:
    """
    Tunable transport/placing/release speeds for
    :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`.
    """

    placing_linear_velocity: Optional[float] = None
    """
    Maximum linear speed (in m/s) for the final descent onto the target location,
    enforced via
    :class:`~giskardpy.motion_statechart.tasks.cartesian_tasks.CartesianPositionVelocityLimit`.
    ``None`` leaves the speed unconstrained.
    """

    transport_linear_velocity: Optional[float] = None
    """
    Maximum linear speed (in m/s) for carrying the held object above the target
    location, before the final descent, enforced via
    :class:`~giskardpy.motion_statechart.tasks.cartesian_tasks.CartesianPositionVelocityLimit`.
    ``None`` leaves the speed unconstrained.
    """

    release_opening_velocity: Optional[float] = None
    """
    Maximum finger joint velocity (in m/s) used while opening the gripper to release
    the object, enforced via
    :class:`~giskardpy.motion_statechart.tasks.joint_tasks.JointVelocityLimit`. ``None``
    leaves the speed unconstrained.
    """

    retract_linear_velocity: Optional[float] = None
    """
    Maximum linear speed (in m/s) for retracting the end effector away from the placed
    object, enforced via
    :class:`~giskardpy.motion_statechart.tasks.cartesian_tasks.CartesianPositionVelocityLimit`.
    ``None`` leaves the speed unconstrained.
    """


@dataclass(kw_only=True)
class MovesGripper:
    """
    Builds the goals that drive a gripper to one of its states.
    """

    def gripper_goal(
        self,
        state: GripperState,
        end_effector: EndEffector,
        finger_velocity: Optional[float] = None,
        stall_minimum_time: Optional[float] = None,
        tolerate_stall: bool = False,
    ) -> MoveGripper:
        """
        :param state: The state to drive the gripper to.
        :param end_effector: The gripper that is driven.
        :param finger_velocity: Cap on the speed of the finger joints, in m/s.
        :param stall_minimum_time: How long the fingers must stand still before a stall
            counts, in seconds.
        :param tolerate_stall: Whether fingers that stopped short of their commanded
            position count as done.
        :return: The goal driving that gripper.
        """
        return MoveGripper(
            end_effector=end_effector,
            state=state,
            finger_velocity=finger_velocity,
            stall_minimum_time=stall_minimum_time,
            tolerate_stall=tolerate_stall,
        )


@dataclass(eq=False, repr=False, kw_only=True)
class MovesToolCenterPoint(Action, ABC):
    """
    An action that moves an arm's tool center point, with optional goal-achievement
    thresholds that fall back to the
    :class:`~coraplex.plans.context_extensions.MotionToleranceConfig` of the context
    when left unset.
    """

    position_threshold: Optional[float] = None
    """
    Distance threshold in meters for goal achievement. ``None`` falls back to
    :attr:`~coraplex.plans.context_extensions.MotionToleranceConfig.default_tcp_position_threshold`.
    """

    orientation_threshold: Optional[float] = None
    """
    Rotation threshold in rad for goal achievement. ``None`` falls back to
    :attr:`~coraplex.plans.context_extensions.MotionToleranceConfig.tool_orientation_threshold`.
    """

    moves_tool_center_point_in_a_straight_line: bool = field(default=False, init=False)
    """
    Whether the tool center point travels to each target along a straight line, instead
    of along whatever path the controller finds.
    """

    @classproperty
    def context_extensions_required_to_expand(
        cls,
    ) -> tuple[type[ContextExtension], ...]:
        return super().context_extensions_required_to_expand + (MotionToleranceConfig,)

    def resolved_position_threshold(self) -> float:
        """
        :return: :attr:`position_threshold` if set, otherwise the context's default.
        """
        if self.position_threshold is not None:
            return self.position_threshold
        return self.context.require_extension(
            MotionToleranceConfig
        ).default_tcp_position_threshold

    def resolved_orientation_threshold(self) -> float:
        """
        :return: :attr:`orientation_threshold` if set, otherwise the context's default.
        """
        if self.orientation_threshold is not None:
            return self.orientation_threshold
        return self.context.require_extension(
            MotionToleranceConfig
        ).tool_orientation_threshold

    def tool_center_point_goal(
        self,
        target: Pose,
        arm: Arm,
        movement_type: MovementType = MovementType.CARTESIAN,
        max_linear_velocity: Optional[float] = None,
        max_angular_velocity: Optional[float] = None,
    ) -> MotionStatechartNode:
        """
        :param target: Where the tool center point should end up.
        :param arm: The arm whose tool center point is moved.
        :param movement_type: Whether the orientation of the tool center point is
            commanded alongside its position.
        :param max_linear_velocity: Cap on the speed of the tool center point, in m/s.
        :param max_angular_velocity: Cap on how fast it turns, in rad/s. Only meaningful
            when the orientation is commanded.
        :return: The goal moving the tool center point there, together with whatever
            speed caps were asked for, and the task keeping the base still, see :meth:`~coraplex.robot_plans.actions.base.Action.keep_base_still`.
            A goal that is a parallel of its tasks holds them itself; any other is put in
            a parallel with them.
        """
        root = self.controlled_root
        tip = arm.end_effector.tool_frame
        accompanying: List[MotionStatechartNode] = self._velocity_limits(
            root, tip, movement_type, max_linear_velocity, max_angular_velocity
        )
        accompanying.extend(self.keep_base_still())
        goal = self._reach_target(target, root, tip, movement_type)
        if not accompanying:
            return goal
        if isinstance(goal, Parallel):
            for node in accompanying:
                goal.add_node(node)
            return goal
        return Parallel(nodes=[goal, *accompanying], name=type(goal).__name__)

    def _reach_target(
        self,
        target: Pose,
        root: KinematicStructureEntity,
        tip: KinematicStructureEntity,
        movement_type: MovementType,
    ) -> MotionStatechartNode:
        """
        :return: The task that brings `tip` to `target`, commanding its orientation
            unless only a translation was asked for, along a straight line where
            :attr:`moves_tool_center_point_in_a_straight_line`.
        """
        if movement_type == MovementType.TRANSLATION:
            position_task_type = (
                CartesianPositionStraight
                if self.moves_tool_center_point_in_a_straight_line
                else CartesianPosition
            )
            return position_task_type(
                root_link=root,
                tip_link=tip,
                goal_point=target.position,
                threshold=self.resolved_position_threshold(),
            )
        if self.moves_tool_center_point_in_a_straight_line:
            return CartesianPoseStraight(
                root_link=root,
                tip_link=tip,
                goal_pose=target,
                translation_threshold=self.resolved_position_threshold(),
                orientation_threshold=self.resolved_orientation_threshold(),
                binding_policy=GoalBindingPolicy.Bind_on_start,
            )
        return CartesianPose(
            root_link=root,
            tip_link=tip,
            goal_pose=target,
            translation_threshold=self.resolved_position_threshold(),
            orientation_threshold=self.resolved_orientation_threshold(),
        )

    @staticmethod
    def _velocity_limits(
        root: KinematicStructureEntity,
        tip: KinematicStructureEntity,
        movement_type: MovementType,
        max_linear_velocity: Optional[float],
        max_angular_velocity: Optional[float],
    ) -> List[MotionStatechartNode]:
        """
        :return: The speed caps that were asked for, if any. A turning cap is left out
            when the orientation is not commanded, because there is nothing to cap.
        """
        limits: List[MotionStatechartNode] = []
        if max_linear_velocity is not None:
            limits.append(
                CartesianPositionVelocityLimit(
                    root_link=root,
                    tip_link=tip,
                    max_linear_velocity=max_linear_velocity,
                )
            )
        if (
            max_angular_velocity is not None
            and movement_type != MovementType.TRANSLATION
        ):
            limits.append(
                CartesianRotationVelocityLimit(
                    root_link=root,
                    tip_link=tip,
                    max_angular_velocity=max_angular_velocity,
                )
            )
        return limits


@dataclass(eq=False, repr=False, kw_only=True)
class ReattachesBodies(Action, ABC):
    """
    An action that moves a body under a new parent in the world model, such as an object
    it picks up or a robot it carries along.
    """

    reattaches_in_world_model: bool = field(default=True, init=False)
    """
    Whether the world model is told that a body moved under its new parent, rather than
    contact carrying it there.
    """

    def reattach(
        self,
        body: KinematicStructureEntity,
        new_parent: KinematicStructureEntity,
    ) -> List[StatechartNode]:
        """
        :param body: The root of the branch to move.
        :param new_parent: The body the branch is moved under.
        :return: The node moving `body` under `new_parent`, none unless this action
            :attr:`reattaches_in_world_model`.
        """
        if not self.reattaches_in_world_model:
            return []
        return [MoveBranch(body=body, new_parent=new_parent)]


@dataclass
class GraspPoseSequence:
    """
    The tool frame goals that approach a grasp, reach it and withdraw from it.
    """

    pre_grasp: Pose
    """
    Where the gripper waits before it moves onto the grasp, clear of the object.
    """

    grasp: Pose
    """
    The tool frame goal at the grasp itself.
    """

    retreat: Pose
    """
    Where the gripper rises to when it leaves the grasp.
    """


@dataclass(kw_only=True)
class HasApproachesGraspPoses:
    """
    Turns a grasp frame (x-axis along the approach, see
    :class:`~semantic_digital_twin.grasping.grasp_candidates.GraspCandidate`) into the
    tool frame goals that approach it, reach it and withdraw from it.
    """

    approach_clearance: float = 0.1
    """
    The gap in meters between the object and the gripper at the pre-grasp pose.
    """

    retreat_distance: float = 0.1
    """
    How far in meters the gripper rises when it leaves a grasp or a placed object.
    """

    def grasp_pose_sequence(
        self,
        reference_T_grasp: Pose,
        end_effector: EndEffector,
        grasp: Optional[GraspCandidate] = None,
    ) -> GraspPoseSequence:
        """
        :param reference_T_grasp: The grasp frame to reach; for a release, where the
            object is to be put.
        :param end_effector: The end effector that is to reach it.
        :param grasp: The grasp whose object the pre-grasp pose has to stay outside of;
            ``None`` keeps only :attr:`approach_clearance`.
        :return: The tool frame goals around the grasp.
        """
        tool_goal = end_effector.tool_frame_goal_for_grasp(reference_T_grasp)
        return GraspPoseSequence(
            pre_grasp=self.pre_grasp_pose(
                reference_T_grasp, end_effector, self._approach_distance(grasp)
            ),
            grasp=tool_goal,
            retreat=self._retreat_pose(reference_T_grasp, tool_goal),
        )

    @staticmethod
    def pre_grasp_pose(
        reference_T_grasp: Pose, end_effector: EndEffector, distance: float
    ) -> Pose:
        """
        The goal back along the direction the gripper approaches a grasp from, aimed at
        the point the fingers meet as the grasp itself is.

        :param reference_T_grasp: The grasp frame, whose x-axis is the approach.
        :param end_effector: The end effector that reaches it.
        :param distance: How far back along the approach direction, in meters.
        :return: The tool frame goal, in ``reference_T_grasp``'s frame.
        """
        grasp_T_pre_grasp = HomogeneousTransformationMatrix.from_xyz_rpy(x=-distance)
        return end_effector.tool_frame_goal_for_grasp(
            (reference_T_grasp.homogeneous_matrix @ grasp_T_pre_grasp).pose
        )

    def _approach_distance(self, grasp: Optional[GraspCandidate]) -> float:
        """
        :param grasp: The grasp on the object, or ``None`` when there is no object.
        :return: The distance in meters from the grasp back to the pre-grasp pose: the
            distance to the object's bounding box along the approach, plus
            :attr:`approach_clearance`.
        """
        if grasp is None or not grasp.graspable.root.has_collision():
            return self.approach_clearance
        return self._distance_to_boundary(grasp) + self.approach_clearance

    @staticmethod
    def _distance_to_boundary(grasp: GraspCandidate) -> float:
        """
        The distance the gripper has to retrace before it leaves the body's bounding
        box.

        :param grasp: The grasp on the object.
        :return: The distance in meters, zero when the grasp already lies outside the
            box.
        """
        body = grasp.graspable.root
        bounding_box = body.collision.as_bounding_box_collection_in_frame(
            body
        ).bounding_box()

        grasp_position = grasp.grasp_pose.to_np()[:3, 3]
        # The grasp frame's x-axis is where the gripper comes from, so it retraces -x.
        retrace_direction = -grasp.grasp_pose.to_np()[:3, 0]
        intervals = (
            bounding_box.x_interval,
            bounding_box.y_interval,
            bounding_box.z_interval,
        )
        minimum = np.array([interval.lower for interval in intervals])
        maximum = np.array([interval.upper for interval in intervals])

        distances = [
            (
                (maximum[axis] if retrace_direction[axis] > 0 else minimum[axis])
                - grasp_position[axis]
            )
            / retrace_direction[axis]
            for axis in range(3)
            if not np.isclose(retrace_direction[axis], 0)
        ]
        return max(min(distances, default=0.0), 0.0)

    def _retreat_pose(self, reference_T_grasp: Pose, tool_goal: Pose) -> Pose:
        """
        The tool frame goal :attr:`retreat_distance` above the grasp along the world's
        z-axis (a grasp frame's own z-axis can lie flat).

        :param reference_T_grasp: The grasp frame that was reached.
        :param tool_goal: The tool frame goal at the grasp, whose orientation is kept.
        :return: The retreat pose, in ``reference_T_grasp``'s frame.
        """
        target = reference_T_grasp.reference_frame
        world = target._world
        world_T_grasp = world.transform(
            reference_T_grasp.homogeneous_matrix, world.root
        )
        world_T_lift = HomogeneousTransformationMatrix.from_xyz_rpy(
            z=self.retreat_distance, reference_frame=world.root
        )
        return Pose(
            world.transform((world_T_lift @ world_T_grasp).position, target),
            tool_goal.quaternion,
            reference_frame=target,
        )
