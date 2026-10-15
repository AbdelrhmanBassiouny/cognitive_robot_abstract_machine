from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional, Self

from krrood.entity_query_language.factories import a, flat_variable, variable
from coraplex.datastructures.enums import ReachFraction
from coraplex.locations.locations import ReachabilityLocation
from cramph.composites import Sequence
from cramph.context import StatechartContext
from cramph.node import StatechartNode
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.mixins import HasApproachesGraspPoses
from coraplex.robot_plans.actions.composite.carrying import CarryAction
from coraplex.robot_plans.actions.composite.facing import FaceAndLookAtAction
from coraplex.robot_plans.actions.core.container import OpenAction
from coraplex.robot_plans.actions.core.navigation import (
    FaceAtAction,
    LookAtAction,
    NavigateAction,
)
from coraplex.querying.grasp_closeness import ClosestGrasps
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.grasping.grasp_candidates import (
    GraspCandidate,
    HasGraspCandidates,
)
from semantic_digital_twin.semantic_annotations.semantic_annotations import Handle
from semantic_digital_twin.spatial_types.spatial_types import Pose

# %% actions running other actions as their steps


@dataclass(eq=False, repr=False)
class TransportAction(Action):
    """
    Picks an object up with one step and puts it down with another.
    """

    pick_up: MoveAndPickUpAction
    """
    The step that picks the object up, or an underspecified statement of it.
    """

    place: MoveAndPlaceAction
    """
    The step that puts down what :attr:`pick_up` picked up, or an underspecified
    statement of it.
    """

    @classmethod
    def from_graspable_by_closest_grasps(
        cls,
        graspable: HasGraspCandidates,
        target_location: Pose,
        arm: Arm,
        context: StatechartContext,
        number_of_grasps: int = ClosestGrasps.number_of_grasps,
        seed: Optional[int] = None,
    ) -> Self:
        """
        A transport that takes `graspable` to `target_location`, standing wherever each
        step can be carried out from and taking the object by the grasps closest to the
        robot there.

        :param graspable: The object to transport.
        :param target_location: Where to put the object down.
        :param arm: The arm that carries the object.
        :param context: The context of the plan the steps run in, whose robot performs
            them.
        :param number_of_grasps: How many of the object's grasps closest to a standing
            pose are tried from there.
        :param seed: Seed for sampling the standing poses; ``None`` samples afresh.
        :return: The transport, standing near the object to pick it up and near the
            target to place it.
        """
        return cls(
            pick_up=MoveAndPickUpAction.from_graspable_by_closest_grasps(
                graspable=graspable,
                arm=arm,
                context=context,
                number_of_grasps=number_of_grasps,
                seed=seed,
            ),
            place=a(MoveAndPlaceAction)(
                navigate=a(NavigateAction)(
                    target_location=variable(
                        Pose,
                        domain=ReachabilityLocation(
                            target_pose=target_location,
                            arm=arm,
                            context=context,
                            seed=seed,
                        ),
                    )
                ),
                face_and_look_at=a(FaceAndLookAtAction)(
                    face_at=a(FaceAtAction)(target=target_location),
                    look_at=a(LookAtAction)(target=target_location),
                ),
                place=a(PlaceAction)(
                    object_designator=graspable, target_location=target_location
                ),
            ),
        )

    def create_action_body(self) -> StatechartNode:
        return Sequence(
            [
                ParkArmsAction(self.robot.all_arms),
                self.pick_up,
                ParkArmsAction(self.robot.all_arms),
                self.place,
                ParkArmsAction(self.robot.all_arms),
            ]
        )


@dataclass(eq=False, repr=False)
class PickAndPlaceAction(Action):
    """
    Picks an object up with one step and puts it down with another, without moving the
    base of the robot.
    """

    pick_up: PickUpAction
    """
    The step that picks the object up, or an underspecified statement of it.
    """

    place: PlaceAction
    """
    The step that puts down what :attr:`pick_up` picked up, or an underspecified
    statement of it.
    """

    def create_action_body(self) -> StatechartNode:
        return Sequence(
            [
                self.pick_up,
                self.place,
            ]
        )


