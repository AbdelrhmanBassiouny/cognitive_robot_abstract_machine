"""
Plan transformations that let particular robots carry out an action with a motion of
their own.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from typing_extensions import List

from coraplex.exceptions import ClosingGoalNotFound, ToolPathNotFound
from coraplex.plans.plan_transformation import (
    ConfigurationTransformation,
    ParallelInsertion,
    PlanTransformation,
)
from coraplex.robot_plans.actions.composite.tool_based import ToolMotionAction
from coraplex.robot_plans.actions.core.container import CloseAction
from coraplex.robot_plans.actions.core.navigation import DrivesBase
from coraplex.robot_plans.mixins import MovesToolCenterPoint
from cramph.composites import CramLanguageNode, Parallel
from cramph.node import StatechartNode
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.goals.open_close import Close
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    CartesianPositionTrajectory,
)
from semantic_digital_twin.robots.justin import Justin
from semantic_digital_twin.robots.stretch import Stretch
from semantic_digital_twin.robots.tiago import Tiago
from semantic_digital_twin.spatial_types.spatial_types import Pose, Vector3

# %% keeping the torso upright while using a tool


@dataclass
class KeepTheTorsoUprightWhileUsingATool(ParallelInsertion[ToolMotionAction]):
    """
    Keeps Justin's torso upright while it moves a tool, which no other robot needs: its
    torso would otherwise lean into the motion.
    """

    def is_applicable(self, plan_node: ToolMotionAction) -> bool:
        return isinstance(plan_node.robot, Justin)

    def anchor(self, plan_node: ToolMotionAction) -> StatechartNode:
        """
        :return: The goal moving the tool along its path, alongside which the torso is
            held.
        :raises ToolPathNotFound: If the action holds no goal moving the tool along a
            path.
        """
        for node in plan_node.descendants:
            if isinstance(node, CartesianPositionTrajectory):
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
