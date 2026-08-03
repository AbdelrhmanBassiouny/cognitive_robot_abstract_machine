"""
Build the Montessori shape-sorting world and, if ROS 2 is available, a robot (see
:data:`DEFAULT_ROBOT_CLASS`) in a semantic digital twin world, visualize it live in
RViz, have the robot sort every loose shape into its matching hole (physically settling
each one under gravity in MuJoCo right after it is placed, rather than leaving it
exactly where it was kinematically teleported to), and finally physically simulate the
finished scene live in MuJoCo.

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.montessori_demo
    python -m experiments.montessori.montessori_demo --headless

.. note::
    ROS 2 (``rclpy``) is optional: without it, the scene is still built and viewable
    through :class:`~experiments.montessori.world.MontessoriWorld` directly, but RViz
    visualization is skipped and, since sorting the shapes requires the ROS-dependent
    CRAM/Giskard motion stack, no robot is spawned, no shapes are inserted, and MuJoCo
    is not started, regardless of whether :data:`DEFAULT_ROBOT_CLASS`'s description is
    installed. With ``rclpy`` installed, add a ``MarkerArray`` display in RViz2 for the
    topic printed at startup, with ``DurabilityPolicy.TRANSIENT_LOCAL``, to see the
    scene. The ``mujoco`` dependency (declared by ``semantic_digital_twin``; run
    ``uv sync`` once from the repository root if it is not yet installed) is required
    either way. :data:`DEFAULT_ROBOT_CLASS` additionally requires its own ROS package
    (e.g. ``hsr_description`` for :class:`~semantic_digital_twin.robots.hsrb.HSRB`) to
    be built and sourced.
"""

from __future__ import annotations

import argparse
import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import mujoco

from typing_extensions import Optional, Type

from experiments.montessori.semantics import MontessoriShape, NoMatchingHoleError
from experiments.montessori.world import MontessoriWorld, robot_installed
from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.utils import clear_memoization_cache
from semantic_digital_twin.adapters.multi_sim import MujocoActuator, MujocoSim
from coraplex.datastructures.enums import Arms
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionBetweenGroups,
    AvoidCollisionBetweenGroups,
)
from semantic_digital_twin.exceptions import PointOccupiedError
from semantic_digital_twin.robots.hsrb import HSRB
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.utils import rclpy_installed
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    ActiveConnection,
    ActiveConnection1DOF,
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import Actuator

if TYPE_CHECKING:
    # coraplex.datastructures.dataclasses pulls in rclpy at module level (see
    # _insert_all_shapes), so this is only ever imported for type hints, never at
    # runtime.
    from coraplex.datastructures.dataclasses import Context

logger = logging.getLogger(__name__)

DEFAULT_ROBOT_CLASS: Type[AbstractRobot] = HSRB
"""
The robot spawned by :func:`main` into the Montessori scene, via
:meth:`~experiments.montessori.world.MontessoriWorld.spawn_robot`.
"""

ACTUATOR_TIME_CONSTANT = 0.1
"""
MuJoCo actuator ``dynamics_parameters[0]`` for the position-hold actuators added to the
robot's joints.
"""

ARM_ACTUATOR_POSITION_GAIN = 100.0
"""
Proportional gain of the MuJoCo position-hold actuators added to the robot's controlled
joints (arm, wrist, head).
"""

ARM_ACTUATOR_VELOCITY_GAIN = 10.0
"""
Derivative (damping) gain of the MuJoCo position-hold actuators added to the robot's
controlled joints (arm, wrist, head).
"""

BASE_ACTUATOR_POSITION_GAIN = 1.0
"""
Proportional gain of the MuJoCo position-hold actuators added to the mobile base's wheel
joints.

Much lower than :data:`ARM_ACTUATOR_POSITION_GAIN`: the wheels have far less inertia
than an arm link, and holding them with the arm's gain makes the simulation numerically
unstable (``QACC`` diverges within the first few milliseconds and never settles).
"""