@dataclass(eq=False, repr=False)
class MoveAndPlaceAction(Action):
    """
    Carries the object upright to where the robot stands, faces the target and places
    the object there.
    """

    navigate: NavigateAction
    """
    The step to where the robot stands while placing, or an underspecified statement of
    it.
    """

    face_and_look_at: FaceAndLookAtAction
    """
    The turn towards the target and the look at it, or an underspecified statement of
    them.
    """

    place: PlaceAction
    """
    The step that puts the object down, or an underspecified statement of it.
    """

    @classmethod
    def from_standing_position(
        cls,
        standing_position: Pose,
        target_location: Pose,
        object_designator: HasGraspCandidates,
    ) -> Self:
        """
        :param standing_position: Where the robot stands while placing.
        :param target_location: Where to put the object down.
        :param object_designator: The object to put down.
        :return: The step placing the object from `standing_position`.
        """
        return cls(
            navigate=NavigateAction(standing_position),
            face_and_look_at=FaceAndLookAtAction(
                face_at=FaceAtAction(target_location),
                look_at=LookAtAction(target_location),
            ),
            place=PlaceAction(
                object_designator=object_designator, target_location=target_location
            ),
        )

    def create_action_body(self) -> StatechartNode:
        return Sequence(
            [
                CarryAction(self.navigate),
                self.face_and_look_at,
                self.place,
            ]
        )


@dataclass(eq=False, repr=False)
class MoveAndPickUpAction(Action):
    """
    Navigates to where the robot stands, faces the object and picks it up.
    """

    navigate: NavigateAction
    """
    The step to where the robot stands while picking up, or an underspecified statement
    of it.
    """

    face_and_look_at: FaceAndLookAtAction
    """
    The turn towards the object and the look at it, or an underspecified statement of
    them.
    """

    pick_up: PickUpAction
    """
    The step that picks the object up, or an underspecified statement of it.
    """

    @classmethod
    def from_standing_position(
        cls,
        standing_position: Pose,
        grasp: GraspCandidate,
        arm: Arm,
        approach_clearance: float = HasApproachesGraspPoses.approach_clearance,
        retreat_distance: float = HasApproachesGraspPoses.retreat_distance,
    ) -> Self:
        """
        :param standing_position: Where the robot stands while picking up.
        :param grasp: The grasp to take hold by, which also names the object.
        :param arm: The arm to pick up with.
        :param approach_clearance: How far from the grasp the gripper approaches from.
        :param retreat_distance: How far the gripper retreats with the object.
        :return: The step picking the object up from `standing_position`.
        """
        object_pose = Pose(reference_frame=grasp.graspable.root)
        return cls(
            navigate=NavigateAction(standing_position),
            face_and_look_at=FaceAndLookAtAction(
                face_at=FaceAtAction(object_pose), look_at=LookAtAction(object_pose)
            ),
            pick_up=PickUpAction(
                grasp=grasp,
                arm=arm,
                approach_clearance=approach_clearance,
                retreat_distance=retreat_distance,
            ),
        )

    @classmethod
    def from_graspable_by_closest_grasps(
        cls,
        graspable: HasGraspCandidates,
        arm: Arm,
        context: StatechartContext,
        number_of_grasps: int = ClosestGrasps.number_of_grasps,
        seed: Optional[int] = None,
    ) -> Match:
        """
        A pick-up of `graspable`, standing wherever it can be reached from and taking it
        by the grasps closest to the robot there, the closest first.

        :param graspable: The object to pick up.
        :param arm: The arm to pick up with.
        :param context: The context of the plan the steps run in, whose robot performs
            them.
        :param number_of_grasps: How many of the object's grasps closest to a standing
            pose are tried from there.
        :param seed: Seed for sampling the standing poses; ``None`` samples afresh.
        :return: The pick-up, with the standing pose and the grasp left open.
        """
        object_pose = Pose(reference_frame=graspable.root)
        standing_position = variable(
            Pose,
            domain=ReachabilityLocation(
                target_pose=object_pose, arm=arm, context=context, seed=seed
            ),
        )
        return a(cls)(
            navigate=a(NavigateAction)(target_location=standing_position),
            face_and_look_at=a(FaceAndLookAtAction)(
                face_at=a(FaceAtAction)(target=object_pose),
                look_at=a(LookAtAction)(target=object_pose),
            ),
            pick_up=a(PickUpAction)(
                grasp=flat_variable(
                    ClosestGrasps(graspable, standing_position, number_of_grasps)
                ),
                arm=arm,
            ),
        )

    def create_action_body(self) -> StatechartNode:
        return Sequence(
            [
                self.navigate,
                self.face_and_look_at,
                self.pick_up,
            ]
        )


