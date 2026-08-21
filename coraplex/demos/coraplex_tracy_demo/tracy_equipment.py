"""
Equip both of Tracy's arms to be driven by direct MuJoCo actuator control (see
:mod:`real_time_simulation`) rather than through Giskard.

Physically simulating the joints Giskard actively commands, and letting Giskard itself
drive them via ``ParkArmsAction``, was tried first and traced all the way down to a real
architectural gap, not a tuning problem: Giskard's own QP control loop reads
``world.state`` as its belief of the robot's current position, but for a
``physically_simulated`` DOF that same state is also written by Giskard's own prior
command (see :mod:`~semantic_digital_twin.adapters.multi_sim`'s
``_write_1dof_to_qpos``), not exclusively by MuJoCo's true physics readback -- and that
same background-threaded readback makes any direct caller's own read of ``world.state``
a race too. Reading the true position directly from the simulator (bypassing
``world.state`` entirely) showed the arm's joints sitting essentially motionless under
an active ``ParkArmsAction``: Giskard was satisfied by its own prior write, not by the
robot actually having moved. Driving the actuators directly via
:meth:`~real_time_simulation.RealTimeSimulation.command` (added on
``ichumuh/cognitive_robot_abstract_machine@t-task-force``, commit ``f0d0e967a``)
sidesteps Giskard, and stepping physics from the calling thread (rather than the
background thread :class:`~semantic_digital_twin.adapters.multi_sim.MujocoSim` normally
runs on its own) sidesteps the read race, entirely.
"""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
from typing_extensions import Dict

from semantic_digital_twin.adapters.multi_sim import MujocoActuator, MujocoBody
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.robots.robot_parts import AbstractRobotPart
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Actuator


@dataclass(frozen=True)
class ServoGains:
    """
    How hard a position servo pulls its joint towards the angle it was given.
    """

    stiffness: float
    """Restoring torque per radian away from the set point, in newton metres."""

    damping: float
    """Opposing torque per radian per second, in newton metre seconds."""

    torque_limit: float
    """The largest torque the servo may exert, in newton metres."""


ARM_SERVO = ServoGains(stiffness=300_000.0, damping=6_000.0, torque_limit=500.0)
"""
Gains for an arm's own joints, taken as-is from ``t-task-force``'s own
``experiments/push_t/tracy_scene.py::ARM_SERVO``.

A servo holds its pose only as far off it as the load it carries divided by its
stiffness, so an arm this heavy needs a large one to settle within a centimetre of where
it was sent. Past roughly ten times this the servos ring at the simulation's millisecond
step. The torque limit is around the UR10e's own, which is enough to hold the arm up and
push against real loads without the arm itself being what gives way first.
"""


def _joint_state_of_type(robot_part: AbstractRobotPart, state_type) -> JointState:
    """
    The one of ``robot_part``'s own joint states with the given ``state_type``.

    :param robot_part: The robot part (an arm or a gripper) to search.
    :param state_type: The state type to find, e.g. :attr:`StaticJointState.PARK`.
    """
    return next(
        joint_state
        for joint_state in robot_part.joint_states
        if joint_state.state_type == state_type
    )


def close_grippers(world: World, robot: Tracy) -> None:
    """
    Close both grippers, before the simulation starts.

    Both arms are driven from the URDF's own zero pose to their own park target (see
    :mod:`demo`), so unlike an idle arm left in a fixed pose, there is no "stand it out
    of the way first" step needed here -- collision geometry is stripped globally (see
    :func:`strip_collision_geometry`), so the two arms sweeping through each other's
    space on the way to their own targets is not a concern.

    :param world: The world to configure, modified in place.
    :param robot: The robot to configure.
    """
    for arm in robot.get_arms():
        _joint_state_of_type(arm.end_effector, GripperState.CLOSE).apply_to(world)
    world.notify_state_change()


def apply_gravity_compensation(world: World, robot: Tracy) -> None:
    """
    Give every arm link MuJoCo's own gravity compensation.

    Without it, each arm's own position servo would have to spend part of its available
    torque fighting gravity instead of tracking its commanded target.

    :param world: The world to modify in place.
    :param robot: The robot to compensate.
    """
    with world.modify_world():
        for arm in robot.get_arms():
            for connection in arm.active_connections:
                if not isinstance(connection, ActiveConnection1DOF):
                    continue
                connection.child.simulator_additional_properties.append(
                    MujocoBody(gravitation_compensation_factor=1.0)
                )


def strip_collision_geometry(world: World, robot: Tracy) -> None:
    """
    Remove every one of the robot's own collision shapes.

    A description's links overlap wherever they meet; sweeping the left arm's shoulder
    through the roughly 150 degrees its own park pose needs swings it through several
    such overlaps (confirmed directly: with collision geometry left in, every other
    joint reached its park target to within a few thousandths of a radian while the
    shoulder alone sat pinned at its starting angle the entire run, the signature of a
    real contact force its own servo -- even at :data:`ARM_SERVO`'s own torque limit --
    could not push through).

    Removing the geometry outright is safe for this scene specifically because nothing
    else in it has collision geometry to check against either (no floor, no loose
    object): once something is added for the robot to actually interact with, this needs
    to become a real per-pair exclusion instead of a blanket one.

    :param world: The world to relax, modified in place.
    :param robot: The robot to strip collision geometry from.
    """
    with world.modify_world():
        for body in robot.bodies_with_collision:
            body.collision = ShapeCollection()


def _servo_actuator(gains: ServoGains, dof: DegreeOfFreedom) -> MujocoActuator:
    """
    Build a MuJoCo actuator that servos ``dof`` to a commanded position with a PD law,
    clamped to ``gains``' own torque limit and ``dof``'s own position limits.

    :param gains: Gains and torque clamp to build the servo with.
    :param dof: The degree of freedom the servo's control range is clamped to.
    """
    limits = dof.limits
    return MujocoActuator(
        dynamics_type=mujoco.mjtDyn.mjDYN_NONE,
        gain_type=mujoco.mjtGain.mjGAIN_FIXED,
        gain_parameters=[gains.stiffness] + [0.0] * 9,
        bias_type=mujoco.mjtBias.mjBIAS_AFFINE,
        bias_parameters=[0.0, -gains.stiffness, -gains.damping] + [0.0] * 7,
        control_range=[limits.lower.position, limits.upper.position],
        force_range=[-gains.torque_limit, gains.torque_limit],
    )


def equip_arms_with_servos(world: World, robot: Tracy) -> Dict[str, Actuator]:
    """
    Give every joint of both arms a position-servo actuator, driven directly via
    :meth:`~real_time_simulation.RealTimeSimulation.command` rather than through
    Giskard.

    :param world: The world to add the actuators to, modified in place.
    :param robot: The robot whose arms are driven.
    :return: Each driven degree of freedom's own actuator, keyed by joint name.
    """
    actuators_by_joint_name: Dict[str, Actuator] = {}
    with world.modify_world():
        for arm in robot.get_arms():
            for connection in arm.active_connections:
                if not isinstance(connection, ActiveConnection1DOF):
                    continue
                dof = connection.raw_dof
                actuator = Actuator()
                actuator.add_dof(dof=dof)
                actuator.simulator_additional_properties.append(
                    _servo_actuator(ARM_SERVO, dof)
                )
                world.add_actuator(actuator=actuator)
                actuators_by_joint_name[dof.name.name] = actuator
    return actuators_by_joint_name
