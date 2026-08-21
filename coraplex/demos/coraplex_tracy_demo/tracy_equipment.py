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

from semantic_digital_twin.adapters.multi_sim import MujocoActuator, MujocoBody, MujocoGeom
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_parts import AbstractRobotPart
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    ActiveConnection1DOF,
    Connection6DoF,
)
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.geometry import Box, Color, Scale, Shape
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Actuator, Body


@dataclass(frozen=True)
class ServoGains:
    """
    How hard a position servo pulls its joint towards the angle it was given, and how
    much passive resistance its joint itself has.
    """

    stiffness: float
    """Restoring torque per radian away from the set point, in newton metres."""

    actuator_damping: float
    """Opposing torque per radian per second the servo itself applies, in newton metre
    seconds."""

    torque_limit: float
    """The largest torque the servo may exert, in newton metres."""

    joint_damping: float
    """Passive viscous damping of the joint itself, independent of the servo -- always
    resists motion, whether or not the servo is actively driving."""

    armature: float
    """Rotor inertia added to the joint, damping high-frequency numerical response
    without changing its real, low-frequency behaviour."""


_STIFFNESS = 5_000.0
_ACTUATOR_DAMPING = 500.0
_ARMATURE = 0.1
"""
Shared across every joint class below, matching MuJoCo Menagerie's own
``universal_robots_ur10e/ur10e.xml``: its ``<general gainprm="5000" biasprm="0 -5000
-500">`` and ``<joint armature="0.1">`` sit on the base ``ur10e`` default class, applying
identically to every joint regardless of size; only torque limit and the joint's own
passive damping are given separately per size class there.
"""

ARM_JOINT_SERVO: dict[str, ServoGains] = {
    # "size4" in ur10e.xml: the two shoulder joints, which carry the whole rest of the
    # arm's weight and so need the most torque and the most passive damping to settle
    # without ringing.
    "shoulder_pan_joint": ServoGains(_STIFFNESS, _ACTUATOR_DAMPING, 330.0, 10.0, _ARMATURE),
    "shoulder_lift_joint": ServoGains(_STIFFNESS, _ACTUATOR_DAMPING, 330.0, 10.0, _ARMATURE),
    # "size3" in ur10e.xml: the elbow.
    "elbow_joint": ServoGains(_STIFFNESS, _ACTUATOR_DAMPING, 150.0, 5.0, _ARMATURE),
    # "size2" in ur10e.xml: the three wrist joints, which carry only the gripper and so
    # need much less of either.
    "wrist_1_joint": ServoGains(_STIFFNESS, _ACTUATOR_DAMPING, 56.0, 2.0, _ARMATURE),
    "wrist_2_joint": ServoGains(_STIFFNESS, _ACTUATOR_DAMPING, 56.0, 2.0, _ARMATURE),
    "wrist_3_joint": ServoGains(_STIFFNESS, _ACTUATOR_DAMPING, 56.0, 2.0, _ARMATURE),
}
"""
Real, per-joint-size UR10e gains and torque limits, taken as-is from MuJoCo Menagerie's
own ``universal_robots_ur10e/ur10e.xml``, keyed by joint name with Tracy's own
``left_``/``right_`` prefix stripped.

Tracy's own UR10 (not UR10e) arms are close enough to reuse this directly. An earlier,
much stronger, flat (same number for every joint) tuning was used instead while Giskard
was still driving the joints; now that the joints are driven directly (see this module's
own docstring) that workaround is no longer needed, and these are the robot's own real
numbers.
"""


def _servo_tuning_for(joint_name: str) -> ServoGains:
    """
    The tuning a joint's servo is built with, by its (possibly ``left_``/``right_``-
    prefixed) name.

    :param joint_name: Name of the joint, e.g. ``"left_shoulder_pan_joint"``.
    :return: Its own tuning from :data:`ARM_JOINT_SERVO`.
    """
    unprefixed = joint_name.removeprefix("left_").removeprefix("right_")
    return ARM_JOINT_SERVO[unprefixed]


