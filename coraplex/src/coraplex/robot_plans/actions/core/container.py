from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from typing_extensions import Any, Dict

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import (
    a,
    and_,
    or_,
    variable,
    variable_from,
    ConditionType,
)
from krrood.entity_query_language.query.match import Match
from cramph.context import StatechartContext
from coraplex.config.action_conf import ActionConfig
from coraplex.querying.predicates import GripperIsFree
from cramph.composites import Sequence
from cramph.node import StatechartNode
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.pick_up import GraspingAction, HasGraspChoice
from coraplex.robot_plans.mixins import HasApproachesGraspPoses
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.goals.open_close import Open, Close
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.reasoning.predicates import allclose
from semantic_digital_twin.reasoning.robot_predicates import is_body_in_gripper
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Handle,
)
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF

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
            the handle offers.
        """
        return a(cls)(
            grasp=variable(GraspCandidate, domain=handle.grasp_candidates()), arm=arm
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

    @staticmethod
    def pre_condition(
        variables: Dict[str, Variable],
        context: StatechartContext,
        kwargs: Dict[str, Any],
    ) -> ConditionType:
        """
        The gripper with which to open the container has to be free.
        """
        return GripperIsFree(variables["arm"].end_effector)

    @staticmethod
    def post_condition(
        variables: Dict[str, Variable],
        context: StatechartContext,
        kwargs: Dict[str, Any],
    ) -> ConditionType:
        """
        The handle has to be in the gripper of the robot and the container has to be
        open.
        """
        end_effector = kwargs["arm"].end_effector
        handle_body = kwargs["grasp"].graspable.root
        parent_connection = handle_body.get_first_parent_connection_of_type(
            ActiveConnection1DOF
        )
        return and_(
            or_(
                is_body_in_gripper(variable_from(handle_body), end_effector) > 0.9,
                allclose(
                    variable_from(handle_body).global_pose.position,
                    variable_from(end_effector.tool_frame).global_pose.position,
                    atol=3e-2,
                ),
            ),
            variable_from(parent_connection).position > 0.3,
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

    @staticmethod
    def post_condition(
        variables: Dict[str, Variable],
        context: StatechartContext,
        kwargs: Dict[str, Any],
    ) -> SymbolicExpression | bool:
        """
        The container has to be closed.
        """
        close_connection = kwargs[
            "grasp"
        ].graspable.root.get_first_parent_connection_of_type(ActiveConnection1DOF)

        return variable_from(close_connection).position < 0.1
