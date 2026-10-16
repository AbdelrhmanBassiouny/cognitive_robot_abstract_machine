"""
Plan transformations that let particular robots carry out an action with a motion of
their own.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

import numpy as np
from typing_extensions import List

from coraplex.datastructures.enums import InsertionPosition
from coraplex.exceptions import ClosingGoalNotFound, ToolPathNotFound
from coraplex.plans.plan_transformation import (
    ConfigurationTransformation,
    InsertionTransformation,
    PlanTransformation,
)
from coraplex.robot_plans.actions.composite.tool_based import ToolMotionAction
from coraplex.robot_plans.actions.core.container import CloseAction, MovesHandle
from coraplex.robot_plans.actions.core.navigation import DrivesBase, NavigateAction
from coraplex.robot_plans.mixins import MovesToolCenterPoint
from cramph.composites import CramLanguageNode, Parallel, Sequence
from cramph.node import StatechartNode
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.goals.cartesian_goals import CartesianPoseStraight
from giskardpy.motion_statechart.goals.open_close import Close
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    CartesianPositionTrajectory,
    HoldOrientation,
)
from semantic_digital_twin.robots.justin import Justin
from semantic_digital_twin.robots.stretch import Stretch
from semantic_digital_twin.robots.tiago import Tiago
from semantic_digital_twin.spatial_types import RotationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose, Vector3
from semantic_digital_twin.world_description.connections import (
    PrismaticConnection,
    RevoluteConnection,
)
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% keeping the torso upright while using a tool


@dataclass
class KeepTheTorsoUprightWhileUsingATool(InsertionTransformation[ToolMotionAction]):
    """
    Keeps Justin's torso upright while it moves a tool, which no other robot needs: its
    torso would otherwise lean into the motion.
    """

    @property
    def position(self) -> InsertionPosition:
        return InsertionPosition.LAST_CHILD

    def is_applicable(self, plan_node: ToolMotionAction) -> bool:
        return isinstance(plan_node.robot, Justin)

    def anchor(self, plan_node: ToolMotionAction) -> StatechartNode:
        """
        :return: The goal holding the tool on its path, beside which the torso is held.
        :raises ToolPathNotFound: If the action holds no goal moving the tool along a
            path.
        """
        for node in plan_node.descendants:
            if isinstance(node, Parallel) and any(
                isinstance(child, CartesianPositionTrajectory) for child in node.nodes
            ):
                return node
        raise ToolPathNotFound(plan_node)

    def nodes_to_insert(self, plan_node: ToolMotionAction) -> List[StatechartNode]:
        root = plan_node.controlled_root
        torso_tip = plan_node.robot.mobile_base.torso.tip
        return [
            AlignPlanes(
                tip_link=torso_tip,
                root_link=root,
                tip_normal=Vector3.X(torso_tip),
                goal_normal=Vector3.Z(root),
                weight=DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE.value,
            )
        ]


# %% driving a differential drive


@dataclass
class DriveWithTheDifferentialDrive(ConfigurationTransformation[DrivesBase], ABC):
    """
    Moves the base of a robot with a goal for its differential drive, which turns
    towards a pose, drives there and turns again, instead of a goal that asks the base
    to move sideways.
    """

    def apply(self, plan_node: DrivesBase) -> None:
        plan_node.drives_differentially = True


@dataclass
class DriveStretchWithItsDifferentialDrive(DriveWithTheDifferentialDrive):
    """
    Moves the base of a Stretch with a goal for its differential drive, simulated or
    not.
    """

    def is_applicable(self, plan_node: DrivesBase) -> bool:
        return isinstance(plan_node.robot, Stretch)


@dataclass
class DriveTiagoWithItsDifferentialDrive(DriveWithTheDifferentialDrive):
    """
    Moves the base of a Tiago with a goal for its differential drive, simulated or not.
    """

    def is_applicable(self, plan_node: DrivesBase) -> bool:
        return isinstance(plan_node.robot, Tiago)


# %% keeping the base from turning while moving the tool


@dataclass
class KeepStretchFromTurningWhileMovingItsTool(
    PlanTransformation[MovesToolCenterPoint]
):
    """
    Drives a Stretch to where its arm reaches the first target of its tool center point,
    then holds the orientation of the base while the tool moves. The base still drives,
    which gives the tool its sixth degree of freedom beside the arm, the lift and the
    wrist, and makes moving it more stable.

    The base stops where the tool, with the arm in its reference configuration (see
    :meth:`_base_T_tool_in_reference_configuration`), is at that target and approaches
    it the way the target asks for. A target approached from straight above or below
    leaves the heading open, so the base is held where it stands.

    Applies only while the base is controlled together with the arm. An action that
    drives the base on its own is left as it is, since holding the base would stop the
    drive; the actions moving the tool inside it are held instead. An action moving a
    container by its handle is left as it is too, with everything inside it, since its
    tool follows the container further than the arm reaches, and the base has to turn to
    follow it. An action inside one that is held already is covered by it.
    """

    def is_applicable(self, plan_node: MovesToolCenterPoint) -> bool:
        robot = plan_node.robot
        return (
            isinstance(robot, Stretch)
            and robot.mobile_base.full_body_controlled
            and not any(
                isinstance(node, MovesHandle) for node in [plan_node, *plan_node.path]
            )
            and not any(isinstance(node, DrivesBase) for node in plan_node.descendants)
            and not any(self._holds_the_base(ancestor) for ancestor in plan_node.path)
        )

    def apply(self, plan_node: MovesToolCenterPoint) -> None:
        goal = self._first_tool_goal(plan_node)
        holding = Parallel(
            [
                HoldOrientation(
                    root_link=plan_node.world.root, tip_link=plan_node.robot.root
                )
            ]
        )
        holding.wrap(plan_node.action_body)
        if goal is None:
            return
        root_T_heading = self._heading_to_reach(plan_node, goal)
        if root_T_heading is None:
            return
        positioning_first = Sequence([])
        positioning_first.wrap(holding)
        positioning_first.insert_before(holding, NavigateAction(root_T_heading))

    @staticmethod
    def _holds_the_base(node: StatechartNode) -> bool:
        """
        :return: Whether `node` holds the orientation of the base of a robot, which this
            transformation makes an action do.
        """
        return any(isinstance(child, HoldOrientation) for child in node.descendants)

    @staticmethod
    def _first_tool_goal(
        action: MovesToolCenterPoint,
    ) -> CartesianPose | CartesianPoseStraight | None:
        """
        :return: The first goal of `action` moving a tool center point of its robot into
            a pose, or None if it holds no such goal.
        """
        tool_frames = [arm.end_effector.tool_frame for arm in action.robot.all_arms]
        for node in action.descendants:
            if (
                isinstance(node, (CartesianPose, CartesianPoseStraight))
                and node.tip_link in tool_frames
            ):
                return node
        return None

    def _heading_to_reach(
        self, action: MovesToolCenterPoint, goal: CartesianPose | CartesianPoseStraight
    ) -> Pose | None:
        """
        :return: The pose for :class:`~coraplex.robot_plans.actions.core.navigation.NavigateAction`
            to drive the base to, from which the tool reaches the pose of `goal` with the
            arm in its reference configuration, or None if the gripper approaches that
            pose from straight above or below.
        """
        world = action.world
        robot = action.robot
        [end_effector] = [
            arm.end_effector
            for arm in robot.all_arms
            if arm.end_effector.tool_frame is goal.tip_link
        ]
        base_T_tool = self._base_T_tool_in_reference_configuration(
            robot.root, end_effector.tool_frame
        )
        root_T_goal = world.transform(goal.goal_pose, world.root).to_np()
        approach_axis = end_effector.approach_axis.to_np()[:3]
        root_V_approach = root_T_goal[:3, :3] @ approach_axis
        base_V_approach = base_T_tool[:3, :3] @ approach_axis
        if np.allclose(root_V_approach[:2], 0):
            return None
        root_yaw_base = np.arctan2(root_V_approach[1], root_V_approach[0]) - np.arctan2(
            base_V_approach[1], base_V_approach[0]
        )
        root_R_base = RotationMatrix.from_rpy(yaw=root_yaw_base).to_np()[:3, :3]
        root_P_base = root_T_goal[:3, 3] - root_R_base @ base_T_tool[:3, 3]
        root_V_front = root_R_base @ robot.mobile_base.forward_axis.to_np()[:3]
        return Pose.from_xyz_rpy(
            root_P_base[0],
            root_P_base[1],
            robot.root.global_pose.to_np()[2, 3],
            yaw=float(np.arctan2(root_V_front[1], root_V_front[0])),
            reference_frame=world.root,
        )

    @staticmethod
    def _base_T_tool_in_reference_configuration(
        base: KinematicStructureEntity, tool_frame: KinematicStructureEntity
    ) -> np.ndarray:
        """
        :return: The pose of `tool_frame` relative to `base` with the arm in its
            reference configuration: every prismatic joint between them in the middle of
            its range, which half extends the arm, and every revolute joint at zero,
            which straightens the wrist. The world's state is left as it is.
        """
        world = base._world
        variables = []
        values = []
        for connection in world.compute_chain_of_connections(base, tool_frame):
            if isinstance(connection, PrismaticConnection):
                limits = connection.raw_dof.limits
                value = (limits.lower.position + limits.upper.position) / 2
            elif isinstance(connection, RevoluteConnection):
                value = -connection.offset / connection.multiplier
            else:
                continue
            variables.append(connection.raw_dof.variables.position)
            values.append(value)
        base_T_tool = world.compose_forward_kinematics_expression(base, tool_frame)
        return base_T_tool.substitute(variables, values).to_np()


# %% moving the tool center point in a straight line


@dataclass
class MoveStretchToolCenterPointInAStraightLine(
    ConfigurationTransformation[MovesToolCenterPoint]
):
    """
    Moves the tool center point of a Stretch to each of its targets along a straight
    line.
    """

    def is_applicable(self, plan_node: MovesToolCenterPoint) -> bool:
        return isinstance(plan_node.robot, Stretch)

    def apply(self, plan_node: MovesToolCenterPoint) -> None:
        plan_node.moves_tool_center_point_in_a_straight_line = True


# %% closing a container


@dataclass
class KeepStretchInFrontOfTheContainerItCloses(PlanTransformation[CloseAction]):
    """
    Keeps a kinematically simulated Stretch standing in front of the container it closes
    and holding on to the handle, so that it closes the container by pushing its arm
    forward.
    """

    def is_applicable(self, plan_node: CloseAction) -> bool:
        return isinstance(plan_node.robot, Stretch)

    @staticmethod
    def closing_goal(plan_node: CloseAction) -> Close:
        """
        :param plan_node: The close action.
        :return: The goal closing the container.
        :raises ClosingGoalNotFound: If the action holds no goal closing a container,
            which it has none of before it is expanded.
        """
        for node in plan_node.descendants:
            if isinstance(node, Close):
                return node
        raise ClosingGoalNotFound(plan_node)

    def apply(self, plan_node: CloseAction) -> None:
        closing_goal = self.closing_goal(plan_node)
        handle = closing_goal.environment_link
        tool_frame = closing_goal.tip_link
        robot_root = plan_node.robot.root
        CramLanguageNode.running(closing_goal).replace(
            closing_goal,
            Parallel(
                [
                    CartesianPose(
                        name="Keep holding handle",
                        root_link=handle,
                        tip_link=tool_frame,
                        goal_pose=Pose(reference_frame=tool_frame),
                    ),
                    AlignPlanes(
                        root_link=plan_node.world.root,
                        tip_link=robot_root,
                        goal_normal=Vector3.X(handle),
                        tip_normal=Vector3.NEGATIVE_Y(robot_root),
                    ),
                    Close(
                        tip_link=tool_frame,
                        environment_link=handle,
                        goal_joint_state=closing_goal.goal_joint_state,
                        grasping_end_effector=closing_goal.grasping_end_effector,
                    ),
                ]
            ),
        )
