"""
Read Tracy's description out of its own ROS package and equip it to be driven by
MuJoCo's own physics (position-servo actuators and gravity compensation) rather than
kinematically teleported, mirroring :mod:`experiments.montessori.franka_panda_equipment`
generalized to Tracy's own dual-UR10-arm, Robotiq-85-gripper body.

Unlike the Panda (see :func:`~experiments.montessori.franka_panda_equipment.parse_panda`),
Tracy has a real ROS package (``iai_tracy_description``), so its own URDF is read
directly rather than out of an MJCF shared with an unrelated demo.

.. note::
    No MJCF (tuned or otherwise) exists for Tracy anywhere in this repository, the
    ``iai_tracy_description`` ROS package, or any locally checked-out copy of
    `MuJoCo Menagerie <https://github.com/google-deepmind/mujoco_menagerie>`_. An
    initial, invented set of generic position-hold gains (unclamped, matching
    :mod:`experiments.montessori.montessori_demo`'s own HSR actuator) was tried first and
    was unstable: passive holding sagged under gravity, and Giskard's control loop,
    chasing a joint that could never converge, drove the arm into growing oscillation
    rather than parking. :data:`TRACY_ARM_JOINT_SERVO_TUNING` replaces that guess with
    Menagerie's own real, pre-tuned ``universal_robots_ur10e/ur10e.xml`` actuator gains,
    per-joint torque limits, and joint damping/armature -- Tracy's arms are a UR10, not a
    UR10e, but structurally close enough that reusing an authoritative reference beats an
    invented one. No such reference exists for the Robotiq-85 gripper (Menagerie has none
    either), so :data:`TRACY_GRIPPER_JOINT_SERVO_TUNING` is still an unproven starting
    point.
"""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
from typing_extensions import Mapping, Tuple

from semantic_digital_twin.adapters.multi_sim import MujocoActuator, MujocoBody
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import (
    Actuator,
    Body,
    KinematicStructureEntity,
)

TRACY_MOUNT_ROOT_NAME = PrefixedName("tracy_mount", "montessori")
"""
Name given to the parsed Tracy's own synthetic world root once merged, so it never
collides with a merge target's own root -- mirrors
:data:`~experiments.montessori.franka_panda_equipment.PANDA_MOUNT_ROOT_NAME`. Tracy's
real kinematic root, the body named ``"table"`` (see
:meth:`~semantic_digital_twin.robots.tracy.Tracy._get_root_body_name`), is a descendant
of this synthetic node, not the node itself, so renaming it does not affect
:meth:`~semantic_digital_twin.robots.robot_parts.AbstractRobot.from_world`'s later lookup.
"""


@dataclass(frozen=True)
class JointServoTuning:
    """
    The gains, torque clamp, and passive joint damping one arm joint's position-servo
    actuator is built with; mirrors
    :class:`~experiments.montessori.franka_panda_equipment.JointServoTuning`, with the
    joint's own passive damping added since :data:`TRACY_ARM_JOINT_SERVO_TUNING`'s source
    specifies one per joint too (unlike the Panda's own tuning table).
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
    Force/torque clamp of the servo.
    """

    joint_damping: float
    """
    Passive viscous damping (:attr:`~semantic_digital_twin.world_description.connection_properties.JointDynamics.damping`)
    of the joint itself, independent of the servo's own :attr:`velocity_gain`.
    """


TRACY_ARM_JOINT_SERVO_TUNING: Mapping[str, JointServoTuning] = {
    # Read directly from MuJoCo Menagerie's universal_robots_ur10e/ur10e.xml: the
    # <general ... gainprm="5000" biasprm="0 -5000 -500"/> default (position_gain=5000,
    # velocity_gain=500) shared by every joint, and each joint's own "size" class
    # <general forcerange=...>/<joint damping=...>: size4 (shoulder_pan, shoulder_lift)
    # =(-330, 330)/10, size3 (elbow) =(-150, 150)/5, size2 (the three wrist joints)
    # =(-56, 56)/2.
    "shoulder_pan_joint": JointServoTuning(5000.0, 500.0, (-330.0, 330.0), 10.0),
    "shoulder_lift_joint": JointServoTuning(5000.0, 500.0, (-330.0, 330.0), 10.0),
    "elbow_joint": JointServoTuning(5000.0, 500.0, (-150.0, 150.0), 5.0),
    "wrist_1_joint": JointServoTuning(5000.0, 500.0, (-56.0, 56.0), 2.0),
    "wrist_2_joint": JointServoTuning(5000.0, 500.0, (-56.0, 56.0), 2.0),
    "wrist_3_joint": JointServoTuning(5000.0, 500.0, (-56.0, 56.0), 2.0),
}
"""
Real, pre-tuned UR10e position-servo gains, torque limits, and joint damping, keyed by
joint name with Tracy's own ``left_``/``right_`` prefix stripped; see this module's own
docstring for where this comes from and why. Looked up by :func:`_servo_tuning_for`.
"""

