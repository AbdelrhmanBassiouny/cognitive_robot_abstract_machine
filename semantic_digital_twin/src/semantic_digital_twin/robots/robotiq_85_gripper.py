from __future__ import annotations

from abc import ABC
from copy import deepcopy
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
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import Body


@dataclass
class KnuckleScan:
    """
    Where the left fingertip pad sits at a raw knuckle angle, on an isolated scratch
    world moved directly rather than through the caller's own world.
    """

    scratch_world: World
    """
    The scratch copy of the world the scan moves; never the caller's own.
    """

    raw_dof: DegreeOfFreedom
    """
    The scratch gripper's knuckle degree of freedom.
    """

    left_fingertip: Body
    """
    The scratch gripper's left fingertip pad.
    """

    gripper_root: Body
    """
    The scratch gripper's root, the frame the pad's position is read in.
    """

    def inner_x(self, raw_angle: float) -> float:
        """
        The left pad's innermost point along the closing axis at one raw angle.

        :param raw_angle: The knuckle angle to move the scratch world to.
        :return: The pad's innermost x coordinate in the gripper's own frame.
        """
        self.scratch_world.state[self.raw_dof.id].position = raw_angle
        self.scratch_world.notify_state_change()
        self.scratch_world.update_forward_kinematics()
        return (
            self.left_fingertip.collision.as_bounding_box_collection_in_frame(
                self.gripper_root
            )
            .bounding_box()
            .min_x
        )


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
    """

    @property
    def knuckle_joint(self) -> ActiveConnection1DOF:
        """
        The joint that actually drives the gripper; every other finger joint in the
        mimic linkage follows it.
        """
        return self.thumb.root.parent_connection

    @property
    def finger_velocity_limit(self) -> float:
        """
        Velocity limit, in radians per second, every finger joint gets instead of the
        description's own: that one is roughly ``0.032`` rad/s, takes about 25 seconds
        to close the gripper, and no hardware reference backs it.

        ``1.0`` converges cleanly under joint-space planning, while ``2.0`` was measured
        to leave the QP solver settled short of its target.
        """
        return 1.0

    @property
    def finger_servo(self) -> JointServo:
        """
        The servo every finger joint is driven by, raised empirically since no pre-tuned
        reference exists for the Robotiq 2F-85, with the armature that gives the coupled
        mechanism the numerical damping keeping it from chattering under load.
        """
        return JointServo(
            gains=ServoGains(stiffness=100.0, damping=10.0, torque_limit=10.0),
            dynamics=JointDynamics(armature=0.05),
        )

    def _setup_servos(self) -> None:
        for connection in self.active_connections:
            if not isinstance(connection, ActiveConnection1DOF):
                continue
            self.finger_servo.apply_to(connection)
        self._compensate_gravity()

    def prepare_for_physical_simulation(self) -> None:
        """
        Give every finger joint's degree of freedom :attr:`finger_velocity_limit`,
        overriding the description's own conservative one: kinematic planning has no
        reason to trust it, but a physically simulated servo needs the room to actually
        reach a commanded position within a plan's own convergence tolerance.
        """
        for connection in self.active_connections:
            if not isinstance(connection, ActiveConnection1DOF):
                continue
            connection.raw_dof.limits.upper.velocity = self.finger_velocity_limit
            connection.raw_dof.limits.lower.velocity = -self.finger_velocity_limit

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
        knuckle closes, so bisection against an isolated scratch copy of the world
        converges reliably; the world itself is never modified.

        :param target_half_width: The half-width, in metres, to close to.
        :param iterations: Bisection steps; 30 narrows the joint's own ~0.8 rad range to
            well under a micro-radian.
        :return: The raw angle.
        """
        scratch_world = deepcopy(self._world)
        scratch_gripper = scratch_world.get_semantic_annotation_by_id(self.id)
        scan = KnuckleScan(
            scratch_world=scratch_world,
            raw_dof=scratch_gripper.knuckle_joint.raw_dof,
            left_fingertip=scratch_gripper.left_fingertip,
            gripper_root=scratch_gripper.root,
        )
        lower = scan.raw_dof.limits.lower.position
        upper = scan.raw_dof.limits.upper.position
        if target_half_width >= scan.inner_x(lower):
            return lower
        if target_half_width <= scan.inner_x(upper):
            return upper
        for _ in range(iterations):
            midpoint = (lower + upper) / 2
            if scan.inner_x(midpoint) > target_half_width:
                lower = midpoint
            else:
                upper = midpoint
        return upper