BASE_ACTUATOR_VELOCITY_GAIN = 0.1
"""
Derivative (damping) gain of the MuJoCo position-hold actuators added to the mobile
base's wheel joints.
"""

BASE_JOINT_DAMPING = 50.0
"""
Viscous friction (:attr:`JointDynamics.damping`) added to the mobile base's wheel
joints, resisting spinning regardless of the (weak) position-hold actuator.
"""

BASE_JOINT_DRY_FRICTION = 5.0
"""
Dry friction (:attr:`JointDynamics.dry_friction`) added to the mobile base's wheel
joints, resisting spinning regardless of the (weak) position-hold actuator.
"""

MUJOCO_STEP_SIZE = 2e-4
"""
MuJoCo simulation step size used for the finished scene, smaller than MuJoCo's own
default (``1e-3``): the default step is too large for the wheel joints' low inertia
combined with their position hold and contact with the floor, and repeatedly drives
``QACC`` to ``NaN``/``Inf``.
"""

MAX_INSERTION_ATTEMPTS = 3
"""
Number of times :func:`_insert_all_shapes` tries inserting a single shape (see
:data:`RETRY_HORIZONTAL_JITTER`) before giving up and logging a warning.
"""

RETRY_HORIZONTAL_JITTER = 0.003
"""
Maximum magnitude, along either axis, of the random horizontal offset (:attr:`~experimen
ts.montessori.insert_shape_action.InsertMontessoriShapeAction.target_horizontal_offset`)
applied to a retried insertion's drop point.

A retry that teleports the shape to the exact same pose and re-settles it in MuJoCo
gives the physics engine no new information, so it is prone to failing the same way
again; a few millimeters of jitter, small next to every hole's own clearance margin
(see :data:`~experiments.montessori.world.SHAPE_FOOTPRINT_CLEARANCE_SCALE`), is enough
to change how the shape first contacts the hole's edge without missing the opening
outright.
"""


def _random_horizontal_jitter() -> Point3:
    """
    A random ``(x, y, 0)`` offset within :data:`RETRY_HORIZONTAL_JITTER` of the origin,
    for :func:`_insert_all_shapes` to retry a failed insertion with an actually
    different drop point.
    """
    return Point3(
        random.uniform(-RETRY_HORIZONTAL_JITTER, RETRY_HORIZONTAL_JITTER),
        random.uniform(-RETRY_HORIZONTAL_JITTER, RETRY_HORIZONTAL_JITTER),
        0.0,
    )


@dataclass(frozen=True)
class InsertionAttemptResult:
    """
    Outcome of a single :func:`_insert_shape` call.
    """

    target_horizontal_offset: Point3
    """
    The horizontal offset the attempt was actually released at (see :attr:`~experiments.
    montessori.insert_shape_action.InsertMontessoriShapeAction.target_horizontal_offset`
    ), whether given by the caller or generated internally.
    """

    fell_through_hole: bool
    """
    Whether the shape actually fell through its hole after settling; see :meth:`~experim
    ents.montessori.insert_shape_action.InsertMontessoriShapeAction.has_fallen_through_h
    ole`.
    """