TRACY_GRIPPER_JOINT_SERVO_TUNING = JointServoTuning(
    position_gain=100.0, velocity_gain=10.0, force_range=(-10.0, 10.0), joint_damping=0.0
)
"""
Tuning for a Robotiq-85 knuckle joint; no Menagerie or otherwise pre-tuned reference
exists for it (see this module's own docstring), so this is still an unproven starting
point, deliberately weak (it only has to move a light gripper through a small ``0..0.8``
rad range) pending real data or empirical iteration.
"""

ARM_JOINT_ARMATURE = 0.1
"""
Rotor inertia (:attr:`~semantic_digital_twin.world_description.connection_properties.JointDynamics.armature`)
added to every physically simulated arm joint, matching ``universal_robots_ur10e/ur10e.xml``'s
own declared armature (``armature="0.1"`` on its ``ur10e`` joint default).
"""


def parse_tracy() -> World:
    """
    Read Tracy out of its own ``iai_tracy_description`` ROS package, without any
    actuator: an actuator parsed into one world cannot be merged into another (see
    :func:`~experiments.montessori.world.mount_stationary_robot`), and
    :func:`equip_tracy_for_physical_simulation` installs its own once Tracy is mounted.

    :return: A world holding only Tracy's own body tree, its synthetic root renamed to
        :data:`TRACY_MOUNT_ROOT_NAME`.
    """
    tracy_world = URDFParser.from_file(Tracy.get_ros_file_path()).parse()
    with tracy_world.modify_world():
        for actuator in list(tracy_world.actuators):
            tracy_world.remove_actuator(actuator)
        tracy_world.root.name = TRACY_MOUNT_ROOT_NAME
    return tracy_world


def tracy_table_mount_position(tracy_world: World, x: float, y: float) -> tuple[Point3, float]:
    """
    Where to bolt a parsed-but-not-yet-mounted Tracy so its own built-in table's legs
    rest exactly on the floor (``z=0``), and the resulting height of that table's own top
    surface once mounted there.

    Tracy's own table is a fixed part of its body tree (see
    :meth:`~semantic_digital_twin.robots.tracy.Tracy._get_root_body_name`), not a
    separate stand built by the caller (contrast
    :meth:`~experiments.montessori.world.MontessoriWorld.add_robot_stand`), so this reads
    its true extent out of the model itself rather than assuming a fixed height.

    :param tracy_world: Tracy's own parsed world, as returned by :func:`parse_tracy`,
        not yet merged into anything.
    :param x: X-coordinate to mount Tracy's root at, in the merge target's root frame.
    :param y: Y-coordinate to mount Tracy's root at, in the merge target's root frame.
    :return: The mount position, and the world-frame height its table's own top surface
        ends up at once mounted there.
    """
    table_bounding_box = (
        tracy_world.get_body_by_name("table")
        .collision.as_bounding_box_collection_in_frame(tracy_world.root)
        .bounding_box()
    )
    mount_z = -table_bounding_box.min_z
    table_top_z = mount_z + table_bounding_box.max_z
    return Point3(x, y, mount_z), table_top_z


