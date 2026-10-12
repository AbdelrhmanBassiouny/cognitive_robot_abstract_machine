from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from typing_extensions import Optional, Dict, Any, List

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import variable_from
from semantic_digital_twin.reasoning.predicates import allclose
from semantic_digital_twin.robots.robot_parts import Arm, EndEffector
from semantic_digital_twin.spatial_types.spatial_types import Pose

from coraplex.plans.context_extensions import RobotAccess
from cramph.context import StatechartContext
from coraplex.datastructures.trajectory import PoseTrajectory
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.mixins import (
    HasMaxJointVelocity,
    MovesGripper,
    MovesToolCenterPoint,
)
from cramph.composites import Parallel, Sequence
from cramph.node import StatechartNode
from giskardpy.motion_statechart.binding_policy import GoalBindingPolicy
from giskardpy.motion_statechart.goals.collision_avoidance import (
    UpdateTemporaryCollisionRules,
)
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPose
from giskardpy.motion_statechart.tasks.joint_tasks import (
    JointPositionList,
    JointVelocityLimit,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.datastructures.definitions import (
    TorsoState,
    GripperState,
    StaticJointState,
)


@dataclass(eq=False, repr=False)
class MoveTorsoAction(Action):
    """
    Move the torso of the robot up and down.
    """

    torso_state: TorsoState
    """
    The state of the torso that should be set.
    """

    def create_action_body(self) -> StatechartNode:
        joint_state = self.robot.get_torso().get_joint_state_by_type(self.torso_state)
        return Sequence([JointPositionList(goal_state=joint_state)])

    @staticmethod
    def post_condition(
        variables: Dict[str, Variable],
        context: StatechartContext,
        kwargs: Dict[str, Any],
    ) -> SymbolicExpression | bool:
        """
        The target joint state for the torso needs to be achieved.
        """
        joint_state = (
            context.require_extension(RobotAccess)
            .robot.get_torso()
            .get_joint_state_by_type(kwargs["torso_state"])
        )
        return variable_from(joint_state).is_achieved()


@dataclass(eq=False, repr=False)
class SetGripperAction(Action, MovesGripper):
    """
    Set the gripper state of the robot.
    """

    gripper: EndEffector
    """
    The gripper that should be set.
    """

    motion: GripperState
    """
    The motion that should be set on the gripper.
    """

    def create_action_body(self) -> StatechartNode:
        return self.gripper_goal(self.motion, self.gripper)


@dataclass(eq=False, repr=False)
class ParkArmsAction(Action, HasMaxJointVelocity):
    """
    Park the arms of the robot.
    """

    arms: List[Arm]
    """
    The arms that should be parked.
    """

    def create_action_body(self) -> StatechartNode:
        park_state = self.park_joint_state()
        joint_goal = JointPositionList(goal_state=park_state)
        if self.max_joint_velocity is None:
            return joint_goal
        return Parallel(
            [
                joint_goal,
                JointVelocityLimit(
                    connections=list(park_state.connections),
                    max_velocity=self.max_joint_velocity,
                ),
            ]
        )

    def park_joint_state(self) -> JointState:
        """
        :return: The joint state that puts every arm this action parks into its park
            position.
        """
        connections = []
        target_values = []
        for arm in self.arms:
            joint_state = arm.get_joint_state_by_type(StaticJointState.PARK)
            connections.extend(joint_state.connections)
            target_values.extend(joint_state.target_values)
        return JointState(connections=connections, target_values=target_values)


@dataclass(eq=False, repr=False)
class FollowToolCenterPointPathAction(MovesToolCenterPoint):
    """
    Represents an action to move a robotic arm's TCP (Tool Center Point) along a path of
    poses.
    """

    target_locations: PoseTrajectory
    """
    Path poses for the TCP motion.
    """

    arm: Arm
    """
    The arm to use.
    """

    def create_action_body(self) -> StatechartNode:
        return Sequence(
            [self._waypoint_goal(pose) for pose in self.target_locations.poses]
        )

    def _waypoint_goal(self, target: Pose) -> CartesianPose:
        """
        :param target: The waypoint the tool center point passes through.
        :return: The task reaching that waypoint, leaving each threshold to giskard's
            own default unless this action was given one.
        """
        thresholds = {}
        if self.position_threshold is not None:
            thresholds["translation_threshold"] = self.position_threshold
        if self.orientation_threshold is not None:
            thresholds["orientation_threshold"] = self.orientation_threshold
        return CartesianPose(
            root_link=self.controlled_root,
            tip_link=self.arm.end_effector.tool_frame,
            goal_pose=target,
            **thresholds,
        )

    def validate(
        self,
        result: Optional[Any] = None,
        max_wait_time: timedelta = timedelta(seconds=2),
    ):
        pass


@dataclass(eq=False, repr=False)
class MoveManipulatorAction(MovesToolCenterPoint):
    """
    Move the end_effector to a specific pose.
    """

    target_pose: Pose
    """
    The pose where the end_effector should be moved to.
    """

    end_effector: EndEffector
    """
    The end_effector that should be moved.
    """

    allow_gripper_collision: bool
    """
    If the gripper can collide with something.
    """

    def create_action_body(self) -> StatechartNode:
        goal = CartesianPose(
            root_link=self.controlled_root,
            tip_link=self.end_effector.tool_frame,
            goal_pose=self.target_pose,
            translation_threshold=self.resolved_position_threshold(),
            orientation_threshold=self.resolved_orientation_threshold(),
            binding_policy=GoalBindingPolicy.Bind_on_start,
        )
        if not self.allow_gripper_collision:
            return goal
        return Parallel(
            [
                goal,
                UpdateTemporaryCollisionRules.for_end_effector(self.end_effector),
            ]
        )

    @staticmethod
    def post_condition(
        variables: Dict[str, Variable],
        context: StatechartContext,
        kwargs: Dict[str, Any],
    ) -> SymbolicExpression:
        end_effector = variables["end_effector"]
        target_pose = variables["target_pose"]
        return allclose(
            end_effector.tool_frame.global_pose.to_np(),
            target_pose.to_np(),
            atol=0.1,
        )
