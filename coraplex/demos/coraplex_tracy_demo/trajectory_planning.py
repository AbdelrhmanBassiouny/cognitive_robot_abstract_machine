"""
Plan Cartesian- or joint-space goals against an isolated, physics-free scratch copy of
the world via Giskard, then play the resulting trajectory back onto the real, physically
simulated MuJoCo world by driving each joint's own position-servo actuator directly.

Giskard never touches the live, physically simulated world under this module: it only
ever ticks against a :func:`copy.deepcopy` of it, so it cannot race
:class:`~semantic_digital_twin.adapters.multi_sim.MujocoSynchronizer`'s own
physics-thread state sync -- the race documented in :mod:`tracy_equipment`'s own
module docstring, and confirmed this session to also stall a purely kinematic joint's
motion once solved together with a physically simulated one. Execution then drives
real MuJoCo actuators the same way :mod:`demo`'s own park loop does, so tracking is
genuinely closed-loop against measured physics, not open-loop trajectory replay.

Every motion here, including park and gripper open/close, is planned this way rather
than commanded straight to the target: see :func:`plan_joint_trajectory`'s own
docstring for why commanding a target directly, with no velocity profile at all (as an
earlier version of this module, and :mod:`demo`'s own park loop, both do), lets a joint
move far faster than its real hardware ever could.
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
from typing_extensions import Dict, List

from coraplex.datastructures.enums import Arms
from coraplex.exceptions import MotionDidNotFinish
from coraplex.plans.executables import GiskardExecutable
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.world_entity import Actuator

from real_time_simulation import RealTimeSimulation
from tracy_equipment import joint_state_of_type

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

    Shared by :func:`plan_cartesian_trajectory` and :func:`plan_joint_trajectory`: both
    are one Giskard task ticked in isolation until :meth:`~giskardpy.motion_statechart.
    motion_statechart.MotionStatechart.is_end_motion`, differing only in which kind of
    task drives the goal.

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
    # Unlike the live Giskard execution this replaces, collision avoidance defaults to
    # on here: this is the only place a path is actually chosen (execution just
    # replays it), and skipping it lets Giskard route straight through the table --
    # confirmed directly, a naive plan drove left_wrist_2_link into real contact with
    # the table and stalled there.
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

    Ticks Giskard purely in-memory against a :func:`copy.deepcopy` of ``world`` -- a
    fresh clone with no simulator or state-change callbacks attached (see
    :meth:`~semantic_digital_twin.world.World.__deepcopy__`) -- so nothing else ever
    reads or writes it while Giskard solves; the live world passed in is never
    modified by this function.

    :param world: The live world to clone; never itself modified.
    :param arm_side: Which arm's tool centre point should reach ``goal_pose``.
    :param goal_pose: Target pose for the arm's tool centre point.
    :param translation_only: If True, only the tip's position is constrained (matching
        ``MovementType.TRANSLATION``); otherwise both position and orientation are.
    :param avoid_collisions: See :func:`_plan_trajectory`.
    :param max_ticks: Tick budget before giving up.
    :return: One dict of joint name to position per tick, in order.
    :raises MotionDidNotFinish: If the goal was not reached within ``max_ticks``.
    """
    scratch_world = deepcopy(world)
    # `deepcopy` replays the original world's own model-modification history (see
    # `World.__deepcopy__`), which already includes whatever `Tracy.from_world` call
    # produced the live `robot` passed in -- re-running it here would try to assign
    # the same robot parts to a second robot and fail. The clone already carries its
    # own equivalent `Tracy` semantic annotation; just look it up.
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
    JointPositionList` task, the same one a live-executed ``ParkArmsAction``/
    ``MoveGripperMotion`` builds -- which clamps its own reference velocity to each
    joint's own real ``dof.limits.upper.velocity`` -- so, unlike commanding a target
    straight to a position-servo actuator with no velocity profile at all (this
    function's own first version, and :mod:`demo`'s own park loop), every joint stays
    within the speed the real robot could actually achieve. Confirmed directly: a
    joint whose own real hardware caps it at 0.13 rad/s peaked at nearly 7 rad/s when
    commanded that way -- over 50x faster than the real robot could ever move, and
    meaningless as a training signal for real-world velocities.

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
    one recorded waypoint per :meth:`~real_time_simulation.RealTimeSimulation.advance`
    step, then hold the final waypoint until every joint settles.

    Each joint's own real position-servo actuator does the actual tracking, reacting to
    genuine measured position every physics step -- this is closed-loop tracking of a
    moving reference, not open-loop trajectory replay. A high-inertia joint (e.g. the
    shoulder, carrying the whole rest of the arm) can lag the reference throughout a
    fast-moving trajectory, so the final waypoint is held and polled for convergence the
    same way :func:`park_arms` does, rather than ending the instant the last waypoint
    was sent.

    :param sim: The running real-time simulation to drive.
    :param actuators: Every joint's own actuator, keyed by joint name (see
        :func:`tracy_equipment.equip_arms_with_servos`).
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

    The park target is a static joint configuration already known ahead of time (see
    :func:`tracy_equipment.joint_state_of_type`), planned via
    :func:`plan_joint_trajectory` (Giskard still never touches the live world -- only
    the isolated scratch copy that function plans against) rather than commanded
    straight to the actuator the way this function's own earlier version, and
    :mod:`demo`'s own park loop, both do: see :func:`plan_joint_trajectory`'s own
    docstring for why that leaves every joint free to move far faster than the real
    robot's own hardware ever could.

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
    which collision avoidance would otherwise treat as an obstacle -- see
    :func:`_plan_trajectory`'s own docstring. :func:`follow_joint_trajectory`'s own
    settle timeout already tolerates never reaching the nominal fully-closed target
    exactly, which a squeeze against a rigid grasped object should not.

    :param sim: The running real-time simulation to drive.
    :param actuators: Every joint's own actuator, keyed by joint name (see
        :func:`tracy_equipment.equip_grippers_with_servos`).
    :param robot: The robot whose gripper is driven.
    :param arm_side: Which arm's gripper to drive.
    :param state: The gripper state to command, e.g. :attr:`GripperState.CLOSE`.
    :param max_ticks: Tick budget before giving up.
    :param settle_timeout: Simulated seconds :func:`follow_joint_trajectory` waits for
        convergence after the trajectory's own last waypoint.
    """
    goal_state = joint_state_of_type(_arm_of(robot, arm_side).end_effector, state)
    # The gripper's own connections are a mimic linkage: every one of them shares the
    # same raw_dof (see equip_grippers_with_servos's own docstring), so a naive target
    # per connection would disagree with itself -- a mimic connection's own target is
    # expressed in its own, not the raw_dof's, sign and offset (e.g. the right
    # knuckle's own -0.8 for the same physical close position the left knuckle's own
    # +0.8 means). Convert each connection's own target back to its raw_dof's own
    # value first, so every connection agrees on one target per dof.
    raw_targets: Dict[str, float] = {}
    for connection, target in zip(goal_state.connections, goal_state.target_values):
        raw_targets[connection.raw_dof.name.name] = (
            target - connection.offset
        ) / connection.multiplier

    trajectory = plan_joint_trajectory(
        robot._world, raw_targets, avoid_collisions=False, max_ticks=max_ticks
    )
    follow_joint_trajectory(sim, actuators, trajectory, settle_timeout=settle_timeout)