def _servo_tuning_for(dof_name: str) -> JointServoTuning:
    """
    The tuning a degree of freedom's servo is built with, by its (possibly
    ``left_``/``right_``-prefixed) name.

    :param dof_name: Name of the degree of freedom, e.g. ``"right_shoulder_pan_joint"``
        or ``"left_robotiq_85_left_knuckle_joint"``.
    :return: Its own tuning from :data:`TRACY_ARM_JOINT_SERVO_TUNING` if it names one of
        Tracy's six arm joints (either arm), else :data:`TRACY_GRIPPER_JOINT_SERVO_TUNING`.
    """
    unprefixed = dof_name.removeprefix("left_").removeprefix("right_")
    return TRACY_ARM_JOINT_SERVO_TUNING.get(unprefixed, TRACY_GRIPPER_JOINT_SERVO_TUNING)


def _position_servo_actuator(tuning: JointServoTuning) -> MujocoActuator:
    """
    Build a MuJoCo actuator that servos its degree of freedom to a commanded position
    with a PD law, clamped to ``tuning``'s own torque limit -- mirrors
    :func:`~experiments.montessori.franka_panda_equipment._position_servo_actuator`,
    duplicated here rather than imported since that module's own tuning is Panda-specific
    (see :data:`~experiments.montessori.franka_panda_equipment.PANDA_JOINT_SERVO_TUNING`'s
    own docstring for why the two should not be shared).

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


def _bodies_downstream_of(root: KinematicStructureEntity) -> list[Body]:
    """
    Every body reachable from ``root`` by following child links, ``root`` itself
    excluded -- a breadth-first walk of :attr:`~semantic_digital_twin.world_description.world_entity.KinematicStructureEntity.child_kinematic_structure_entities`.

    :param root: The entity to walk downstream from.
    """
    bodies: list[Body] = []
    frontier = list(root.child_kinematic_structure_entities)
    while frontier:
        entity = frontier.pop()
        if isinstance(entity, Body):
            bodies.append(entity)
        frontier.extend(entity.child_kinematic_structure_entities)
    return bodies


def equip_tracy_for_physical_simulation(robot: Tracy) -> set[DegreeOfFreedom]:
    """
    Give Tracy everything it needs to be driven by MuJoCo's own physics rather than
    kinematically teleported, and report which of its degrees of freedom that covers.

    Every controlled joint (both arms and both grippers) gets a position-servo actuator
    (see :data:`TRACY_ARM_JOINT_SERVO_TUNING`/:data:`TRACY_GRIPPER_JOINT_SERVO_TUNING`)
    that tracks whatever the motion planner commands, and each arm joint additionally
    gets :data:`ARM_JOINT_ARMATURE` and its own passive damping. Every body downstream of
    Tracy's own mounted root gets MuJoCo's own gravity compensation -- not just each
    arm's own chain up to the wrist (its
    :class:`~semantic_digital_twin.robots.robot_parts.Arm.active_connections`, which
    :meth:`~semantic_digital_twin.robots.robot_parts.Arm.setup_default_configuration_in_world_below_robot_root`
    stops at, leaving the Robotiq gripper hanging off the end of it entirely
    uncompensated): without full coverage each joint settles with a steady-state error
    from gravity sag alone (see
    :func:`~experiments.montessori.franka_panda_equipment.equip_panda_for_physical_simulation`,
    whose own reasoning around gravity sag this mirrors, generalized to Tracy's own
    separate arm/gripper split).

    :param robot: The mounted Tracy, modified in place.
    :return: The degrees of freedom MuJoCo now drives, for
        :class:`~semantic_digital_twin.adapters.multi_sim.MujocoSim`'s
        ``physically_simulated_dofs``.
    """
    physically_simulated_dofs = set(robot.degrees_of_freedom_with_hardware_interface)

    with robot._world.modify_world():
        for dof in sorted(physically_simulated_dofs, key=lambda d: d.name.name):
            _add_actuator(robot._world, dof, _servo_tuning_for(dof.name.name))

        for connection in [*robot.left_arm.active_connections, *robot.right_arm.active_connections]:
            tuning = _servo_tuning_for(connection.raw_dof.name.name)
            connection.dynamics.armature = ARM_JOINT_ARMATURE
            connection.dynamics.damping = tuning.joint_damping

        for body in _bodies_downstream_of(robot.root):
            body.simulator_additional_properties.append(
                MujocoBody(gravitation_compensation_factor=1.0)
            )

    return physically_simulated_dofs