def _insert_shape(
    shape: MontessoriShape,
    montessori: MontessoriWorld,
    context: Context,
    headless: bool,
    target_horizontal_offset: Optional[Point3] = None,
) -> InsertionAttemptResult:
    """
    Have the robot pick up and insert a single loose shape into its matching hole once,
    then physically settle it under gravity in MuJoCo (see
    :func:`_settle_shape_in_mujoco`).

    Runs with Giskard's collision avoidance off
    (:data:`~coraplex.execution_environment.simulated_robot`'s
    ``collision_avoidance`` default): with it on, even the pre-grasp hover pose (well
    clear of the table) consistently failed to converge for this scene, regardless of
    how far the standing pose or collision buffer were tuned, pointing at the QP
    solver's own performance under collision avoidance rather than at genuinely
    unreachable geometry (see :func:`_enable_robot_table_collision_avoidance`, no
    longer called here). Any resulting table/board interpenetration during the
    kinematic reach is corrected once each shape settles under gravity in MuJoCo.

    :param shape: The shape to insert; must have a matching hole (see
        :meth:`~experiments.montessori.semantics.ShapeSortingBoard.hole_for`).
    :param montessori: The Montessori scene, with :attr:`MontessoriWorld.robot` already
        spawned and its controlled joints already held (see
        :func:`_hold_controlled_joints_in_mujoco`).
    :param context: The CRAM execution context to run the insertion action in.
    :param headless: Whether to run the settling MuJoCo simulation without opening a
        viewer window.
    :param target_horizontal_offset: Horizontal offset to release the shape at; a
        random :func:`_random_horizontal_jitter` is used if not given.
    :return: The attempt's outcome.
    """
    from coraplex.datastructures.enums import Arms
    from coraplex.execution_environment import simulated_robot
    from coraplex.plans.factories import execute_single
    from experiments.montessori.insert_shape_action import InsertMontessoriShapeAction

    offset = target_horizontal_offset or _random_horizontal_jitter()

    # World.get_kinematic_structure_entities_of_branch is @memoize'd per
    # (world, root-object) and never invalidated across the attach/detach cycle
    # of the *previous* insertion's pick-and-place, so the next action's
    # gripper-contents query silently returns a stale branch. Clearing it before
    # each insertion forces a fresh read of the actual current world state.
    clear_memoization_cache(montessori.world)
    action = InsertMontessoriShapeAction(
        montessori_shape=shape,
        board=montessori.board,
        arm=Arms.RIGHT,
        target_horizontal_offset=offset,
    )
    with simulated_robot():
        node = execute_single(action, context=context)
        node.perform()

    logger.info("Settling %s in MuJoCo.", shape.name)
    _settle_shape_in_mujoco(shape, montessori, headless)

    return InsertionAttemptResult(offset, action.has_fallen_through_hole())


def _insert_shape_or_none(
    shape: MontessoriShape,
    montessori: MontessoriWorld,
    context: Context,
    headless: bool,
    attempt: int,
) -> Optional[InsertionAttemptResult]:
    """
    Attempt one insertion via :func:`_insert_shape`, returning ``None`` instead of
    letting a retryable failure propagate: either
    :class:`~semantic_digital_twin.exceptions.PointOccupiedError`, if this attempt's
    jittered drop point put the reach target outside the navigation map's free space; a
    :class:`~coraplex.plans.failures.PlanFailure` (e.g. ``EmptyUnderspecified`` if no
    standing offset/grasp satisfies every constraint, or ``MotionDidNotFinish`` if a
    motion failed while executing), while actually reaching for and grasping the shape;
    or a :class:`~giskardpy.motion_statechart.exceptions.CollisionViolatedError`, raised
    when the gripper's approach to a shape resting on the table marginally breaches
    :data:`GRIPPER_TABLE_BUFFER_ZONE_DISTANCE`, since the standing offset
    :meth:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction._move_to_reach`
    resolves is not itself constrained to avoid that. None of these indicate a
    fundamentally unreachable shape, only that this specific attempt's resolved
    standing offset or approach did not work out, so retrying (with a jittered drop
    point, changing what gets resolved next) is as reasonable as it is for
    ``PointOccupiedError``.

    :param shape: The shape to insert; must have a matching hole.
    :param montessori: The Montessori scene, with :attr:`MontessoriWorld.robot` already
        spawned and its controlled joints already held.
    :param context: The CRAM execution context to run the insertion action in.
    :param headless: Whether to run the settling MuJoCo simulation without opening a
        viewer window.
    :param attempt: This attempt's 1-based index, used only for the log message.
    :return: The attempt's outcome, or ``None`` if this attempt failed in a retryable
        way.
    """
    from coraplex.plans.failures import PlanFailure
    from giskardpy.motion_statechart.exceptions import CollisionViolatedError

    try:
        return _insert_shape(shape, montessori, context, headless)
    except (PointOccupiedError, PlanFailure, CollisionViolatedError) as error:
        logger.warning(
            "%s's insertion attempt %d/%d failed (%s); retrying.",
            shape.name,
            attempt,
            MAX_INSERTION_ATTEMPTS,
            error,
        )
        return None