def joint_state_of_type(robot_part: AbstractRobotPart, state_type) -> JointState:
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
    of the way first" step needed here -- self-collision is excluded globally (see
    :func:`exclude_self_collision`), so the two arms sweeping through each other's space
    on the way to their own targets is not a concern.

    :param world: The world to configure, modified in place.
    :param robot: The robot to configure.
    """
    for arm in robot.get_arms():
        joint_state_of_type(arm.end_effector, GripperState.CLOSE).apply_to(world)
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


ROBOT_COLLISION_BIT = 1
"""
MuJoCo ``contype``/``conaffinity`` bit given to every one of Tracy's own collision
geoms by :func:`exclude_self_collision`.
"""

EXTERNAL_COLLISION_BIT = 2
"""
MuJoCo ``contype``/``conaffinity`` bit given to things Tracy is meant to actually touch
-- loose objects, a table, anything that is not the robot's own body.
"""


def _mujoco_geom_for(shape: Shape) -> MujocoGeom:
    """
    ``shape``'s own :class:`MujocoGeom` additional property, creating one if it has
    none yet.

    :class:`~semantic_digital_twin.adapters.multi_sim.MujocoGeomConverter` reads only
    the first ``MujocoGeom`` it finds on a shape, so a second, appended one would be
    silently ignored: callers must modify the returned instance in place rather than
    replacing it.

    :param shape: The shape to find or create a ``MujocoGeom`` on, modified in place if
        none exists yet.
    """
    existing = [
        additional_property
        for additional_property in shape.simulator_additional_properties
        if isinstance(additional_property, MujocoGeom)
    ]
    if existing:
        return existing[0]
    mujoco_geom = MujocoGeom()
    shape.simulator_additional_properties.append(mujoco_geom)
    return mujoco_geom


def exclude_self_collision(world: World, robot: Tracy) -> None:
    """
    Let the robot's own links pass through each other, without also excusing them from
    colliding with anything else.

    A description's links overlap wherever they meet; sweeping the left arm's shoulder
    through the roughly 150 degrees its own park pose needs swings it through several
    such overlaps (confirmed directly: with collision left unaddressed, every other
    joint reached its park target to within a few thousandths of a radian while the
    shoulder alone sat pinned at its starting angle the entire run, the signature of a
    real contact force its own servo -- even at 500N.m, well above any of
    :data:`ARM_JOINT_SERVO`'s own real torque limits -- could not push through).

    Gives every one of the robot's own collision geoms :data:`ROBOT_COLLISION_BIT` as
    both ``contype`` and ``conaffinity``: two robot geoms then never generate a contact
    (``ROBOT_COLLISION_BIT`` shares no bit with itself once excluded from
    ``conaffinity`` -- see the bit layout below), while a robot geom still collides
    normally with anything carrying :data:`EXTERNAL_COLLISION_BIT` (see
    :func:`add_cube`), since MuJoCo generates a contact whenever either geom's
    ``contype`` intersects the other's ``conaffinity``. An earlier version of this
    function stripped the robot's collision geometry entirely instead, which also
    stopped the gripper from ever touching anything it was meant to actually grasp.

    :param world: The world to relax, modified in place.
    :param robot: The robot to exclude self-collision on.
    """
    with world.modify_world():
        for body in robot.bodies_with_collision:
            for shape in body.collision:
                mujoco_geom = _mujoco_geom_for(shape)
                mujoco_geom.contype = ROBOT_COLLISION_BIT
                mujoco_geom.conaffinity = EXTERNAL_COLLISION_BIT


def add_cube(
    world: World, name: str, position: Point3, size: float, color: Color
) -> Body:
    """
    Add a free-standing cube with real collision geometry to the world, so it can be
    pushed, grasped, and stacked by real contact rather than teleported into place or
    kinematically attached to whatever is holding it.

    Its collision geom gets :data:`EXTERNAL_COLLISION_BIT`, and is allowed to touch
    both the robot (:data:`ROBOT_COLLISION_BIT`) and other external things, including
    another cube -- see :func:`exclude_self_collision`.

    :param world: The world to add the cube to, modified in place.
    :param name: Name of the cube.
    :param position: Where the cube starts, in the world root frame.
    :param size: Edge length of the cube, in metres.
    :param color: Colour of the cube.
    :return: The newly added cube.
    """
    cube = Body(name=PrefixedName(name))
    shape = Box(
        origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=cube),
        scale=Scale(size, size, size),
        color=color,
    )
    mujoco_geom = _mujoco_geom_for(shape)
    mujoco_geom.contype = EXTERNAL_COLLISION_BIT
    mujoco_geom.conaffinity = ROBOT_COLLISION_BIT | EXTERNAL_COLLISION_BIT
    geometry = ShapeCollection([shape], reference_frame=cube)
    cube.collision, cube.visual = geometry, geometry

    with world.modify_world():
        world.add_connection(
            Connection6DoF.create_with_dofs(
                world=world,
                parent=world.root,
                child=cube,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=position.x,
                    y=position.y,
                    z=position.z,
                    reference_frame=world.root,
                ),
            )
        )
    return cube


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
        bias_parameters=[0.0, -gains.stiffness, -gains.actuator_damping] + [0.0] * 7,
        control_range=[limits.lower.position, limits.upper.position],
        force_range=[-gains.torque_limit, gains.torque_limit],
    )


def equip_arms_with_servos(world: World, robot: Tracy) -> Dict[str, Actuator]:
    """
    Give every joint of both arms a position-servo actuator, its own passive damping,
    and armature, driven directly via
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
                gains = _servo_tuning_for(dof.name.name)
                connection.dynamics.armature = gains.armature
                connection.dynamics.damping = gains.joint_damping
                actuator = Actuator()
                actuator.add_dof(dof=dof)
                actuator.simulator_additional_properties.append(
                    _servo_actuator(gains, dof)
                )
                world.add_actuator(actuator=actuator)
                actuators_by_joint_name[dof.name.name] = actuator
    return actuators_by_joint_name
