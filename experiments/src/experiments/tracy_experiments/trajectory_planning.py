"""
Plan Cartesian- or joint-space goals against an isolated, physics-free scratch copy of
the world via Giskard, then play the resulting trajectory back onto the real, physically
simulated MuJoCo world by driving each joint's own position-servo actuator directly.

Giskard never touches the live, physically simulated world under this module: it only
ever ticks against a :func:`copy.deepcopy` of it, so it cannot race
:class:`~semantic_digital_twin.adapters.multi_sim.MujocoSynchronizer`'s own
physics-thread state sync (see :mod:`~experiments.tracy_experiments.equipment`'s own
module docstring). Execution then drives real MuJoCo actuators the same way, so tracking
is genuinely closed-loop against measured physics, not open-loop trajectory replay.

Every motion here, including park and gripper open/close, is planned this way rather
than commanded straight to the target: see :func:`plan_joint_trajectory`'s own
docstring for why commanding a target directly, with no velocity profile at all, lets a
joint move far faster than its real hardware ever could.
"""

from __future__ import annotations

import logging
from copy import deepcopy

from giskardpy.executor import Executor
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.goals.collision_avoidance import (
    ExternalCollisionAvoidance,
)
from giskardpy.motion_statechart.graph_node import EndMotion, Task
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    CartesianPosition,
)
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList
from giskardpy.qp.qp_controller_config import QPControllerConfig
from typing_extensions import Dict, List, Tuple

from coraplex.datastructures.enums import Arms
from coraplex.exceptions import MotionDidNotFinish
from coraplex.plans.executables import GiskardExecutable
from experiments.tracy_experiments.equipment import joint_state_of_type
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import Actuator, Body

logger = logging.getLogger(__name__)

TARGET_FREQUENCY = 50
"""
Giskard tick rate used both to plan (scratch world) and to pace trajectory playback
(real world), so one recorded waypoint corresponds to one real physics-advance step.
"""

DEFAULT_MAX_TICKS = 2000
"""
Tick budget a single plan gets before giving up, matching
:attr:`~coraplex.plans.executables.GiskardExecutable.max_ticks_per_motion_mapping`'s own
kinematic-motion default -- planning always runs kinematically (see this module's own
docstring), regardless of whether the executing arm is physically simulated.
"""


def _arm_of(robot: Tracy, arm_side: Arms):
    """
    ``robot``'s own left or right arm object, by ``arm_side``.

    :param robot: The robot to look the arm up on.
    :param arm_side: Which arm to return; must be :attr:`Arms.LEFT` or
        :attr:`Arms.RIGHT`.
    """
    return robot.left_arm if arm_side == Arms.LEFT else robot.right_arm


def _plan_trajectory(
    scratch_world: World,
    task: Task,
    joint_connections: List[ActiveConnection1DOF],
    avoid_collisions: bool,
    max_ticks: int,
) -> List[Dict[str, float]]:
    """
    Tick ``task`` (already built against ``scratch_world``) until it converges,
    recording ``joint_connections``' own positions after every tick.

    :param scratch_world: The isolated world ``task`` was built against.
    :param task: The Giskard task to converge.
    :param joint_connections: Which connections' positions to record each tick.
    :param avoid_collisions: Whether Giskard's own ``ExternalCollisionAvoidance`` is
        enabled for this plan. Set False for a goal whose own point is to approach (and
        end up touching) an object -- e.g. descending onto something to grasp or place
        it, or closing a gripper around it -- since collision avoidance would otherwise
        treat that same object as an obstacle to stay away from and make the goal
        unreachable.
    :param max_ticks: Tick budget before giving up.
    :return: One dict of joint name to position per tick, in order.
    :raises MotionDidNotFinish: If the goal was not reached within ``max_ticks``.
    """
    motion_state_chart = MotionStatechart()
    motion_state_chart.add_node(task)
    if avoid_collisions:
        motion_state_chart.add_node(ExternalCollisionAvoidance())
    end_motion = EndMotion()
    end_motion.start_condition = task.observation_variable
    motion_state_chart.add_node(end_motion)

    executor = Executor(
        context=MotionStatechartContext(
            world=scratch_world,
            qp_controller_config=QPControllerConfig(
                target_frequency=TARGET_FREQUENCY,
                prediction_horizon=GiskardExecutable.prediction_horizon,
                verbose=False,
            ),
        )
    )
    executor.compile(motion_state_chart)

    trajectory: List[Dict[str, float]] = []
    try:
        for _ in range(max_ticks):
            executor.tick()
            trajectory.append(
                {
                    connection.raw_dof.name.name: scratch_world.state[
                        connection.raw_dof.id
                    ].position
                    for connection in joint_connections
                }
            )
            if executor.motion_statechart.is_end_motion():
                return trajectory
    finally:
        executor.set_velocity_acceleration_jerk_to_zero()
        executor.motion_statechart.cleanup_nodes(context=executor.context)
        executor.context.cleanup()

    raise MotionDidNotFinish(failed_motions=[task])


