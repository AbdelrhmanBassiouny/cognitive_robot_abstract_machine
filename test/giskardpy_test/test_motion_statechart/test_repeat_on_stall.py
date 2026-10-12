"""
Tests for ``RepeatOnStall`` (see ``giskardpy/motion_statechart/goals/templates.py``),
exercised against a motion that really does stop making progress.

The loop it builds on
is tested with ``test/cramph_test/test_statechart/test_repeat_until.py``.
"""

from datetime import timedelta
from functools import partial

from cramph.data_types import ObservationStateValues
from cramph.composites import Attempt
from giskardpy.motion_statechart.goals.templates import RepeatOnStall
from giskardpy.motion_statechart.graph_node import EndMotion
from cramph.statechart import Statechart
from cramph.monitors import CountNodeResets, CountTicks
from giskardpy.motion_statechart.monitors.progress_monitors import Stalled
from cramph.nodes_for_testing import ConstFalseNode
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPosition
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World

from .test_progress_monitors import unreachable_arm_goal
from ...cramph_test.test_statechart.test_repeat_until import (
    ATTEMPT_TICKS,
    SETTLE_TICKS,
    _repeat_on_timeout,
)
from giskardpy.motion_control import MotionControl
from cramph.context import StatechartContext
from cramph.executor import StatechartExecutor

STALL_TIMEOUT_OUTLASTING_THE_TEST = timedelta(days=1)
"""
A stall timeout no world free test below runs long enough to reach.
"""

# %% the stall timeout


def _repeat_on_stall(**timeout_argument) -> RepeatOnStall:
    """
    Build a loop around a placeholder task and let it join a statechart, to read back
    how its stall timeout reached the progress monitor.
    """
    task = ConstFalseNode(name="task")
    loop = RepeatOnStall(
        name="loop",
        task=task,
        stop_retry_monitor=CountNodeResets(name="counter", node=task, target=1),
        **timeout_argument,
    )
    Statechart(context=StatechartContext(world=World())).add_node(loop)
    return loop


def test_repeat_on_stall_retries_when_a_failure_monitor_of_its_attempt_fires():
    """
    An attempt handed to the stall loop keeps giving up on its own failure monitors, so
    the loop retries it without waiting for a stall.
    """
    task = ConstFalseNode(name="task")
    loop, _, executor = _repeat_on_timeout(
        StatechartExecutor(
            context=StatechartContext(world=World()), extensions=[MotionControl()]
        ),
        task,
        target=3,
        repeat_template=partial(
            RepeatOnStall, timeout=STALL_TIMEOUT_OUTLASTING_THE_TEST
        ),
    )

    for _ in range(SETTLE_TICKS):
        executor.tick()

    assert loop.stop_retry_monitor.resets == 3
    assert loop.last_observation_state == ObservationStateValues.FALSE


def test_stall_timeout_reaches_the_progress_monitor():
    """
    The window the loop was configured with is what its progress monitor watches.
    """
    timeout = timedelta(days=1, seconds=30)

    loop = _repeat_on_stall(timeout=timeout)

    assert loop.task.failure_monitors[0].timeout == timeout


def test_default_stall_timeout_leaves_an_attempt_time_to_converge():
    """
    The default window spans several seconds of simulated time, so an attempt is not
    declared stalled on the first control cycle in which nothing moves.
    """
    loop = _repeat_on_stall()

    assert loop.task.failure_monitors[0].timeout == timedelta(seconds=5)


def test_repeat_on_stall_watches_the_task_of_an_attempt_it_is_handed():
    """
    An attempt handed to the stall loop is kept, and giving up on a stall becomes one
    more of its ways of failing, measured on the task it runs.
    """
    task = ConstFalseNode(name="task")
    given_monitor = CountTicks(name="timeout", ticks=ATTEMPT_TICKS)
    attempt = Attempt(name="attempt", task=task, failure_monitors=[given_monitor])

    loop = RepeatOnStall(
        name="loop",
        task=attempt,
        stop_retry_monitor=CountNodeResets(name="counter", node=attempt, target=1),
    )
    Statechart(context=StatechartContext(world=World())).add_node(loop)

    assert loop.task is attempt
    [kept_monitor, stall_monitor] = attempt.failure_monitors
    assert kept_monitor is given_monitor
    assert type(stall_monitor) is Stalled
    assert stall_monitor.monitored_node is task


def test_repeat_on_stall_retries_a_motion_that_stops_converging(
    pr2_world_state_reset: World,
):
    """
    An arm that has extended as far as it can stops closing on its goal, so the attempt
    is given up on and started again, until the monitor calls it off.
    """
    task = unreachable_arm_goal(pr2_world_state_reset)
    loop = RepeatOnStall(
        name="loop",
        task=task,
        stop_retry_monitor=CountNodeResets(name="counter", node=task, target=2),
        timeout=timedelta(seconds=1),
    )
    executor = StatechartExecutor(
        context=StatechartContext(world=pr2_world_state_reset),
        extensions=[MotionControl()],
    )
    motion_statechart = Statechart(context=executor.context)
    motion_statechart.add_node(loop)
    motion_statechart.add_node(EndMotion.when_true(loop))

    executor.compile(statechart=motion_statechart)
    for _ in range(2000):
        executor.tick()
        if loop.last_observation_state == ObservationStateValues.FALSE:
            break

    assert loop.stop_retry_monitor.resets == 2
    assert loop.last_observation_state == ObservationStateValues.FALSE


def test_repeat_on_stall_leaves_a_reachable_motion_alone(cylinder_bot_world: World):
    """
    A goal the robot converges on is never mistaken for a stalled attempt.
    """
    bot = cylinder_bot_world.get_kinematic_structure_entity_by_name("bot")
    task = CartesianPosition(
        root_link=cylinder_bot_world.root,
        tip_link=bot,
        goal_point=Point3(1, 0, 0, reference_frame=cylinder_bot_world.root),
    )
    loop = RepeatOnStall(
        name="loop",
        task=task,
        stop_retry_monitor=CountNodeResets(name="counter", node=task, target=1),
        timeout=timedelta(seconds=0.5),
    )
    executor = StatechartExecutor(
        context=StatechartContext(world=cylinder_bot_world),
        extensions=[MotionControl()],
    )
    motion_statechart = Statechart(context=executor.context)
    motion_statechart.add_node(loop)
    motion_statechart.add_node(EndMotion.when_true(loop))

    executor.compile(statechart=motion_statechart)
    executor.tick_until_end(2000)

    assert loop.stop_retry_monitor.resets == 0
    assert loop.last_observation_state == ObservationStateValues.TRUE
