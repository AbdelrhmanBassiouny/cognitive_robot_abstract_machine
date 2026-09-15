"""
Tuning a world for physical simulation in MuJoCo: position servos on a robot's joints,
gravity compensation and self-collision exclusion on its links, and contact parameters on
the objects it handles.

A robot's joints are driven by servos rather than written straight into the simulation,
so the physics stays real: a servo pulls a joint towards the angle it was commanded to
and gets there only as fast and as hard as its gains allow, and an object is held by
contact friction between the fingers alone rather than kinematically attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import mujoco
from typing_extensions import TYPE_CHECKING, Dict, Iterable, Optional

from semantic_digital_twin.adapters.multi_sim import (
    MujocoActuator,
    MujocoBody,
    MujocoContactFriction,
    MujocoGeom,
    MujocoSolverImpedance,
    MujocoSolverReference,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import Actuator, Body

if TYPE_CHECKING:
    from semantic_digital_twin.robots.robot_parts import AbstractRobot

# %% position servos


@dataclass(frozen=True)
class ServoGains:
    """
    How hard a position servo pulls its joint towards the angle it was given, and how
    much passive resistance the joint itself has.
    """

    stiffness: float
    """
    Restoring torque per radian away from the set point, in newton metres.
    """

    actuator_damping: float
    """
    Opposing torque per radian per second the servo itself applies, in newton metre
    seconds.
    """

    torque_limit: float
    """
    The largest torque the servo may exert, in newton metres.
    """

    joint_damping: float = 0.0
    """
    Passive viscous damping of the joint itself, independent of the servo; it resists
    motion whether or not the servo is driving.
    """

    armature: float = 0.0
    """
    Rotor inertia added to the joint, which damps high-frequency numerical response
    without changing the joint's real, low-frequency behaviour.
    """

    def position_servo(self, degree_of_freedom: DegreeOfFreedom) -> MujocoActuator:
        """
        A MuJoCo actuator that servos ``degree_of_freedom`` to a commanded position with
        a PD law, clamped to these gains' torque limit and to the degree of freedom's own
        position limits.

        :param degree_of_freedom: The degree of freedom the servo's control range is
            clamped to.
        :return: The actuator's MuJoCo definition.
        """
        limits = degree_of_freedom.limits
        return MujocoActuator(
            dynamics_type=mujoco.mjtDyn.mjDYN_NONE,
            gain_type=mujoco.mjtGain.mjGAIN_FIXED,
            gain_parameters=[self.stiffness] + [0.0] * 9,
            bias_type=mujoco.mjtBias.mjBIAS_AFFINE,
            bias_parameters=[0.0, -self.stiffness, -self.actuator_damping] + [0.0] * 7,
            control_range=[limits.lower.position, limits.upper.position],
            force_range=[-self.torque_limit, self.torque_limit],
        )


def equip_with_servos(
    world: World,
    connections: Iterable[ActiveConnection1DOF],
    gains_for: Dict[str, ServoGains],
) -> Dict[str, Actuator]:
    """
    Give every one of ``connections`` a position-servo actuator, its own passive damping
    and armature.

    A mimic linkage, such as a gripper's underactuated four-bar mechanism, shares one
    raw degree of freedom across several connections. Each such degree of freedom gets
    one actuator, since a second on the same one would apply a competing servo force
    rather than drive anything new. Armature and damping live on each connection's own
    MuJoCo joint, so they are set on every connection regardless: a mimicked joint left
    without armature starves the whole coupled mechanism of the numerical damping that
    keeps it from chattering under load.

    :param world: The world to add the actuators to, modified in place.
    :param connections: The connections to equip.
    :param gains_for: Each connection's gains, by the name of its raw degree of freedom.
    :return: Each driven degree of freedom's actuator, keyed by that name.
    """
    actuators_by_joint_name: Dict[str, Actuator] = {}
    equipped: set[DegreeOfFreedom] = set()
    with world.modify_world():
        for connection in connections:
            degree_of_freedom = connection.raw_dof
            gains = gains_for[degree_of_freedom.name.name]
            connection.dynamics.armature = gains.armature
            connection.dynamics.damping = gains.joint_damping
            if degree_of_freedom in equipped:
                continue
            equipped.add(degree_of_freedom)
            actuator = Actuator()
            actuator.add_dof(dof=degree_of_freedom)
            actuator.simulator_additional_properties.append(
                gains.position_servo(degree_of_freedom)
            )
            world.add_actuator(actuator=actuator)
            actuators_by_joint_name[degree_of_freedom.name.name] = actuator
    return actuators_by_joint_name


# %% a robot's own links


class CollisionGroup(IntEnum):
    """
    MuJoCo ``contype``/``conaffinity`` bits telling apart what may touch what: a contact
    between two geoms is generated only if one's ``contype`` shares a bit with the
    other's ``conaffinity``.
    """

    ROBOT = 1
    """
    A robot's own moving links; see :func:`exclude_self_collision`.
    """

    EXTERNAL = 2
    """
    Things a robot is meant to actually touch: loose objects, a table, anything that is
    not the robot's own body.
    """


def compensate_gravity(world: World, robot: AbstractRobot) -> None:
    """
    Give every arm and end-effector link of ``robot`` MuJoCo's own gravity compensation.

    Without it, each link's servo spends part of its torque holding the link up instead
    of tracking its commanded target. The end effectors are covered too: an end
    effector is its own robot part hanging off the arm's tip, not part of the arm's
    active connections, and its comparatively weak servo has no authority against the
    whole uncompensated finger assembly's weight.

    :param world: The world to modify in place.
    :param robot: The robot to compensate.
    """
    with world.modify_world():
        for arm in robot.get_arms():
            for body in arm.bodies + arm.end_effector.bodies:
                body.simulator_property_or_default(
                    MujocoBody
                ).gravitation_compensation_factor = 1.0


def exclude_self_collision(world: World, robot: AbstractRobot) -> None:
    """
    Let ``robot``'s own links pass through each other, without excusing them from
    colliding with anything else.

    A description's links overlap wherever they meet, and sweeping an arm through its
    own park pose swings it through several such overlaps, which a position servo cannot
    push through by itself. Every one of the robot's collision geoms gets
    :attr:`CollisionGroup.ROBOT` as ``contype`` and :attr:`CollisionGroup.EXTERNAL` as
    ``conaffinity``: two robot geoms then never generate a contact, while a robot geom
    still collides with anything external.

    The robot's root is skipped: for a stationary robot that is the table it stands on,
    which is exactly the kind of thing it should keep colliding with.

    :param world: The world to modify in place.
    :param robot: The robot to exclude self-collision on.
    """
    with world.modify_world():
        for body in robot.bodies_with_collision:
            if body is robot.root:
                continue
            for shape in body.collision:
                mujoco_geom = shape.simulator_property_or_default(MujocoGeom)
                mujoco_geom.contype = CollisionGroup.ROBOT
                mujoco_geom.conaffinity = CollisionGroup.EXTERNAL


# %% contacts with objects


@dataclass(frozen=True)
class MujocoContactParameters:
    """
    The contact parameters one kind of geometry gets in MuJoCo: its friction and,
    optionally, how stiffly its contacts resolve.

    MuJoCo combines contact friction as the element-wise maximum of the two geoms in
    contact, so a contact is only as slippery as the grippier of its two sides.
    """

    friction: MujocoContactFriction
    """
    Sliding, torsional and rolling friction.
    """

    solver_reference: Optional[MujocoSolverReference] = None
    """
    How stiff and how damped the contacts are, or ``None`` to leave the geometry's own.
    """

    solver_impedance: Optional[MujocoSolverImpedance] = None
    """
    How hard the contacts push back as they are violated, or ``None`` to leave the
    geometry's own.
    """

    @classmethod
    def grasped_object(cls, sliding_friction: float = 0.3) -> MujocoContactParameters:
        """
        The parameters that let a gripper pick an object up and hold it by friction.

        The contacts are stiffer and harder than MuJoCo's defaults, since a soft contact
        lets a pinched object sink into the fingers and slip back out as the arm lifts.
        The torsional and rolling friction are raised above MuJoCo's defaults to keep a
        held object from pivoting between the pads.

        :param sliding_friction: The sliding friction coefficient; ``0.3`` approximates
            painted wood or plastic.
        :return: The parameters.
        """
        return cls(
            friction=MujocoContactFriction(
                sliding=sliding_friction, torsional=0.05, rolling=0.001
            ),
            solver_reference=MujocoSolverReference(time_constant=0.008),
            solver_impedance=MujocoSolverImpedance(minimum=0.96, maximum=0.99),
        )

    @classmethod
    def surface(cls, sliding_friction: float = 0.3) -> MujocoContactParameters:
        """
        The friction of a surface loose objects rest on, with MuJoCo's own torsional
        and rolling defaults, since a surface is never pinched between fingers.

        :param sliding_friction: The sliding friction coefficient.
        :return: The parameters.
        """
        return cls(friction=MujocoContactFriction(sliding=sliding_friction))

    def apply_to(self, bodies: Iterable[Body]) -> None:
        """
        Give every collision geometry of every body these parameters, in place.

        :param bodies: The bodies to modify.
        """
        for body in bodies:
            for geometry in body.collision:
                mujoco_geom = geometry.simulator_property_or_default(MujocoGeom)
                mujoco_geom.friction = self.friction
                if self.solver_reference is not None:
                    mujoco_geom.solver_reference = self.solver_reference
                if self.solver_impedance is not None:
                    mujoco_geom.solver_impedance = self.solver_impedance


def make_touchable(body: Body, contact: MujocoContactParameters) -> None:
    """
    Let a loose object's collision geometry touch both a robot and other loose objects,
    with the given contact parameters.

    :param body: The object, modified in place.
    :param contact: The contact parameters its geometry gets.
    """
    for shape in body.collision:
        mujoco_geom = shape.simulator_property_or_default(MujocoGeom)
        mujoco_geom.contype = CollisionGroup.EXTERNAL
        mujoco_geom.conaffinity = CollisionGroup.ROBOT | CollisionGroup.EXTERNAL
    contact.apply_to([body])