def plan_cartesian_trajectory(
    world: World,
    arm_side: Arms,
    goal_pose: Pose,
    translation_only: bool,
    avoid_collisions: bool = True,
    max_ticks: int = DEFAULT_MAX_TICKS,
) -> List[Dict[str, float]]:
    """
    Solve a Cartesian goal against an isolated clone of ``world``, returning the
    resulting joint-space trajectory as a list of per-tick position snapshots for the
    given arm's own joints.

    :param world: The live world to clone; never itself modified.
    :param arm_side: Which arm's tool centre point should reach ``goal_pose``.
    :param goal_pose: Target pose for the arm's tool centre point.
    :param translation_only: If True, only the tip's position is constrained; otherwise
        both position and orientation are.
    :param avoid_collisions: See :func:`_plan_trajectory`.
    :param max_ticks: Tick budget before giving up.
    :return: One dict of joint name to position per tick, in order.
    :raises MotionDidNotFinish: If the goal was not reached within ``max_ticks``.
    """
    scratch_world = deepcopy(world)
    [scratch_robot] = scratch_world.get_semantic_annotations_by_type(Tracy)
    scratch_arm = _arm_of(scratch_robot, arm_side)
    joint_connections = [
        connection
        for connection in scratch_arm.active_connections
        if isinstance(connection, ActiveConnection1DOF)
    ]

    if translation_only:
        task = CartesianPosition(
            root_link=scratch_robot.root,
            tip_link=scratch_arm.end_effector.tool_frame,
            goal_point=goal_pose.to_position(),
        )
    else:
        task = CartesianPose(
            root_link=scratch_robot.root,
            tip_link=scratch_arm.end_effector.tool_frame,
            goal_pose=goal_pose,
        )

    return _plan_trajectory(
        scratch_world, task, joint_connections, avoid_collisions, max_ticks
    )


def plan_joint_trajectory(
    world: World,
    targets: Dict[str, float],
    avoid_collisions: bool = True,
    max_ticks: int = DEFAULT_MAX_TICKS,
) -> List[Dict[str, float]]:
    """
    Solve a joint-space goal against an isolated clone of ``world``, returning the
    resulting trajectory as a list of per-tick position snapshots.

    Uses Giskard's own :class:`~giskardpy.motion_statechart.tasks.joint_tasks.
    JointPositionList` task, which clamps its own reference velocity to each joint's own
    real ``dof.limits.upper.velocity``, so every joint stays within the speed the real
    robot could actually achieve, unlike commanding a target straight to a
    position-servo actuator with no velocity profile at all.

    :param world: The live world to clone; never itself modified.
    :param targets: Target position by joint name.
    :param avoid_collisions: See :func:`_plan_trajectory`.
    :param max_ticks: Tick budget before giving up.
    :return: One dict of joint name to position per tick, in order.
    :raises MotionDidNotFinish: If the goal was not reached within ``max_ticks``.
    """
    scratch_world = deepcopy(world)
    joint_connections = [scratch_world.get_connection_by_name(name) for name in targets]
    goal_state = JointState.from_mapping(dict(zip(joint_connections, targets.values())))
    task = JointPositionList(goal_state=goal_state)

    return _plan_trajectory(
        scratch_world, task, joint_connections, avoid_collisions, max_ticks
    )


