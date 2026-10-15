from __future__ import annotations

from dataclasses import dataclass, field

from cramph.composites import Parallel
from cramph.node import StatechartNode
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.spatial_types.spatial_types import Vector3

# %% which way a held object's upright axis points in its gripper


@dataclass
class HeldObjectAxis:
    """
    The z-axis of an object an arm holds, as seen from the gripper holding it.
    """

    arm: Arm
    """
    The arm whose gripper holds the object.
    """

    tool_V_object_z: Vector3
    """
    The object's z-axis, expressed in the tool frame of :attr:`arm`'s end effector.
    """


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
                tip_link=axis.arm.end_effector.tool_frame,
                tip_normal=axis.tool_V_object_z,
                goal_normal=Vector3.Z(reference_frame=self.world.root),
                threshold=self.upright_threshold,
            )
            for axis in self._held_object_axes()
        ]
        if not keep_upright:
            return self.navigate
        return Parallel([self.navigate, *keep_upright])

    def _held_object_axes(self) -> list[HeldObjectAxis]:
        """
        :return: The z-axis of the object each arm holds, for every arm that holds one.
        """
        axes = []
        for arm in self.robot.all_arms:
            held_body = arm.end_effector.held_body
            if held_body is not None:
                axes.append(
                    HeldObjectAxis(
                        arm,
                        self.world.transform(
                            Vector3.Z(reference_frame=held_body),
                            arm.end_effector.tool_frame,
                        ),
                    )
                )
                continue
            pick_up = self._earlier_pick_up_still_holding(arm)
            if pick_up is not None:
                axes.append(HeldObjectAxis(arm, self._object_z_in_tool_frame(pick_up)))
        return axes

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

    @staticmethod
    def _object_z_in_tool_frame(pick_up: PickUpAction) -> Vector3:
        """
        :param pick_up: The pick-up that takes the object.
        :return: The z-axis of the object `pick_up` takes, in the tool frame of its
            arm's end effector once the gripper sits at the grasp.
        """
        tool_R_object = (
            pick_up.arm.end_effector.tool_R_grasp
            @ pick_up.grasp.grasp_pose.rotation_matrix.inverse()
        )
        return tool_R_object @ Vector3.Z()