@dataclass(eq=False, repr=False)
class MoveAndOpenAction(Action):
    """
    Navigates to where the robot stands, faces the handle and opens its container.
    """

    navigate: NavigateAction
    """
    The step to where the robot stands while opening, or an underspecified statement of
    it.
    """

    face_and_look_at: FaceAndLookAtAction
    """
    The turn towards the handle and the look at it, or an underspecified statement of
    them.
    """

    open_container: OpenAction
    """
    The step that opens the container, or an underspecified statement of it.
    """

    @classmethod
    def from_standing_position(
        cls, standing_position: Pose, grasp: GraspCandidate, arm: Arm
    ) -> Self:
        """
        :param standing_position: Where the robot stands while opening.
        :param grasp: The grasp to take the handle by, which also names the handle.
        :param arm: The arm to open with.
        :return: The step opening the container from `standing_position`.
        """
        handle_pose = Pose(reference_frame=grasp.graspable.root)
        return cls(
            navigate=NavigateAction(standing_position),
            face_and_look_at=FaceAndLookAtAction(
                face_at=FaceAtAction(handle_pose), look_at=LookAtAction(handle_pose)
            ),
            open_container=OpenAction(grasp=grasp, arm=arm),
        )

    @classmethod
    def from_handle_by_closest_grasps(
        cls,
        handle: Handle,
        arm: Arm,
        context: StatechartContext,
        number_of_grasps: int = ClosestGrasps.number_of_grasps,
        seed: Optional[int] = None,
    ) -> Match:
        """
        An opening of the container `handle` belongs to, standing wherever the handle
        can be worked from and taking it by the grasps closest to the robot there, the
        closest first.

        :param handle: The handle of the container to open.
        :param arm: The arm to open with.
        :param context: The context of the plan the steps run in, whose robot performs
            them.
        :param number_of_grasps: How many of the handle's grasps closest to a standing
            pose are tried from there.
        :param seed: Seed for sampling the standing poses; ``None`` samples afresh.
        :return: The opening, with the standing pose and the grasp left open.
        """
        handle_pose = Pose(reference_frame=handle.root)
        standing_position = variable(
            Pose,
            domain=ReachabilityLocation(
                target_pose=handle_pose,
                arm=arm,
                reach_fraction=ReachFraction.ACCESSING,
                context=context,
                seed=seed,
            ),
        )
        return a(cls)(
            navigate=a(NavigateAction)(target_location=standing_position),
            face_and_look_at=a(FaceAndLookAtAction)(
                face_at=a(FaceAtAction)(target=handle_pose),
                look_at=a(LookAtAction)(target=handle_pose),
            ),
            open_container=a(OpenAction)(
                grasp=flat_variable(
                    ClosestGrasps(handle, standing_position, number_of_grasps)
                ),
                arm=arm,
            ),
        )

    def create_action_body(self) -> StatechartNode:
        return Sequence(
            [
                self.navigate,
                self.face_and_look_at,
                self.open_container,
            ]
        )