def follow_joint_trajectory(
    sim: RealTimeSimulation,
    actuators: Dict[str, Actuator],
    trajectory: List[Dict[str, float]],
    tick_period: float = 1.0 / TARGET_FREQUENCY,
    convergence_threshold: float = 0.01,
    settle_timeout: float = 10.0,
) -> None:
    """
    Drive ``actuators`` through ``trajectory`` on the real, physically simulated world,
    one recorded waypoint per :meth:`~experiments.tracy_experiments.real_time_simulation.
    RealTimeSimulation.advance` step, then hold the final waypoint until every joint
    settles.

    :param sim: The running real-time simulation to drive.
    :param actuators: Every joint's own actuator, keyed by joint name.
    :param trajectory: Waypoints from :func:`plan_cartesian_trajectory`, in order.
    :param tick_period: Simulated seconds to advance per waypoint; matches the tick rate
        the trajectory was planned at.
    :param convergence_threshold: Maximum per-joint error, in radians, to count the
        final waypoint as reached.
    :param settle_timeout: Simulated seconds to wait for convergence after the last
        waypoint, on top of the trajectory's own duration.
    """
    for waypoint in trajectory:
        for joint_name, target in waypoint.items():
            sim.command(actuators[joint_name], target)
        sim.advance(tick_period)

    targets = trajectory[-1]
    simulated_time = 0.0
    errors: Dict[str, float] = {}
    while simulated_time < settle_timeout:
        sim.advance(tick_period)
        simulated_time += tick_period
        errors = {
            joint_name: abs(
                sim.multi_sim.simulator.get_joint_value(joint_name).result - target
            )
            for joint_name, target in targets.items()
        }
        if max(errors.values()) < convergence_threshold:
            return
    worst_joint = max(errors, key=errors.get)
    logger.warning(
        "Trajectory did not settle within %.0fs; worst joint %s is %.3f rad off.",
        settle_timeout,
        worst_joint,
        errors[worst_joint],
    )


def park_arms(
    sim: RealTimeSimulation,
    actuators: Dict[str, Actuator],
    robot: Tracy,
    arm_sides: List[Arms],
    avoid_collisions: bool = True,
    max_ticks: int = DEFAULT_MAX_TICKS,
) -> None:
    """
    Plan a velocity-limited joint trajectory to park ``arm_sides`` and play it back on
    the real, physically simulated world.

    :param sim: The running real-time simulation to drive.
    :param actuators: Every joint's own actuator, keyed by joint name.
    :param robot: The robot whose arms are parked.
    :param arm_sides: Which arms to park, e.g. ``[Arms.LEFT, Arms.RIGHT]``.
    :param avoid_collisions: See :func:`_plan_trajectory`.
    :param max_ticks: Tick budget before giving up.
    """
    targets: Dict[str, float] = {}
    for arm_side in arm_sides:
        park_state = joint_state_of_type(
            _arm_of(robot, arm_side), StaticJointState.PARK
        )
        for connection, target in zip(park_state.connections, park_state.target_values):
            targets[connection.raw_dof.name.name] = target

    trajectory = plan_joint_trajectory(
        robot._world, targets, avoid_collisions=avoid_collisions, max_ticks=max_ticks
    )
    follow_joint_trajectory(sim, actuators, trajectory)


def set_gripper(
    sim: RealTimeSimulation,
    actuators: Dict[str, Actuator],
    robot: Tracy,
    arm_side: Arms,
    state: GripperState,
    max_ticks: int = DEFAULT_MAX_TICKS,
    settle_timeout: float = 3.0,
) -> None:
    """
    Plan a velocity-limited joint trajectory to close or open an arm's gripper and play
    it back on the real, physically simulated world.

    Collision avoidance is always off for this plan (unlike :func:`park_arms`'s own
    default): the goal is to close the fingers around whatever object is between them,
    which collision avoidance would otherwise treat as an obstacle.

    :param sim: The running real-time simulation to drive.
    :param actuators: Every joint's own actuator, keyed by joint name.
    :param robot: The robot whose gripper is driven.
    :param arm_side: Which arm's gripper to drive.
    :param state: The gripper state to command, e.g. :attr:`GripperState.CLOSE`.
    :param max_ticks: Tick budget before giving up.
    :param settle_timeout: Simulated seconds :func:`follow_joint_trajectory` waits for
        convergence after the trajectory's own last waypoint.
    """
    goal_state = joint_state_of_type(_arm_of(robot, arm_side).end_effector, state)
    # The gripper's own connections are a mimic linkage: every one of them shares the
    # same raw_dof, so a naive target per connection would disagree with itself -- a
    # mimic connection's own target is expressed in its own, not the raw_dof's, sign
    # and offset. Convert each connection's own target back to its raw_dof's own value
    # first, so every connection agrees on one target per dof.
    raw_targets: Dict[str, float] = {}
    for connection, target in zip(goal_state.connections, goal_state.target_values):
        raw_targets[connection.raw_dof.name.name] = (
            target - connection.offset
        ) / connection.multiplier

    trajectory = plan_joint_trajectory(
        robot._world, raw_targets, avoid_collisions=False, max_ticks=max_ticks
    )
    follow_joint_trajectory(sim, actuators, trajectory, settle_timeout=settle_timeout)