ROBOT_TABLE_BUFFER_ZONE_DISTANCE = 0.02
"""
Buffer-zone distance (see
:attr:`~semantic_digital_twin.collision_checking.collision_rules.AvoidCollisionRule.buffer_zone_distance`)
used for the robot against the table, instead of the robot's default 5cm
(:meth:`~semantic_digital_twin.robots.hsrb.HSRB._setup_collision_rules`).

A grasp pose sits at the target shape's own center, a couple of centimeters above the
table at most for every Montessori shape (see
:meth:`~experiments.montessori.world.MontessoriWorld._resting_position_on_table`); the
default 5cm buffer keeps the whole robot no closer than that to any external body,
which not just the gripper but the wrist and forearm too cannot honor while actually
reaching down to grasp a shape resting on the table, so the reach never leaves its
pre-grasp hover. Narrowing the buffer for the whole robot (not just the gripper; the
lower arm needs to get close to the table too) against only the table (not the shapes
or board, already excluded entirely below) keeps a real, if smaller, standoff instead
of removing avoidance outright.
"""


def _enable_robot_table_collision_avoidance(montessori: MontessoriWorld) -> None:
    """
    Restrict Giskard's collision avoidance, enabled by ``collision_avoidance=True`` on
    :data:`~coraplex.execution_environment.simulated_robot` in :func:`_insert_shape`, to
    the robot and the table, and let the robot approach the table more closely than its
    default standoff.

    .. note::
        Currently unused: :func:`_insert_shape` runs with collision avoidance off
        entirely, since even with this narrowing in place, the reach still failed to
        converge to the pre-grasp hover pose (well clear of the table) once collision
        avoidance was actually turned on. Kept for whoever next attempts to re-enable
        collision avoidance for this scene, e.g. after addressing the QP solver's
        performance under it.

    The robot's own default
    :class:`~semantic_digital_twin.collision_checking.collision_rules.AvoidExternalCollisions`
    rules (added when it is spawned, e.g. :meth:`~semantic_digital_twin.robots.hsrb.HSRB.__post_init__`)
    already check it against every other collision body in the world once that flag is
    on, including the shape-sorting board's ~40-50-piece CoACD decomposition, which
    overloads Giskard's QP solver (a convergence timeout, not a detected collision) for
    the tight-clearance pickup motion. Force-excluding everything but the table, rather
    than adding another avoid-rule on top of those, is what actually narrows the
    checked set: :attr:`~semantic_digital_twin.collision_checking.collision_manager.CollisionManager.ignore_collision_rules`
    are applied last and cannot be overwritten by the broader default rules already in
    place.

    A second, narrower :class:`~semantic_digital_twin.collision_checking.collision_rules.AvoidCollisionBetweenGroups`
    rule is added as a default rule for the robot against the table specifically, with
    :data:`ROBOT_TABLE_BUFFER_ZONE_DISTANCE` instead of the default 5cm:
    :meth:`~semantic_digital_twin.collision_checking.collision_manager.CollisionManager.get_buffer_zone_distance`
    scans rules most-recently-added first, so this rule (added after the robot's own
    default rule) wins for every robot-table pair.

    :param montessori: The Montessori scene, with :attr:`MontessoriWorld.robot` already
        spawned.
    """
    [table] = montessori.world.get_semantic_annotations_by_type(Table)
    robot_bodies = set(montessori.robot.bodies_with_collision)
    table_bodies = set(table.bodies_with_collision)
    other_bodies = (
        set(montessori.world.bodies_with_collision) - robot_bodies - table_bodies
    )
    with montessori.world.modify_world():
        montessori.world.collision_manager.add_ignore_collision_rule(
            AllowCollisionBetweenGroups(
                body_group_a=list(robot_bodies), body_group_b=list(other_bodies)
            )
        )
        montessori.world.collision_manager.add_default_rule(
            AvoidCollisionBetweenGroups(
                body_group_a=list(robot_bodies),
                body_group_b=list(table_bodies),
                buffer_zone_distance=ROBOT_TABLE_BUFFER_ZONE_DISTANCE,
            )
        )


