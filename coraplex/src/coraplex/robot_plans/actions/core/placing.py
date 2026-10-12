from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, Dict, List, Tuple

from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import (
    or_,
    not_,
    and_,
    variable_from,
    ConditionType,
)
from coraplex.plans.context_extensions import RobotAccess
from cramph.context import StatechartContext
from coraplex.exceptions import ObjectIsNotHeld
from coraplex.querying.predicates import GripperHolds
from cramph.node import StatechartNode
from cramph.composites import Sequence
from cramph.world_modification_nodes import MoveBranch
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.mixins import (
    HasApproachesGraspPoses,
    HasGraspDetectionThreshold,
    MovesGripper,
    MovesToolCenterPoint,
    PlaceTuningParameters,
)
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.grasping.grasp_candidates import (
    GraspCandidate,
    HasGraspCandidates,
)
from semantic_digital_twin.reasoning.predicates import allclose
from semantic_digital_twin.reasoning.robot_predicates import is_body_gripped
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types.spatial_types import Pose


@dataclass(eq=False, repr=False)
class PlaceAction(
    MovesToolCenterPoint,
    HasApproachesGraspPoses,
    PlaceTuningParameters,
    HasGraspDetectionThreshold,
    MovesGripper,
):
    """
    Places an object at a position with the arm that holds it.
    """

    object_designator: HasGraspCandidates
    """
    The annotation of the object that should be placed.
    """

    target_location: Pose
    """
    Pose in the world at which the object should be placed.
    """

    grasp_release_threshold: float = field(default=0.1, kw_only=True)
    """
    Maximum fraction of sampled rays between the gripper's fingers that may still hit
    :attr:`object_designator` for it to count as released (see
    :func:`~semantic_digital_twin.reasoning.robot_predicates.is_body_gripped`).
    """

    def create_action_body(self) -> StatechartNode:
        arm, grasp = self._holding_arm_and_grasp()
        # A release runs the grasp backwards: down from above the target, then out
        # along the way the grasp was approached.
        poses = self.grasp_pose_sequence(
            grasp.moved_to(self.target_location), arm.end_effector, grasp
        )

        return Sequence(
            [
                self.tool_center_point_goal(
                    poses.retreat,
                    arm,
                    allow_gripper_collision=True,
                    max_linear_velocity=self.transport_linear_velocity,
                ),
                self.tool_center_point_goal(
                    poses.grasp,
                    arm,
                    allow_gripper_collision=True,
                    max_linear_velocity=self.placing_linear_velocity,
                ),
                self.gripper_goal(
                    GripperState.OPEN,
                    arm.end_effector,
                    allow_gripper_collision=True,
                    finger_velocity=self.release_opening_velocity,
                ),
                self._retract(arm, poses.pre_grasp),
            ]
        )

    def _retract(self, arm: Arm, retract_pose: Pose) -> Sequence:
        """
        :param arm: The arm that placed the object.
        :param retract_pose: Where its tool frame withdraws to.
        :return: The steps that re-parent the placed object back to the world and
            retract the end effector away from it.
        """
        return Sequence(
            name=f"{self.name}/retract",
            nodes=[
                MoveBranch(
                    body=self.object_designator.root, new_parent=self.world.root
                ),
                self.tool_center_point_goal(
                    retract_pose,
                    arm,
                    max_linear_velocity=self.retract_linear_velocity,
                ),
            ],
        )

    def _holding_arm_and_grasp(self) -> Tuple[Arm, GraspCandidate]:
        """
        The arm that holds :attr:`object_designator`, and the grasp it holds it by.

        Read off the gripper while it holds the object; while the statechart is still
        being built, taken from the latest pick-up of the object before this place.

        :return: The arm and its grasp on the object.
        :raises ObjectIsNotHeld: If no arm holds the object and no pick-up precedes this
            place.
        """
        object_body = self.object_designator.root
        for arm in self.robot.all_arms:
            end_effector = arm.end_effector
            if GripperHolds(end_effector, object_body)():
                return arm, GraspCandidate(
                    self.object_designator, end_effector.held_body_T_grasp
                )
        for previous_pick in self.statechart.get_preceding_nodes_by_type(
            self, PickUpAction
        ):
            if previous_pick.grasp.graspable.root is object_body:
                return previous_pick.arm, previous_pick.grasp
        raise ObjectIsNotHeld(self.object_designator)

    def _grasp_on_the_held_object(self) -> GraspCandidate:
        """
        :return: The grasp :attr:`object_designator` is held by, as
            :meth:`_holding_arm_and_grasp` finds it.
        """
        return self._holding_arm_and_grasp()[1]

    @staticmethod
    def pre_condition(
        variables: Dict[str, Variable],
        context: StatechartContext,
        kwargs: Dict[str, Any],
    ) -> ConditionType:
        """
        An arm of the robot needs to hold the object, whether the object hangs off its
        gripper or merely lies between the fingers.

        A thin or rim grasp leaves too little of the object between the fingers for the
        ray test alone to see it, so a gripper the object hangs off counts too.
        """
        object_body = kwargs["object_designator"].root
        return or_(
            *[
                GripperHolds(arm.end_effector, object_body)
                for arm in context.require_extension(RobotAccess).robot.all_arms
            ],
            *PlaceAction._grips_of_every_arm(
                context, kwargs, kwargs["grasp_detection_threshold"]
            ),
        )

    @staticmethod
    def post_condition(
        variables: Dict[str, Variable],
        context: StatechartContext,
        kwargs: Dict[str, Any],
    ) -> ConditionType:
        """
        No arm may hold the object any more and it needs to be at the target location.
        """
        return and_(
            *[
                not_(grip)
                for grip in PlaceAction._grips_of_every_arm(
                    context, kwargs, kwargs["grasp_release_threshold"]
                )
            ],
            allclose(
                variable_from(kwargs["object_designator"].root).global_pose,
                kwargs["target_location"],
                atol=0.03,
            ),
        )

    @staticmethod
    def _grips_of_every_arm(
        context: StatechartContext, kwargs: Dict[str, Any], threshold: float
    ) -> List[ConditionType]:
        """
        :param threshold: The fraction of rays between the fingers that has to hit the
            object for it to count as gripped.
        :return: For every arm of the robot, whether its gripper grips the object.
        """
        return [
            is_body_gripped(
                variable_from(kwargs["object_designator"].root),
                arm.end_effector,
                threshold=threshold,
            )
            for arm in context.require_extension(RobotAccess).robot.all_arms
        ]