def _fingertip_body_names(arm_side: Arms) -> Tuple[str, str]:
    """
    The gripper's own two fingertip pad link names, by which arm they belong to.

    :param arm_side: Which arm's gripper to name.
    :return: The left and right fingertip pad link names.
    """
    prefix = "right_" if arm_side == Arms.RIGHT else "left_"
    return (
        f"{prefix}robotiq_85_left_finger_tip_link",
        f"{prefix}robotiq_85_right_finger_tip_link",
    )


SQUEEZE_MARGIN = 0.001
"""
How far, in metres, past a grasped object's own half-width the fingers are commanded to
close, so they press into it firmly rather than merely touching.

Mirrors the proven-working Franka Montessori demo's own
(``montessori_segmind_integration``) ``MoveGripperMotion.squeeze_margin``: kept small,
since it is *commanded* penetration into a rigid object, and the whole point of sizing
the close to the object is to keep that penetration bounded and deliberate.
"""


def _knuckle_raw_dof(robot: Tracy, arm_side: Arms) -> DegreeOfFreedom:
    """
    The raw degree of freedom that actually drives an arm's own gripper knuckle; every
    other finger connection in the mimic linkage follows it.

    :param robot: The robot whose gripper is measured.
    :param arm_side: Which arm's gripper to measure.
    """
    prefix = "right_" if arm_side == Arms.RIGHT else "left_"
    joint_name = f"{prefix}robotiq_85_left_knuckle_joint"
    return next(
        connection.raw_dof
        for connection in _arm_of(robot, arm_side).end_effector.active_connections
        if connection.raw_dof.name.name == joint_name
    )


def _finger_pad_inner_x(
    world: World,
    gripper_root: Body,
    left_tip_body: Body,
    raw_dof: DegreeOfFreedom,
    raw_angle: float,
) -> float:
    """
    The left fingertip pad's own innermost point along the gripper's closing axis, in
    the gripper's own root frame, with the knuckle's raw degree of freedom set to
    ``raw_angle``.

    Kinematic only -- moves ``world``'s own state directly rather than through a physics
    step, so ``world`` must be an isolated scratch copy, never the live, physically
    simulated world.

    :param world: An isolated scratch copy of the world to measure against.
    :param gripper_root: The gripper's own root body.
    :param left_tip_body: The left fingertip pad body.
    :param raw_dof: The knuckle joint's own raw degree of freedom.
    :param raw_angle: The candidate raw angle to measure at.
    """
    world.state[raw_dof.id].position = raw_angle
    world.notify_state_change()
    world.update_forward_kinematics()
    return (
        left_tip_body.collision.as_bounding_box_collection_in_frame(gripper_root)
        .bounding_box()
        .min_x
    )


def _closing_raw_angle_for_half_width(
    world: World,
    robot: Tracy,
    arm_side: Arms,
    target_half_width: float,
    iterations: int = 30,
) -> float:
    """
    The knuckle raw degree of freedom angle at which the fingertip pads' own inner faces
    first reach ``target_half_width`` out from the gripper's own centreline.

    The pad's inner x position decreases monotonically as the knuckle closes (confirmed
    directly, sampled across its own full range: from the pad's own half-open extent
    down to under a millimetre at the joint's own upper limit), so bisection against an
    isolated scratch copy of ``world`` converges reliably.

    :param world: The live world to clone for the search; never itself modified.
    :param robot: The robot whose gripper is measured.
    :param arm_side: Which arm's gripper closes.
    :param target_half_width: The half-width, in metres, to close to.
    :param iterations: Bisection steps; 30 narrows the joint's own ~0.8 rad range to
        well under a micro-radian.
    """
    scratch_world = deepcopy(world)
    [scratch_robot] = scratch_world.get_semantic_annotations_by_type(Tracy)
    prefix = "right_" if arm_side == Arms.RIGHT else "left_"
    gripper_root = _arm_of(scratch_robot, arm_side).end_effector.root
    left_tip_body = scratch_world.get_body_by_name(
        f"{prefix}robotiq_85_left_finger_tip_link"
    )
    raw_dof = _knuckle_raw_dof(scratch_robot, arm_side)

    def inner_x(raw_angle: float) -> float:
        return _finger_pad_inner_x(
            scratch_world, gripper_root, left_tip_body, raw_dof, raw_angle
        )

    lower, upper = raw_dof.limits.lower.position, raw_dof.limits.upper.position
    if target_half_width >= inner_x(lower):
        return lower
    if target_half_width <= inner_x(upper):
        return upper
    for _ in range(iterations):
        midpoint = (lower + upper) / 2
        if inner_x(midpoint) > target_half_width:
            lower = midpoint
        else:
            upper = midpoint
    return upper


