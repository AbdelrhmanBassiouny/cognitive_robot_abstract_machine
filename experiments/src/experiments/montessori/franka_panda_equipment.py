"""
Read the Franka Emika Panda's description out of this repo's own MJCF for it, and equip
it to be driven by MuJoCo's own physics (position-servo actuators, gravity compensation,
and contact friction) rather than kinematically teleported -- mirroring how
``coraplex/demos/coraplex_panda_demo/demo.py`` already drives the same robot for its
cube-stacking task, generalized here to however many loose Montessori shapes there are.

No ROS package exists for the Panda in this repository (see
:meth:`~semantic_digital_twin.robots.panda.Panda.get_ros_file_path`), so
:func:`parse_panda` reads it out of the one MJCF this repo already has for it instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mujoco
from typing_extensions import Iterable, Mapping, Tuple

from semantic_digital_twin.adapters.mjcf import MJCFParser
from semantic_digital_twin.adapters.multi_sim import (
    MujocoActuator,
    MujocoBody,
    MujocoGeom,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.panda import Panda
from semantic_digital_twin.robots.panda_assets import PandaMeshAssets
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import Actuator, Body

PANDA_SCENE_PATH = (
    Path(__file__).resolve().parents[4]
    / "coraplex"
    / "demos"
    / "coraplex_panda_demo"
    / "stacking_scene.xml"
)
"""
The one MJCF this repo has for the Panda: its body tree, gripper, and mesh references,
shared with ``coraplex_panda_demo``'s own cube-stacking demo.
"""

PANDA_SCENE_BODIES_TO_DISCARD = frozenset(
    {"target", "cube0", "cube1", "cube2", "cube3", "floor", "stack_pad"}
)
"""
Bodies of :data:`PANDA_SCENE_PATH` that belong to its own cube-stacking task rather than
to the robot, dropped so only the Panda itself is merged into another scene.
"""

PANDA_MOUNT_ROOT_NAME = PrefixedName("panda_mount", "montessori")
"""
Name given to the parsed Panda's own world root once merged, so it never collides with
a merge target's own root.
"""


def parse_panda() -> World:
    """
    Read the Panda out of :data:`PANDA_SCENE_PATH`, without the cube-stacking task it
    shares that file with, and without any actuator: an actuator parsed into one world
    cannot be merged into another (see
    :meth:`~experiments.montessori.world.MontessoriWorld.mount_stationary_robot`), and
    :func:`equip_panda_for_physical_simulation` installs its own once the Panda is
    mounted.

    :return: A world holding only the Panda's body tree.
    """
    # The scene's meshes are tens of megabytes and are not kept in the repository, so a
    # checkout that has never run a Panda demo has none of them.
    PandaMeshAssets(scene=PANDA_SCENE_PATH).download_if_missing()
    panda_world = MJCFParser(str(PANDA_SCENE_PATH)).parse()
    with panda_world.modify_world():
        for body in [
            body
            for body in panda_world.bodies
            if body.name.name in PANDA_SCENE_BODIES_TO_DISCARD
        ]:
            panda_world.remove_kinematic_structure_entity(body)
        for actuator in list(panda_world.actuators):
            panda_world.remove_actuator(actuator)
        panda_world.root.name = PANDA_MOUNT_ROOT_NAME
    return panda_world


@dataclass(frozen=True)
class JointServoTuning:
    """
    The gains and force clamp one joint's position-servo actuator is built with.
    """

    position_gain: float
    """
    Proportional gain of the servo.
    """

    velocity_gain: float
    """
    Derivative (damping) gain of the servo.
    """

    force_range: Tuple[float, float]
    """
    Force clamp of the servo.
    """


DEFAULT_JOINT_SERVO_TUNING = JointServoTuning(
    position_gain=2000.0, velocity_gain=200.0, force_range=(-12.0, 12.0)
)
"""
Tuning for joints 5-7 (the wrist), read off :data:`PANDA_SCENE_PATH`'s own ``<actuator>``
block -- the real ``mujoco_menagerie`` Panda gains, not the HSR's constants in
:mod:`experiments.montessori.montessori_demo`: its links carry different inertias, and
driven at the HSR's gains the Panda oscillates around a pose it is merely holding.
"""

PANDA_JOINT_SERVO_TUNING: Mapping[str, JointServoTuning] = {
    "joint1": JointServoTuning(4500.0, 450.0, (-87.0, 87.0)),
    "joint2": JointServoTuning(4500.0, 450.0, (-87.0, 87.0)),
    "joint3": JointServoTuning(3500.0, 350.0, (-87.0, 87.0)),
    "joint4": JointServoTuning(3500.0, 350.0, (-87.0, 87.0)),
    "/finger_joint1": JointServoTuning(1000.0, 100.0, (-100.0, 100.0)),
}
"""
Per-joint tuning overriding :data:`DEFAULT_JOINT_SERVO_TUNING`, keyed by joint name (see
:func:`_servo_tuning_for`). The finger entry drives each finger's own degree of freedom
(see :func:`equip_panda_for_physical_simulation`) directly in metres, so only its gains
carry over from the scene's own tendon-driven actuator, not that actuator's ``0..255``
control range -- and only after that actuator's own 10x stiffness fix (``biasprm``
``100`` -> ``1000`` N/m, see :data:`PANDA_SCENE_PATH`'s own comment on it): the squeeze
force a position servo can apply to a grasped object is stiffness times commanded
penetration, and at 100 N/m holding a light grasped shape needs several millimetres of
penetration -- comparable to the shapes' own half-widths -- which wedges it out
sideways instead of gripping it.
"""

GRASP_FRICTION = [1.0, 0.05, 0.001]
"""
Contact friction (sliding, torsional, rolling; see
:attr:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom.friction`) given to every
loose shape's collision geometry, matching the cube in
``coraplex_panda_demo``'s own grasping scene, which the Panda picks up and stacks
reliably.
"""

GRASP_SOLVER_REFERENCE = [0.008, 1.0]
"""
Contact solver reference (see
:attr:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom.solver_reference`) given to
every loose shape, matching ``coraplex_panda_demo``'s cube (``solref="0.008"``).

