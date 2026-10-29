from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import (
    ConditionType,
    variable_from,
)
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.robot_parts import Arm, EndEffector
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Handle,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from typing_extensions import Any

from coraplex.datastructures.dataclasses import Context
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.querying.predicates import GripperIsFree, IsAmongTheClosestGraspsTo
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.pick_up import GraspingAction
from coraplex.robot_plans.mixins import HasApproachesGraspPoses
from coraplex.robot_plans.motions.base import BaseMotion
from coraplex.robot_plans.motions.container import OpeningMotion, ClosingMotion
from coraplex.robot_plans.motions.gripper import (
    MoveGripperMotion,
    MoveToolCenterPointMotion,
)


@dataclass
class ContainerAction(ActionDescription, HasApproachesGraspPoses):
    """
    Moves a container like object by its handle.

    Taking hold of the handle, letting go of it again and clearing it afterwards is the
    same whichever way the container is moved; only the motion working the mechanism
    differs.
    """

    grasp: GraspCandidate
    """
    The grasp on the handle of the container that should be moved.
    """

    arm: Arm
    """
    Arm that should be used.
    """

    release_clearance: float = 0.05
    """
    The gap in meters between the handle and the gripper once it has let go.
    """

    @property
    @abstractmethod
    def _mechanism_motion(self) -> BaseMotion:
        """
        :return: The motion that moves the container while its handle is held.
        """

    def back_off_pose(self, grasp_pose: Pose, end_effector: EndEffector) -> Pose:
        """
        The tool frame goal that clears the released handle.

        The gripper leaves the way it came in, so that an open gripper still straddling
        the handle is drawn off it rather than across it.

        :param grasp_pose: The grasp frame the handle was held by.
        :param end_effector: The end effector that held it.
        :return: The pose the tool frame backs off to, in ``grasp_pose``'s frame.
        """
        return self.pre_grasp_pose(grasp_pose, end_effector, self.release_clearance)

    @classmethod
    def from_handle(cls, handle: Handle, arm: Arm, standing_position: Pose) -> Self:
        """
        :param handle: The handle of the container.
        :param arm: The arm that takes hold of the handle.
        :param standing_position: Where the robot stands while it takes hold.
        :return: This action, taking `handle` by its grasp closest to
            `standing_position`.
        """
        grasps = handle.grasp_candidates()
        [closest_grasp] = [
            grasp
            for grasp in grasps
            if IsAmongTheClosestGraspsTo(
                grasp, standing_position, grasps, number_of_grasps=1
            )()
        ]
        return cls(grasp=closest_grasp, arm=arm)

    @property
    def _action_plan(self) -> PlanNode:
        return sequential(
            [
                GraspingAction(
                    self.grasp,
                    self.arm,
                    approach_clearance=self.approach_clearance,
                ),
                self._mechanism_motion,
                MoveGripperMotion(
                    configuration=self.arm.end_effector.default_configuration(
                        GripperState.OPEN
                    ),
                    allow_gripper_collision=True,
                ),
                MoveToolCenterPointMotion(
                    self.back_off_pose(self.grasp.grasp_pose, self.arm.end_effector),
                    self.arm,
                    allow_gripper_collision=True,
                ),
            ]
        )


@dataclass
class OpenAction(ContainerAction):
    """
    Opens a container like object.
    """

    @property
    def _mechanism_motion(self) -> BaseMotion:
        return OpeningMotion(self.grasp.graspable.root, self.arm)

    @staticmethod
    def pre_condition(
        variables: dict[str, Variable], context: Context, kwargs: dict[str, Any]
    ) -> ConditionType:
        """
        The gripper with which to open the container has to be free.
        """
        return GripperIsFree(variables["arm"].end_effector)

    @staticmethod
    def post_condition(
        variables: dict[str, Variable], context: Context, kwargs: dict[str, Any]
    ) -> ConditionType:
        """
        The container has to be open.

        The gripper is clear of the handle by then, so what it holds says nothing about
        whether the container was opened.
        """
        handle_body = kwargs["grasp"].graspable.root
        open_connection = handle_body.get_first_parent_connection_of_type(
            ActiveConnection1DOF
        )

        return variable_from(open_connection).position > 0.3


@dataclass
class CloseAction(ContainerAction):
    """
    Closes a container like object.
    """

    @property
    def _mechanism_motion(self) -> BaseMotion:
        return ClosingMotion(self.grasp.graspable.root, self.arm)

    @staticmethod
    def post_condition(
        variables: dict[str, Variable], context: Context, kwargs: dict[str, Any]
    ) -> SymbolicExpression | bool:
        """
        The container has to be closed.
        """
        handle_body = kwargs["grasp"].graspable.root
        close_connection = handle_body.get_first_parent_connection_of_type(
            ActiveConnection1DOF
        )

        return variable_from(close_connection).position < 0.1