def close_gripper_around(
    sim: RealTimeSimulation,
    actuators: Dict[str, Actuator],
    robot: Tracy,
    arm_side: Arms,
    target_body: Body,
    squeeze_margin: float = SQUEEZE_MARGIN,
    max_ticks: int = DEFAULT_MAX_TICKS,
    tick_period: float = 1.0 / TARGET_FREQUENCY,
) -> None:
    """
    Close an arm's gripper around ``target_body``, sized to the object's own width
    instead of always driving to the gripper's fully closed position.

    Closing all the way to zero opening on an object that is not perfectly centred
    between the fingers wedges it sideways rather than gripping it -- confirmed
    directly on Tracy: the fully-closed target let the fingers close *past* a shape's
    own width, shoving it out from between them before both sides ever made contact.
    Mirrors the proven-working Franka Montessori demo's own
    (``montessori_segmind_integration``) fix: measure the target's own half-width along
    the gripper's closing axis, in the gripper's own root frame (so it stays correct
    regardless of the object's orientation relative to the approach), and close to
    that instead, minus :data:`SQUEEZE_MARGIN` so the fingers press in rather than
    merely touch. Also stops early if both fingertip pads register real MuJoCo contact
    against ``target_body`` before reaching the computed target, as a safety net
    against the target being sized slightly off.

    :param sim: The running real-time simulation to drive.
    :param actuators: Every joint's own actuator, keyed by joint name.
    :param robot: The robot whose gripper is driven.
    :param arm_side: Which arm's gripper to drive.
    :param target_body: The body to close around.
    :param squeeze_margin: See :data:`SQUEEZE_MARGIN`.
    :param max_ticks: Tick budget before giving up.
    :param tick_period: Simulated seconds to advance per waypoint; matches the tick rate
        the trajectory was planned at.
    """
    world = robot._world
    gripper_root = _arm_of(robot, arm_side).end_effector.root
    half_width = target_body.collision.as_bounding_box_collection_in_frame(
        gripper_root
    ).bounding_box()
    half_width = (half_width.max_x - half_width.min_x) / 2
    target_inner_x = max(0.0, half_width - squeeze_margin)
    raw_angle = _closing_raw_angle_for_half_width(
        world, robot, arm_side, target_inner_x
    )

    raw_dof = _knuckle_raw_dof(robot, arm_side)
    trajectory = plan_joint_trajectory(
        world,
        {raw_dof.name.name: raw_angle},
        avoid_collisions=False,
        max_ticks=max_ticks,
    )

    simulator = sim.multi_sim.simulator
    left_tip_name, right_tip_name = _fingertip_body_names(arm_side)
    target_name = target_body.name.name

    def both_fingertips_touching() -> bool:
        left_contacts = simulator.get_contact_bodies(
            body_name=left_tip_name, including_children=False
        ).result
        right_contacts = simulator.get_contact_bodies(
            body_name=right_tip_name, including_children=False
        ).result
        return target_name in left_contacts and target_name in right_contacts

    for waypoint in trajectory:
        for joint_name, target in waypoint.items():
            sim.command(actuators[joint_name], target)
        sim.advance(tick_period)
        if both_fingertips_touching():
            logger.info(
                "%s: gripper stopped early on both-fingertip contact.", target_body.name
            )
            return
    logger.info(
        "%s: gripper closed to its own half-width-sized target (%.4fm).",
        target_body.name,
        target_inner_x,
    )
