"""
Tuning a world for physical simulation in MuJoCo: position servos on the degrees of
freedom that declare them, gravity compensation on a robot part's links, no contact
between a robot's own links, and contact parameters on the objects a robot handles.

A robot's joints are driven by servos rather than written straight into the simulation,
so the physics stays real: a servo pulls a joint towards the position it was commanded
to and gets there only as fast and as hard as its gains allow, and an object is held by
contact friction between the fingers alone rather than kinematically attached.
"""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
from typing_extensions import TYPE_CHECKING, Dict, Iterable, Optional

from semantic_digital_twin.adapters.multi_sim import (
    MujocoActuator,
    MujocoBody,
    MujocoGeom,
    MujocoSolverImpedance,
    MujocoSolverReference,
)
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionBetweenGroups,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connection_properties import ServoGains
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.geometry import ContactFriction
from semantic_digital_twin.world_description.world_entity import Actuator, Body

if TYPE_CHECKING:
    from semantic_digital_twin.robots.robot_parts import (
        AbstractRobot,
        AbstractRobotPart,
    )

# %% position servos


def servo_actuator(
    gains: ServoGains, degree_of_freedom: DegreeOfFreedom
) -> MujocoActuator:
    """
    The MuJoCo actuator that servos ``degree_of_freedom`` to a commanded position with
    ``gains``' PD law, clamped to its torque limit and to the degree of freedom's own
    position limits.

    :param gains: The servo's gains.
    :param degree_of_freedom: The degree of freedom the servo's control range is clamped
        to.
    :return: The actuator's MuJoCo definition.
    """
    limits = degree_of_freedom.limits
    return MujocoActuator(
        dynamics_type=mujoco.mjtDyn.mjDYN_NONE,
        gain_type=mujoco.mjtGain.mjGAIN_FIXED,
        gain_parameters=[gains.stiffness] + [0.0] * 9,
        bias_type=mujoco.mjtBias.mjBIAS_AFFINE,
        bias_parameters=[0.0, -gains.stiffness, -gains.damping] + [0.0] * 7,
        control_range=[limits.lower.position, limits.upper.position],
        force_range=[-gains.torque_limit, gains.torque_limit],
    )


def equip_with_servos(
    world: World, degrees_of_freedom: Iterable[DegreeOfFreedom]
) -> Dict[str, Actuator]:
    """
    Give every one of ``degrees_of_freedom`` that declares servo gains a position-servo
    actuator.

    :param world: The world to add the actuators to, modified in place.
    :param degrees_of_freedom: The degrees of freedom to equip; those without gains are
        skipped, and one named twice is equipped once.
    :return: Each driven degree of freedom's actuator, keyed by its name.
    """
    actuators_by_name: Dict[str, Actuator] = {}
    with world.modify_world():
        for degree_of_freedom in degrees_of_freedom:
            name = degree_of_freedom.name.name
            if degree_of_freedom.servo_gains is None or name in actuators_by_name:
                continue
            actuator = Actuator()
            actuator.add_dof(dof=degree_of_freedom)
            actuator.simulator_additional_properties.append(
                servo_actuator(degree_of_freedom.servo_gains, degree_of_freedom)
            )
            world.add_actuator(actuator=actuator)
            actuators_by_name[name] = actuator
    return actuators_by_name


def equip_for_mujoco(robot: AbstractRobot) -> Dict[str, Actuator]:
    """
    Prepare a mounted robot to be simulated physically: every joint a robot part knows a
    servo for declares it and gets a servo actuator, every arm and end-effector link is
    gravity-compensated, and the robot's own links are allowed to pass through each
    other.

    The robot's root is not among those links: for a stationary robot that is the table
    it stands on, which its fingers should keep colliding with.

    :param robot: The robot, already mounted in its world.
    :return: Each driven degree of freedom's actuator, keyed by its name.
    """
    world = robot._world
    robot.declare_servos()
    for robot_part in robot._robot_parts:
        robot_part.prepare_for_physical_simulation()
    for arm in robot.get_arms():
        compensate_gravity(world, arm)
        compensate_gravity(world, arm.end_effector)
    links = [body for body in robot.bodies_with_collision if body is not robot.root]
    with world.modify_world():
        world.collision_manager.add_ignore_collision_rule(
            AllowCollisionBetweenGroups(body_group_a=links, body_group_b=links)
        )
    return equip_with_servos(
        world,
        [
            connection.raw_dof
            for robot_part in robot._robot_parts
            for connection in robot_part.active_connections
            if isinstance(connection, ActiveConnection1DOF)
        ],
    )


# %% a robot part's own links


def compensate_gravity(
    world: World, robot_part: AbstractRobotPart, factor: float = 1.0
) -> None:
    """
    Give every link of ``robot_part`` MuJoCo's own gravity compensation.

    Without it, each link's servo spends part of its torque holding the link up instead
    of tracking its commanded position; a weak servo, such as a gripper's, has no
    authority against the uncompensated weight of the whole assembly it drives.

    :param world: The world to modify in place.
    :param robot_part: The robot part whose links are compensated.
    :param factor: How much of the gravity to compensate; ``1`` cancels it entirely.
    """
    with world.modify_world():
        for body in robot_part.bodies:
            body.simulator_property_or_default(
                MujocoBody
            ).gravitation_compensation_factor = factor


# %% contacts with objects


@dataclass(frozen=True)
class MujocoContactParameters:
    """
    The contact parameters one kind of geometry gets in MuJoCo: its friction and,
    optionally, how stiffly its contacts resolve.

    MuJoCo combines contact friction as the element-wise maximum of the two geoms in
    contact, so a contact is only as slippery as the grippier of its two sides.
    """

    friction: ContactFriction
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
            friction=ContactFriction(
                sliding=sliding_friction, torsional=0.05, rolling=0.001
            ),
            solver_reference=MujocoSolverReference(time_constant=0.008),
            solver_impedance=MujocoSolverImpedance(minimum=0.96, maximum=0.99),
        )

    @classmethod
    def surface(cls, sliding_friction: float = 0.3) -> MujocoContactParameters:
        """
        The friction of a surface loose objects rest on, with MuJoCo's own torsional and
        rolling defaults, since a surface is never pinched between fingers.

        :param sliding_friction: The sliding friction coefficient.
        :return: The parameters.
        """
        return cls(friction=ContactFriction(sliding=sliding_friction))

    def apply_to(self, bodies: Iterable[Body]) -> None:
        """
        Give every collision geometry of every body these parameters, in place: the
        friction as the geometry's own declaration, the solver settings as its MuJoCo
        property.

        :param bodies: The bodies to modify.
        """
        for body in bodies:
            for geometry in body.collision:
                geometry.friction = self.friction
                if self.solver_reference is None and self.solver_impedance is None:
                    continue
                mujoco_geom = geometry.simulator_property_or_default(MujocoGeom)
                if self.solver_reference is not None:
                    mujoco_geom.solver_reference = self.solver_reference
                if self.solver_impedance is not None:
                    mujoco_geom.solver_impedance = self.solver_impedance