Stiffer than MuJoCo's own default (``0.02``): a soft contact lets a pinched shape sink
into the fingers and then slip back out as the arm lifts, rather than being held solidly
between them.
"""

GRASP_SOLVER_IMPEDANCE = [0.96, 0.99, 0.001, 0.5, 2.0]
"""
Contact solver impedance (see
:attr:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom.solver_impedance`) given to
every loose shape, matching ``coraplex_panda_demo``'s cube (``solimp="0.96 0.99"``, the
remaining three values MuJoCo's own defaults).

Harder than MuJoCo's own default (``0.9 0.95``), for the same reason as
:data:`GRASP_SOLVER_REFERENCE`.
"""

ARM_JOINT_ARMATURE = 0.1
"""
Rotor inertia (:attr:`~semantic_digital_twin.world_description.connection_properties.JointDynamics.armature`)
added to every physically simulated arm joint, matching the real Panda's own declared
armature (``armature="0.1"`` on :data:`PANDA_SCENE_PATH`'s ``/panda`` joint default).
"""


def _servo_tuning_for(joint_name: str) -> JointServoTuning:
    """
    The tuning a joint's servo is built with, by name.

    :param joint_name: Name of the joint.
    :return: Its own tuning from :data:`PANDA_JOINT_SERVO_TUNING`, or
        :data:`DEFAULT_JOINT_SERVO_TUNING` if it has none.
    """
    return PANDA_JOINT_SERVO_TUNING.get(joint_name, DEFAULT_JOINT_SERVO_TUNING)


def _position_servo_actuator(tuning: JointServoTuning) -> MujocoActuator:
    """
    Build a MuJoCo actuator that servos its degree of freedom to a commanded position
    with a PD law, resisting gravity and contacts.

    :param tuning: Gains and force clamp to build the servo with.
    """
    return MujocoActuator(
        dynamics_type=mujoco.mjtDyn.mjDYN_NONE,
        dynamics_parameters=[1.0] + [0.0] * 9,
        gain_type=mujoco.mjtGain.mjGAIN_FIXED,
        gain_parameters=[tuning.position_gain] + [0.0] * 9,
        bias_type=mujoco.mjtBias.mjBIAS_AFFINE,
        bias_parameters=[0.0, -tuning.position_gain, -tuning.velocity_gain] + [0.0] * 7,
        force_limited=mujoco.mjtLimited.mjLIMITED_TRUE,
        force_range=list(tuning.force_range),
    )


def _add_actuator(world: World, dof: DegreeOfFreedom, tuning: JointServoTuning) -> None:
    """
    Add a :func:`_position_servo_actuator` for ``dof`` to ``world``.

    :param world: The world to add the actuator to, modified in place.
    :param dof: The degree of freedom to drive.
    :param tuning: Gains and force clamp to build the servo with.
    """
    actuator = Actuator()
    actuator.add_dof(dof=dof)
    actuator.simulator_additional_properties.append(_position_servo_actuator(tuning))
    world.add_actuator(actuator=actuator)


def apply_grasp_contact_parameters(shapes: Iterable[Body]) -> None:
    """
    Give every body in ``shapes`` the contact parameters that let the Panda pick it up
    and hold it: the friction, solver reference, and solver impedance of
    ``coraplex_panda_demo``'s own reliably-grasped cube (see :data:`GRASP_FRICTION`,
    :data:`GRASP_SOLVER_REFERENCE`, :data:`GRASP_SOLVER_IMPEDANCE`).

    An existing :class:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom` on a
    geometry is modified in place rather than a second one appended:
    :class:`~semantic_digital_twin.adapters.multi_sim.MujocoBuilder` reads only the first
    ``MujocoGeom`` it finds on a shape, so a second, appended one is silently ignored.

    :param shapes: The bodies to modify in place.
    """
    for shape in shapes:
        for geometry in shape.collision:
            existing = [
                prop
                for prop in geometry.simulator_additional_properties
                if isinstance(prop, MujocoGeom)
            ]
            mujoco_geom = existing[0] if existing else MujocoGeom()
            mujoco_geom.friction = list(GRASP_FRICTION)
            mujoco_geom.solver_reference = list(GRASP_SOLVER_REFERENCE)
            mujoco_geom.solver_impedance = list(GRASP_SOLVER_IMPEDANCE)
            if not existing:
                geometry.simulator_additional_properties.append(mujoco_geom)


def equip_panda_for_physical_simulation(robot: Panda) -> set[DegreeOfFreedom]:
    """
    Give the Panda everything it needs to be driven by MuJoCo's own physics rather than
    kinematically teleported, and report which of its degrees of freedom that covers.

    Every controlled joint (arm and gripper) gets a position-servo actuator (see
    :data:`PANDA_JOINT_SERVO_TUNING`) that tracks whatever the motion planner commands.
    Every arm link gets MuJoCo's own gravity compensation: without it each joint settles
    with a steady-state error from gravity sag alone, large enough that a motion merely
    holding the arm never registers as converged.

    The fingertips keep the friction their own MJCF declares, matching
    ``coraplex_panda_demo``, which grasps reliably without overriding them; only the
    grasped shapes get :func:`apply_grasp_contact_parameters`.

    :param robot: The mounted Panda, modified in place.
    :return: The degrees of freedom MuJoCo now drives, for
        :class:`~semantic_digital_twin.adapters.multi_sim.MujocoSim`'s
        ``physically_simulated_dofs``.
    """
    arm = robot.get_arms()[0]
    physically_simulated_dofs = set(robot.degrees_of_freedom_with_hardware_interface)

    with robot._world.modify_world():
        for dof in sorted(physically_simulated_dofs, key=lambda d: d.name.name):
            _add_actuator(robot._world, dof, _servo_tuning_for(dof.name.name))

        for connection in arm.active_connections:
            connection.dynamics.armature = ARM_JOINT_ARMATURE
            connection.child.simulator_additional_properties.append(
                MujocoBody(gravitation_compensation_factor=1.0)
            )

    return physically_simulated_dofs
