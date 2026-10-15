from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING

from cramph.composites import Parallel
from cramph.node import StatechartNode
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types.spatial_types import Vector3

if TYPE_CHECKING:
    from semantic_digital_twin.world_description.world_entity import Body

# %% driving with held objects upright


@dataclass(eq=False, repr=False)
class CarryAction(Action):
    """
    Drives the robot's base to a pose while every object the robot holds keeps its
    z-axis pointing up.

    An object counts as held when it hangs below a gripper's tool frame, or when a pick-
    up earlier in the plan takes it and no placing puts it down again before this
    action.
    """

    navigate: NavigateAction
    """
    The drive, or an underspecified statement of it.
    """

    upright_threshold: float = field(default=AlignPlanes.threshold, kw_only=True)
    """
    Angle in radians between a held object's z-axis and the world's z-axis within which
    the object counts as upright.
    """

    def create_action_body(self) -> StatechartNode:
        keep_upright = [
            AlignPlanes(
                root_link=self.world.root,
                tip_link=held_body,
                tip_normal=Vector3.Z(reference_frame=held_body),
                goal_normal=Vector3.Z(reference_frame=self.world.root),
                threshold=self.upright_threshold,
            )
            for held_body in self._held_bodies()
        ]
        if not keep_upright:
            return self.navigate
        return Parallel([self.navigate, *keep_upright])

    def _held_bodies(self) -> list[Body]:
        """
        :return: The body each arm holds, for every arm that holds one.
        """
        held_bodies = []
        for arm in self.robot.all_arms:
            held_body = arm.end_effector.held_body
            if held_body is not None:
                held_bodies.append(held_body)
                continue
            pick_up = self._earlier_pick_up_still_holding(arm)
            if pick_up is not None:
                held_bodies.append(pick_up.grasp.graspable.root)
        return held_bodies

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