def _insert_all_shapes(montessori: MontessoriWorld, headless: bool) -> None:
    """
    Have the robot pick up and insert every loose shape that has a matching hole into
    the shape-sorting board, skipping any that don't (e.g. the sphere), retrying a shape
    that does not actually fall through its hole (see :func:`_insert_shape`) up to
    :data:`MAX_INSERTION_ATTEMPTS` times with a jittered drop point before giving up on
    it.

    :param montessori: The Montessori scene, with :attr:`MontessoriWorld.robot` already
        spawned and its controlled joints already held (see
        :func:`_hold_controlled_joints_in_mujoco`).
    :param headless: Whether to run the settling MuJoCo simulations without opening a
        viewer window.
    """
    # Imported lazily: coraplex.datastructures.dataclasses pulls in
    # coraplex.plans.executables for GiskardExecutable, which imports rclpy at module
    # level, so this whole chain would make the demo unimportable without ROS 2 even
    # though nothing here runs without it anyway (see rclpy_installed() in main()).
    from coraplex.datastructures.dataclasses import Context

    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )

    for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape):
        try:
            montessori.board.hole_for(shape)
        except NoMatchingHoleError:
            logger.info("Skipping %s: no matching hole.", shape.name)
            continue

        for attempt in range(1, MAX_INSERTION_ATTEMPTS + 1):
            logger.info(
                "Inserting %s into its matching hole (attempt %d/%d).",
                shape.name,
                attempt,
                MAX_INSERTION_ATTEMPTS,
            )
            result = _insert_shape_or_none(shape, montessori, context, headless, attempt)
            if result is not None and result.fell_through_hole:
                break
        else:
            logger.warning(
                "%s did not fall through its hole after %d attempts; it may be "
                "resting on the board or wedged in the opening.",
                shape.name,
                MAX_INSERTION_ATTEMPTS,
            )


def _position_hold_actuator(
    position_gain: float, velocity_gain: float
) -> MujocoActuator:
    """
    Build a MuJoCo actuator that holds its degree of freedom at whatever position it had
    when the simulation started, resisting gravity and contacts with a PD law.

    :param position_gain: Proportional gain of the hold.
    :param velocity_gain: Derivative (damping) gain of the hold.
    """
    return MujocoActuator(
        dynamics_type=mujoco.mjtDyn.mjDYN_NONE,
        dynamics_parameters=[ACTUATOR_TIME_CONSTANT] + [0.0] * 9,
        gain_type=mujoco.mjtGain.mjGAIN_FIXED,
        gain_parameters=[position_gain] + [0.0] * 9,
        bias_type=mujoco.mjtBias.mjBIAS_AFFINE,
        bias_parameters=[0, -position_gain, -velocity_gain] + [0.0] * 7,
    )


def _add_position_hold_actuator(
    world: World, dof: DegreeOfFreedom, position_gain: float, velocity_gain: float
) -> None:
    """
    Add a :func:`_position_hold_actuator` for ``dof`` to ``world``.

    :param world: The world to add the actuator to, modified in place.
    :param dof: The degree of freedom to hold.
    :param position_gain: Proportional gain of the hold.
    :param velocity_gain: Derivative (damping) gain of the hold.
    """
    actuator = Actuator()
    actuator.add_dof(dof=dof)
    actuator.simulator_additional_properties.append(
        _position_hold_actuator(position_gain, velocity_gain)
    )
    world.add_actuator(actuator=actuator)


def _base_degrees_of_freedom_without_hardware_interface(
    robot: AbstractRobot,
) -> list[DegreeOfFreedom]:
    """
    The degrees of freedom of :func:`_base_connections_without_hardware_interface`.

    :param robot: The spawned robot.
    """
    return [
        connection.raw_dof
        for connection in _base_connections_without_hardware_interface(robot)
    ]


