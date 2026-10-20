from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING

from cramph.node import StatechartNode
from coraplex.robot_plans.actions.base import Action, ParallelAction
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types.spatial_types import Vector3

if TYPE_CHECKING:
    from semantic_digital_twin.world_description.world_entity import Body

# %% driving with held objects upright


@dataclass(eq=False, repr=False, kw_only=True)
class CarryAction(ParallelAction):
    """
    Drives the robot's base to a pose while every object the robot holds keeps its
    z-axis pointing up and every arm holding nothing is parked.

    An object counts as held when it hangs below a gripper's tool frame, or when a pick-
    up earlier in the plan takes it and no placing puts it down again before this
    action.
    """

    navigate: NavigateAction
    """
    The drive.
    """

    upright_threshold: float = AlignPlanes.threshold
    """
    Angle in radians between a held object's z-axis and the world's z-axis within which
    the object counts as upright.
    """

    def create_steps(self) -> list[StatechartNode]:
        held_bodies = {arm: self._held_body(arm) for arm in self.robot.all_arms}
        free_arms = [arm for arm, held_body in held_bodies.items() if held_body is None]
        park_free_arms = [ParkArmsAction(arms=free_arms)] if free_arms else []
        keep_upright = [
            AlignPlanes(
                root_link=self.world.root,
                tip_link=held_body,
                tip_normal=Vector3.Z(reference_frame=held_body),
                goal_normal=Vector3.Z(reference_frame=self.world.root),
                threshold=self.upright_threshold,
            )
            for held_body in held_bodies.values()
            if held_body is not None
        ]
        return [self.navigate, *park_free_arms, *keep_upright]

    def _held_body(self, arm: Arm) -> Body | None:
        """
        :param arm: The arm to look at.
        :return: The body `arm` holds, or None if it holds nothing.
        """
        held_body = arm.end_effector.held_body
        if held_body is not None:
            return held_body
        pick_up = self._earlier_pick_up_still_holding(arm)
        if pick_up is None:
            return None
        return pick_up.grasp.graspable.root

    def _earlier_pick_up_still_holding(self, arm: Arm) -> PickUpAction | None:
        """
        :param arm: The arm to look at.
        :return: The latest pick-up with `arm` before this action whose object no
            placing between it and this action puts down, or None if there is none.
        """
        put_down = set()
        for earlier in self.statechart.get_preceding_nodes_by_type(self, Action):
            if isinstance(earlier, PlaceAction):
                put_down.add(earlier.object_designator.root)
            elif isinstance(earlier, PickUpAction) and earlier.arm is arm:
                if earlier.grasp.graspable.root in put_down:
                    return None
                return earlier
        return None
