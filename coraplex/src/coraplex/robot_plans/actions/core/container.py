from __future__ import annotations

from abc import ABC
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
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.pick_up import GraspingAction, HasGraspChoice
from coraplex.robot_plans.mixins import HasApproachesGraspPoses
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.goals.open_close import Open, Close
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Handle,
)

# %% taking a container by its handle


@dataclass(eq=False, repr=False)
class MovesHandle(Action, HasGraspChoice, ABC):
    """
    An action that takes hold of a container's handle by :attr:`grasp` and moves it.
    """

    approach_clearance: float = HasApproachesGraspPoses.approach_clearance
    """
    The gap in meters between the handle and the gripper before it closes on it.
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


# %% opening and closing


@dataclass(eq=False, repr=False)
class OpenAction(MovesHandle):
    """
    Opens a container like object.
    """

    def create_action_body(self) -> StatechartNode:
        end_effector = self.arm.end_effector
        return Sequence(
            [
                GraspingAction(
                    self.grasp,
                    self.arm,
                    approach_clearance=self.approach_clearance,
                ),
                Open(
                    tip_link=end_effector.tool_frame,
                    environment_link=self.grasp.graspable.root,
                    grasping_end_effector=end_effector,
                ),
                MoveGripper(
                    end_effector=end_effector,
                    state=GripperState.OPEN,
                    allow_gripper_collision=True,
                ),
            ]
        )


@dataclass(eq=False, repr=False)
class CloseAction(MovesHandle):
    """
    Closes a container like object.
    """

    def create_action_body(self) -> StatechartNode:
        end_effector = self.arm.end_effector
        return Sequence(
            [
                GraspingAction(
                    self.grasp,
                    self.arm,
                    approach_clearance=self.approach_clearance,
                ),
                Close(
                    tip_link=end_effector.tool_frame,
                    environment_link=self.grasp.graspable.root,
                    goal_joint_state=ActionConfig.closed_container_joint_state,
                    grasping_end_effector=end_effector,
                ),
                MoveGripper(
                    end_effector=end_effector,
                    state=GripperState.OPEN,
                    allow_gripper_collision=True,
                ),
            ]
        )