def _base_connections_without_hardware_interface(
    robot: AbstractRobot,
) -> list[ActiveConnection1DOF]:
    """
    The robot's mobile-base joints (drive wheels, passive caster wheels, base roll, ...)
    that have a degree of freedom but, unlike the arm/wrist/head, are not part of
    :attr:`AbstractRobot.degrees_of_freedom_with_hardware_interface`: they are driven
    indirectly through the :class:`OmniDrive` connection rather than controlled
    directly. Left unactuated, MuJoCo's contact and gravity forces spin them up without
    bound.

    Excludes every end effector's own uncontrolled (mimic/spring) joints, which already
    move together through their mimic relationship and don't need an independent hold.

    :param robot: The spawned robot.
    """
    controlled_dofs = set(robot.degrees_of_freedom_with_hardware_interface)
    gripper_dofs = {
        dof
        for end_effector in robot.get_end_effectors()
        for connection in end_effector.connections
        if isinstance(connection, ActiveConnection)
        for dof in connection.active_dofs
    }

    base_connections = []
    seen_dofs = set(controlled_dofs)
    for connection in robot.connections:
        if not isinstance(connection, ActiveConnection1DOF):
            continue
        if connection.raw_dof in seen_dofs or connection.raw_dof in gripper_dofs:
            continue
        seen_dofs.add(connection.raw_dof)
        base_connections.append(connection)
    return base_connections


def _hold_controlled_joints_in_mujoco(robot: AbstractRobot) -> None:
    """
    Keep every joint of the robot that would otherwise be left to MuJoCo's own physics
    (arm, wrist, head, and the mobile base's wheels) from sagging or spinning under
    gravity and contacts once MuJoCo starts stepping the world.

    The arm/wrist/head are held with a MuJoCo position-hold actuator
    (:data:`ARM_ACTUATOR_POSITION_GAIN`). The base's wheels additionally get joint
    damping and dry friction (:data:`BASE_JOINT_DAMPING`,
    :data:`BASE_JOINT_DRY_FRICTION`): their low inertia makes the arm's actuator gains
    numerically unstable, and a weak actuator (:data:`BASE_ACTUATOR_POSITION_GAIN`)
    alone is not enough to stop them spinning once the robot has actually driven around
    and is resting at a real, contact-heavy pose rather than its spawn pose.

    :param robot: The spawned robot, modified in place.
    """
    with robot._world.modify_world():
        for dof in robot.degrees_of_freedom_with_hardware_interface:
            _add_position_hold_actuator(
                robot._world,
                dof,
                ARM_ACTUATOR_POSITION_GAIN,
                ARM_ACTUATOR_VELOCITY_GAIN,
            )
        for connection in _base_connections_without_hardware_interface(robot):
            connection.dynamics.damping = BASE_JOINT_DAMPING
            connection.dynamics.dry_friction = BASE_JOINT_DRY_FRICTION
            _add_position_hold_actuator(
                robot._world,
                connection.raw_dof,
                BASE_ACTUATOR_POSITION_GAIN,
                BASE_ACTUATOR_VELOCITY_GAIN,
            )


