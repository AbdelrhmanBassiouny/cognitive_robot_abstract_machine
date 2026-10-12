from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Dict

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import (
    and_,
    or_,
    variable_from,
    ConditionType,
)
from cramph.context import StatechartContext
from coraplex.config.action_conf import ActionConfig
from coraplex.querying.predicates import GripperIsFree
from cramph.composites import Sequence
from cramph.node import StatechartNode
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.pick_up import GraspingAction
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


@dataclass(eq=False, repr=False)
class OpenAction(Action):
    """
    Opens a container like object.
    """

    handle: Handle
    """
    The handle of the container that should be opened.
    """

    arm: Arm
    """
    Arm that should be used for opening the container.
    """

    approach_clearance: float = HasApproachesGraspPoses.approach_clearance
    """
    The gap in meters between the handle and the gripper before it closes on it.
    """

    def create_action_body(self) -> StatechartNode:
        end_effector = self.arm.end_effector
        return Sequence(
            [
                GraspingAction(
                    GraspCandidate.from_body_origin(self.handle),
                    self.arm,
                    approach_clearance=self.approach_clearance,
                ),
                Open(
                    tip_link=end_effector.tool_frame,
                    environment_link=self.handle.root,
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
        handle_body = kwargs["handle"].root
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
class CloseAction(Action):
    """
    Closes a container like object.
    """

    handle: Handle
    """
    The handle of the container that should be closed.
    """

    arm: Arm
    """
    Arm that should be used for closing.
    """

    approach_clearance: float = HasApproachesGraspPoses.approach_clearance
    """
    The gap in meters between the handle and the gripper before it closes on it.
    """

    def create_action_body(self) -> StatechartNode:
        end_effector = self.arm.end_effector
        return Sequence(
            [
                GraspingAction(
                    GraspCandidate.from_body_origin(self.handle),
                    self.arm,
                    approach_clearance=self.approach_clearance,
                ),
                Close(
                    tip_link=end_effector.tool_frame,
                    environment_link=self.handle.root,
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
        close_connection = kwargs["handle"].root.get_first_parent_connection_of_type(
            ActiveConnection1DOF
        )

        return variable_from(close_connection).position < 0.1
