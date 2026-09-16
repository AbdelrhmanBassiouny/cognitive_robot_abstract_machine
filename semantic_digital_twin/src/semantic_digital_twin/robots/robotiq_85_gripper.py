from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from typing_extensions import Generic

from semantic_digital_twin.robots.robot_part_mixins import (
    HasTwoFingers,
    TGenericLeftFinger,
    TGenericRightFinger,
)
from semantic_digital_twin.robots.robot_parts import EndEffector
from semantic_digital_twin.world_description.connection_properties import (
    JointDynamics,
    JointServo,
    ServoGains,
)
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.world_entity import Body


@dataclass(eq=False)
class Robotiq85Gripper(
    EndEffector,
    HasTwoFingers[TGenericLeftFinger, TGenericRightFinger],
    Generic[TGenericLeftFinger, TGenericRightFinger],
    ABC,
):
    """
    A Robotiq 2F-85 parallel gripper: two fingers coupled by a mimic linkage, driven by
    the knuckle joint of the thumb.

    Knows what a grasp and a physical simulation need from it: the pads that meet an
    object, the joint that drives the fingers, how far that joint has to turn to close
    the pads to a given width, and the servo driving it.

    The servo is raised empirically, since no pre-tuned reference exists for the
    Robotiq 2F-85; its armature gives the coupled mechanism the numerical damping that
    keeps it from chattering under load.
    """

    @property
    def knuckle_joint(self) -> ActiveConnection1DOF:
        """
        The joint that actually drives the gripper; every other finger joint in the
        mimic linkage follows it.
        """
        return self.thumb.root.parent_connection

    def _setup_servos(self) -> None:
        for connection in self.active_connections:
            if not isinstance(connection, ActiveConnection1DOF):
                continue
            self._declare_servo(
                connection,
                JointServo(
                    gains=ServoGains(stiffness=100.0, damping=10.0, torque_limit=10.0),
                    dynamics=JointDynamics(armature=0.05),
                ),
            )
        self._compensate_gravity()

    @property
    def left_fingertip(self) -> Body:
        """
        The left fingertip pad's body.
        """
        return self.thumb.tip

    @property
    def right_fingertip(self) -> Body:
        """
        The right fingertip pad's body.
        """
        return self.finger.tip

    def knuckle_angle_for_half_width(
        self, target_half_width: float, iterations: int = 30
    ) -> float:
        """
        The knuckle's raw angle at which the fingertip pads' inner faces first reach
        ``target_half_width`` out from the gripper's own centreline: what to command the
        knuckle to for closing the fingers on an object of twice that width.

        Closing all the way on an object that is not perfectly centred between the
        fingers wedges it sideways rather than gripping it, so a grasp closes to the
        object's width instead. The pad's inner position decreases monotonically as the
        knuckle closes, so bisection converges reliably; the world's state is moved for
        the search and restored afterwards.

        :param target_half_width: The half-width, in metres, to close to.
        :param iterations: Bisection steps; 30 narrows the joint's own ~0.8 rad range to
            well under a micro-radian.
        :return: The raw angle.
        """
        limits = self.knuckle_joint.raw_dof.limits
        lower, upper = limits.lower.position, limits.upper.position
        with self._world.reset_state_context():
            if target_half_width >= self._pad_inner_x_at(lower):
                return lower
            if target_half_width <= self._pad_inner_x_at(upper):
                return upper
            for _ in range(iterations):
                midpoint = (lower + upper) / 2
                if self._pad_inner_x_at(midpoint) > target_half_width:
                    lower = midpoint
                else:
                    upper = midpoint
        return upper

    def _pad_inner_x_at(self, raw_angle: float) -> float:
        """
        Move the knuckle to a raw angle and read where the left pad's innermost point
        then sits along the closing axis.

        :param raw_angle: The knuckle angle to move to.
        :return: The pad's innermost x coordinate in the gripper's own frame.
        """
        self._world.state[self.knuckle_joint.raw_dof.id].position = raw_angle
        self._world.notify_state_change()
        self._world.update_forward_kinematics()
        return (
            self.left_fingertip.collision.as_bounding_box_collection_in_frame(self.root)
            .bounding_box()
            .min_x
        )