def _make_shape_movable_in_mujoco(shape: MontessoriShape, world: World) -> None:
    """
    Re-attach a loose shape's body to the world root with a free
    (:class:`Connection6DoF`) joint instead of the rigid connection it currently has,
    preserving its current pose.

    :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction` always re-attaches a
    placed object with a :class:`~semantic_digital_twin.world_description.connections.FixedConnection`
    (a deliberate, framework-wide choice; see the ``# TODO: this shouldn't be fixed but
    6DOF`` comment in ``coraplex.plans.executables.ModelChangeExecutable``), and every
    loose shape starts out :class:`FixedConnection`'d to the world root too. MuJoCo
    treats an unjointed body as welded to its parent, so without this a shape cannot be
    affected by gravity or contacts at all once MuJoCo starts stepping the world.

    :param shape: The shape to make movable.
    :param world: The world the shape belongs to, modified in place.
    """
    current_pose = world.compute_forward_kinematics(world.root, shape.root)
    with world.modify_world():
        world.remove_connection(shape.root.parent_connection)
        connection = Connection6DoF.create_with_dofs(
            world=world,
            parent=world.root,
            child=shape.root,
        )
        world.add_connection(connection)
    # Bakes current_pose into the connection's own DOF values (x, y, z, qx, qy, qz, qw)
    # rather than passing it as create_with_dofs' parent_T_connection_expression: MuJoCo
    # export only reads a Connection6DoF's DOF values into the free joint's keyframe
    # qpos, which is MuJoCo's *absolute* world position/orientation for a free joint, not
    # a fixed offset applied on top of it. Passing current_pose as
    # parent_T_connection_expression left the DOFs at their create_with_dofs default
    # (identity), so MuJoCo always started the shape at the world origin regardless of
    # current_pose - correct only for whichever shape happened to be the first one ever
    # settled in a given MontessoriWorld, because MujocoBuilder.build_world's one-time
    # "connect the existing root to a body literally named 'world'" step reparents that
    # first shape's free joint via World.move_branch, which (unlike this) writes the
    # DOF values directly.
    connection.origin = current_pose


def _make_all_shapes_movable_in_mujoco(montessori: MontessoriWorld) -> None:
    """
    Apply :func:`_make_shape_movable_in_mujoco` to every loose Montessori shape.

    :param montessori: The Montessori scene, modified in place.
    """
    for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape):
        _make_shape_movable_in_mujoco(shape, montessori.world)


SHAPE_SETTLE_DURATION = 2.0
"""
Real-time seconds a just-inserted shape is given to physically settle under gravity and
contacts in MuJoCo (see :func:`_settle_shape_in_mujoco`) before it is fixed in place and
the next shape is inserted.
"""


def _settle_shape_in_mujoco(
    shape: MontessoriShape, montessori: MontessoriWorld, headless: bool
) -> None:
    """
    Physically settle a single, just-placed shape under gravity and contacts in MuJoCo,
    then fix it in place wherever it comes to rest.

    :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction` only ever teleports
    a shape kinematically to its target pose, so without this every shape is left
    exactly where it was placed rather than where gravity actually settles it (e.g.
    resting on the board's surface instead of having dropped through a hole). Settling
    one shape at a time, right after it is inserted, rather than all of them together
    only once at the very end (see :func:`_simulate_finished_scene_in_mujoco`), also
    avoids MuJoCo resolving several simultaneous tight-clearance contacts in the same
    step, which was observed to make an unrelated shape's contact resolution
    nondeterministic (which of several simultaneously falling shapes gets wedged varied
    from run to run, even though each one settles correctly when dropped alone).

    The robot's controlled joints must already be held (see
    :func:`_hold_controlled_joints_in_mujoco`) before this runs, or they sag/spin under
    gravity for the duration of the settle and are left in that pose once MuJoCo stops.

    :param shape: The just-inserted shape to settle.
    :param montessori: The Montessori scene, modified in place.
    :param headless: Whether to run without opening a MuJoCo viewer window.
    """
    _make_shape_movable_in_mujoco(shape, montessori.world)

    mujoco_sim = MujocoSim(
        world=montessori.world, headless=headless, step_size=MUJOCO_STEP_SIZE
    )
    mujoco_sim.start_simulation()
    time.sleep(SHAPE_SETTLE_DURATION)
    mujoco_sim.stop_simulation()

    montessori.world.update_forward_kinematics()
    settled_pose = montessori.world.compute_forward_kinematics(
        montessori.world.root, shape.root
    )
    with montessori.world.modify_world():
        montessori.world.remove_connection(shape.root.parent_connection)
        montessori.world.add_connection(
            FixedConnection(
                parent=montessori.world.root,
                child=shape.root,
                parent_T_connection_expression=settled_pose,
            )
        )


