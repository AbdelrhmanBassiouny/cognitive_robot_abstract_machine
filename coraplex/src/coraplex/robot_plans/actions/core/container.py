from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


from krrood.entity_query_language.factories import (
    a,
    variable,
)
from krrood.entity_query_language.query.match import Match
from coraplex.config.action_conf import ActionConfig
from coraplex.querying.grasp_closeness import GraspsClosestToTheRobot
from cramph.composites import Sequence
from cramph.node import StatechartNode
from coraplex.robot_plans.actions.core.pick_up import GraspingAction, HasGraspChoice
from coraplex.robot_plans.mixins import HasApproachesGraspPoses, MovesToolCenterPoint
from giskardpy.motion_statechart.graph_node import MotionStatechartNode
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.goals.open_close import Open, Close
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import Arm, EndEffector
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Handle,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose

# %% taking a container by its handle


@dataclass(eq=False, repr=False, kw_only=True)
class MovesHandle(MovesToolCenterPoint, HasGraspChoice, ABC):
    """
    An action that takes hold of a container's handle by :attr:`grasp`, moves the
    container with it, lets go and clears the handle.
    """

    approach_clearance: float = HasApproachesGraspPoses.approach_clearance
    """
    The gap in meters between the handle and the gripper before it closes on it.
    """

    release_clearance: float = 0.05
    """
    The gap in meters between the handle and the gripper once it has let go.
    """

    @classmethod
    def from_handle(cls, handle: Handle, arm: Arm) -> Match:
        """
        :param handle: The handle of the container.
        :param arm: The arm that takes hold of the handle.
        :return: This action on `handle`, with the grasp left open among the grasps
            the handle offers, the closest to where the robot stands when it is grounded
            first.
        """
        return a(cls)(
            grasp=variable(
                GraspCandidate, domain=GraspsClosestToTheRobot(handle, arm._robot)
            ),
            arm=arm,
        )

    @abstractmethod
    def create_mechanism_goal(self) -> MotionStatechartNode:
        """
        :return: A new goal moving the container while its handle is held.
        """

    def back_off_pose(self, grasp_pose: Pose, end_effector: EndEffector) -> Pose:
        """
        The tool frame goal that clears the released handle, back along the way the
        gripper came in, so an open gripper still straddling the handle is drawn off it
        rather than across it.

        :param grasp_pose: The grasp frame the handle was held by.
        :param end_effector: The end effector that held it.
        :return: The pose the tool frame backs off to, in `grasp_pose`'s frame.
        """
        return HasApproachesGraspPoses.pre_grasp_pose(
            grasp_pose, end_effector, self.release_clearance
        )

    def create_action_body(self) -> StatechartNode:
        end_effector = self.arm.end_effector
        return Sequence(
            nodes=[
                GraspingAction(
                    grasp=self.grasp,
                    arm=self.arm,
                    approach_clearance=self.approach_clearance,
                ),
                self.create_mechanism_goal(),
                MoveGripper(
                    end_effector=end_effector,
                    state=GripperState.OPEN,
                    allow_gripper_collision=True,
                ),
                self.tool_center_point_goal(
                    self.back_off_pose(self.grasp.grasp_pose, end_effector),
                    self.arm,
                    allow_gripper_collision=True,
                ),
            ]
        )


# %% opening and closing


@dataclass(eq=False, repr=False, kw_only=True)
class OpenAction(MovesHandle):
    """
    Opens a container like object.
    """

    def create_mechanism_goal(self) -> MotionStatechartNode:
        end_effector = self.arm.end_effector
        return Open(
            tip_link=end_effector.tool_frame,
            environment_link=self.grasp.graspable.root,
            grasping_end_effector=end_effector,
        )


@dataclass(eq=False, repr=False, kw_only=True)
class CloseAction(MovesHandle):
    """
    Closes a container like object.
    """

    def create_mechanism_goal(self) -> MotionStatechartNode:
        end_effector = self.arm.end_effector
        return Close(
            tip_link=end_effector.tool_frame,
            environment_link=self.grasp.graspable.root,
            goal_joint_state=ActionConfig.closed_container_joint_state,
            grasping_end_effector=end_effector,
        )