def _simulate_finished_scene_in_mujoco(
    montessori: MontessoriWorld, headless: bool
) -> MujocoSim:
    """
    Physically simulate the sorted scene in MuJoCo, with the robot's controlled joints
    held in place and the shapes free to move under gravity and contacts.

    Every shape has already individually settled under physics once, right after it was
    inserted (see :func:`_settle_shape_in_mujoco`); this final pass is for live viewing
    of the completed scene, not the shapes' only chance to physically settle.

    :param montessori: The finished Montessori scene, with :attr:`MontessoriWorld.robot`
        already spawned.
    :param headless: Whether to run without opening a MuJoCo viewer window.
    :return: The running :class:`MujocoSim`.
    """
    _make_all_shapes_movable_in_mujoco(montessori)

    mujoco_sim = MujocoSim(
        world=montessori.world, headless=headless, step_size=MUJOCO_STEP_SIZE
    )
    mujoco_sim.synchronizer.sync_rate_hz = 20
    mujoco_sim.start_simulation()
    return mujoco_sim


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments selecting whether a MuJoCo viewer window is opened.

    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the MuJoCo simulation without opening a viewer window.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Build the Montessori world, visualize it in RViz, have the robot sort the loose
    shapes into the board, physically simulate the finished scene in MuJoCo, and keep
    the live viewer open until interrupted.
    """
    logging.basicConfig(level=logging.INFO)
    arguments = _parse_arguments()

    montessori = MontessoriWorld()

    if robot_installed(DEFAULT_ROBOT_CLASS):
        montessori.spawn_robot(DEFAULT_ROBOT_CLASS)
        # Must happen before any MuJoCo simulation runs, including the per-shape
        # settling in _insert_all_shapes, or the robot's own joints sag/spin under
        # gravity for that simulation's duration (see
        # _hold_controlled_joints_in_mujoco).
        _hold_controlled_joints_in_mujoco(montessori.robot)
    else:
        logger.warning(
            "%s's description is not installed; spawning the Montessori scene "
            "without a robot.",
            DEFAULT_ROBOT_CLASS.__name__,
        )
    logger.info("Built Montessori world with %d bodies.", len(montessori.world.bodies))

    # Sorting the shapes goes through CRAM's execute_single, which pulls in
    # coraplex.plans.executables for GiskardExecutable, which imports rclpy at module
    # level regardless of whether a real robot ever executes a real ROS 2 motion; RViz
    # visualization needs rclpy directly. Both are skipped without it, rather than the
    # whole demo failing to even import.
    ros_active = rclpy_installed()
    node = executor = thread = tf_publisher = viz_marker_publisher = None
    if ros_active:
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
        from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
            VizMarkerPublisher,
        )

        if not rclpy.ok():
            rclpy.init()
        node = rclpy.create_node("montessori_demo")
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        thread = threading.Thread(
            target=executor.spin, daemon=True, name="rclpy-executor"
        )
        thread.start()
        time.sleep(0.1)

        tf_publisher = TFPublisher(node=node, _world=montessori.world)
        viz_marker_publisher = VizMarkerPublisher(_world=montessori.world, node=node)
        logger.info(
            "Visualizing the Montessori world on topic '%s'.",
            viz_marker_publisher.topic_name,
        )
    else:
        logger.warning("rclpy is not installed; running without RViz visualization.")

    mujoco_sim = None
    if montessori.robot is not None and ros_active:
        import experiments.orm.ormatic_interface  # type: ignore

        _insert_all_shapes(montessori, headless=arguments.headless)
        logger.info("Sorting done; starting the MuJoCo simulation.")
        mujoco_sim = _simulate_finished_scene_in_mujoco(
            montessori, headless=arguments.headless
        )
    elif montessori.robot is not None:
        logger.warning("rclpy is not installed; skipping sorting and MuJoCo.")

    logger.info("Done. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if mujoco_sim is not None:
            mujoco_sim.stop_simulation()
        if viz_marker_publisher is not None:
            viz_marker_publisher.stop()
        if tf_publisher is not None:
            tf_publisher.stop()
        if executor is not None:
            executor.shutdown()
        if thread is not None:
            thread.join(timeout=2.0)
        if node is not None:
            node.destroy_node()
        if ros_active and rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
