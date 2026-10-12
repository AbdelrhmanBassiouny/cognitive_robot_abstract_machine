"""
Tests for ``Attempt`` (see ``cramph/src/cramph/composites.py``).

The template is exercised by compiling it into a real :class:`Statechart` and ticking
the executor. ``ConstTrueNode`` / ``ConstFalseNode`` stand in for a task that is always
/ never at its goal, and ``CountTicks`` for a failure monitor that fires after a known
number of ticks, so none of these tests needs a world with a robot in it.
"""

import pytest
from cramph.executor import StatechartExecutor
from cramph.context import StatechartContext
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.composites import Attempt, Sequence
from cramph.exceptions import AttemptWithoutFailureMonitorsError
from cramph.node import StatechartNode
from cramph.statechart import Statechart
from cramph.monitors import CountTicks, Pulse
from cramph.nodes_for_testing import (
    ConstFalseNode,
    ConstTrueNode,
    NodeDeclaringItsOwnFailure,
    NodeObservingNothingYet,
)
from semantic_digital_twin.world import World

# Ticks after which the attempts below have settled on an outcome.
SETTLE_TICKS = 6

# Ticks a failure monitor is given before it fires. Small enough that
# SETTLE_TICKS still covers the ticks the attempt needs to react to it.
TICKS_UNTIL_GIVING_UP = 2


def _compile(
    node: StatechartNode,
) -> tuple[Statechart, StatechartExecutor]:
    """
    Add the node to a fresh statechart and compile it.

    :param node: The template under test.
    :return: The chart, so a caller can read its recorded history, and the executor.
    """
    executor = StatechartExecutor(StatechartContext(world=World()))
    statechart = Statechart(context=executor.context)
    statechart.add_node(node)
    executor.compile(statechart=statechart)
    return statechart, executor


def _compile_and_tick(
    node: StatechartNode, ticks: int = SETTLE_TICKS
) -> tuple[Statechart, StatechartExecutor]:
    """
    Add the node to a fresh statechart, compile it and tick the executor.

    :param node: The template under test.
    :param ticks: Ticks to run after compiling.
    :return: The chart and the executor, so a caller can keep ticking and inspect
        intermediate states.
    """
    statechart, executor = _compile(node)
    for _ in range(ticks):
        executor.tick()
    return statechart, executor


# %% reaching the goal


def test_an_attempt_succeeds_once_its_task_reaches_its_goal():
    """
    A task at its goal is what this template is waiting for, and it says so itself
    rather than leaving the caller to read the task.

    What it observed is read through its last observation, because the observation
    behind it is gone once the attempt ended. The outcome belongs to the attempt: the
    task it held open is only taken down with it.
    """
    task = ConstTrueNode(name="task")
    attempt = Attempt(task=task, failure_monitors=[ConstFalseNode()])

    _compile_and_tick(attempt)

    assert attempt.last_observation_state == ObservationStateValues.TRUE
    assert attempt.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert task.life_cycle_state == LifeCycleValues.INTERRUPTED


def test_an_attempt_ends_itself_without_anything_wiring_a_success_condition():
    """
    Supplying the ending a task cannot produce is the whole point of the template, so it
    must not depend on a parent having wired one.
    """
    attempt = Attempt(
        task=ConstTrueNode(name="task"), failure_monitors=[ConstFalseNode()]
    )

    _compile_and_tick(attempt)

    assert attempt.life_cycle_state.is_terminal


# %% giving up


def test_an_attempt_fails_once_a_failure_monitor_fires():
    """
    A monitor that fires is the only thing that ends a task short of its goal, and it is
    reported as a failure rather than as a task still on its way.
    """
    task = ConstFalseNode(name="task")
    attempt = Attempt(
        task=task,
        failure_monitors=[CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="gave_up")],
    )

    _compile_and_tick(attempt)

    assert attempt.last_observation_state == ObservationStateValues.FALSE
    assert attempt.life_cycle_state == LifeCycleValues.FAILED
    # The attempt is what gave up; the task was only taken down with it.
    assert task.life_cycle_state == LifeCycleValues.INTERRUPTED


def test_an_attempt_holds_its_task_open_until_it_is_decided():
    """
    A constraint that stops running stops being enforced, so the task keeps running for
    as long as neither outcome has been decided.
    """
    task = ConstFalseNode(name="task")
    attempt = Attempt(
        task=task,
        failure_monitors=[CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="gave_up")],
    )

    _compile_and_tick(attempt, ticks=TICKS_UNTIL_GIVING_UP - 1)

    assert attempt.observation_state == ObservationStateValues.UNKNOWN
    assert task.life_cycle_state == LifeCycleValues.RUNNING


def test_giving_up_on_a_task_that_observed_nothing_interrupts_it():
    """
    A failure monitor fails the attempt, and the attempt ending interrupts its task,
    because a node whose parent ended is interrupted whatever it observed.
    """
    task = NodeObservingNothingYet(name="task")
    attempt = Attempt(
        task=task,
        failure_monitors=[CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="gave_up")],
    )

    _compile_and_tick(attempt)

    assert task.life_cycle_state == LifeCycleValues.INTERRUPTED
    assert attempt.life_cycle_state == LifeCycleValues.FAILED


def test_an_attempt_observes_nothing_while_neither_outcome_has_happened():
    """
    A task that has not arrived yet has not failed, so the observation stays undecided
    rather than reading as a failure the whole way there.
    """
    attempt = Attempt(
        task=ConstFalseNode(name="task"),
        failure_monitors=[CountTicks(ticks=99, name="gave_up")],
    )

    statechart, _ = _compile_and_tick(attempt)

    assert set(statechart.history.get_observation_history_of_node(attempt)) == {
        ObservationStateValues.UNKNOWN
    }


def test_an_attempt_without_failure_monitors_is_rejected():
    """
    Without a failure monitor nothing could give up on the task, which is what an
    attempt exists to decide.
    """
    with pytest.raises(AttemptWithoutFailureMonitorsError):
        Attempt(task=ConstFalseNode(name="task"), failure_monitors=[])


def test_an_attempt_whose_failure_monitors_never_fire_never_gives_up():
    """
    Being short of its goal is no failure, so only a failure monitor ends an attempt
    short of it.
    """
    attempt = Attempt(
        task=ConstFalseNode(name="task"),
        failure_monitors=[ConstFalseNode(name="never gives up")],
    )

    _, executor = _compile(attempt)

    with pytest.raises(TimeoutError):
        executor.tick_until_end(timeout=SETTLE_TICKS)


def test_an_attempt_fails_once_its_task_ended_without_succeeding():
    """
    A task that ended on its own is as decided as one a monitor gave up on, and an
    attempt still waiting for it would never end.
    """
    task = Attempt(
        task=ConstFalseNode(name="inner_task"),
        failure_monitors=[CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="gave_up")],
    )
    attempt = Attempt(task=task, failure_monitors=[ConstFalseNode()])

    _compile_and_tick(attempt)

    assert task.life_cycle_state == LifeCycleValues.FAILED
    assert attempt.last_observation_state == ObservationStateValues.FALSE
    assert attempt.life_cycle_state == LifeCycleValues.FAILED


def test_an_attempt_fails_once_its_task_failed_while_observing_true():
    """
    A task that declared its own failure did not reach its goal, whatever it observed on
    the tick it failed, so its last observation must not count as an arrival.
    """
    task = ConstTrueNode(name="task")
    task.fail_condition = task.observes_true
    attempt = Attempt(task=task, failure_monitors=[ConstFalseNode()])

    _compile_and_tick(attempt)

    assert task.life_cycle_state == LifeCycleValues.FAILED
    assert attempt.life_cycle_state == LifeCycleValues.FAILED


def test_reaching_the_goal_wins_over_a_failure_on_the_same_tick():
    """
    A monitor firing on the tick the statechart arrives must not undo the arrival.
    """
    attempt = Attempt(
        task=ConstTrueNode(name="task"),
        failure_monitors=[ConstTrueNode(name="gave_up")],
    )

    _compile_and_tick(attempt)

    assert attempt.last_observation_state == ObservationStateValues.TRUE
    assert attempt.life_cycle_state == LifeCycleValues.SUCCEEDED


# %% why an attempt was given up on


def test_failure_reasons_names_the_monitor_that_fired():
    """
    Which monitor ended an attempt is what turns a failure into a reason, so it has to
    survive the monitor being taken down along with the attempt.
    """
    fired = CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="fired")
    stayed_quiet = CountTicks(ticks=99, name="stayed_quiet")
    attempt = Attempt(
        task=ConstFalseNode(name="task"), failure_monitors=[fired, stayed_quiet]
    )

    _compile_and_tick(attempt)

    assert attempt.failure_reasons == [fired]


def test_failure_reasons_is_empty_once_the_task_reached_its_goal():
    """
    Nothing gave up on an attempt that arrived, so there is no reason to report.
    """
    attempt = Attempt(
        task=ConstTrueNode(name="task"),
        failure_monitors=[CountTicks(ticks=99, name="gave_up")],
    )

    _compile_and_tick(attempt)

    assert attempt.failure_reasons == []


def test_failure_reasons_names_a_monitor_that_fired_for_a_single_tick():
    """
    The monitor is back to observing nothing after its single tick, so the attempt has
    to name it from the observation the monitor ended with.
    """
    fired_briefly = Pulse(name="fired_briefly")
    attempt = Attempt(
        task=ConstFalseNode(name="task"), failure_monitors=[fired_briefly]
    )

    _compile_and_tick(attempt)

    assert attempt.life_cycle_state == LifeCycleValues.FAILED
    assert attempt.failure_reasons == [fired_briefly]


def test_failure_reasons_is_empty_when_a_monitor_fired_but_the_goal_was_reached():
    """
    Nothing was given up on when the task arrived anyway, so a monitor that fired on
    that same tick is not a reason for anything.
    """
    attempt = Attempt(
        task=ConstTrueNode(name="task"),
        failure_monitors=[ConstTrueNode(name="fired")],
    )

    _compile_and_tick(attempt)

    assert attempt.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert attempt.failure_reasons == []


def test_failure_reasons_lists_every_monitor_that_fired_at_once():
    """
    Two monitors can fire on the same tick, and neither of them is more the reason than
    the other.
    """
    first = CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="first")
    second = CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="second")
    attempt = Attempt(
        task=ConstFalseNode(name="task"), failure_monitors=[first, second]
    )

    _compile_and_tick(attempt)

    assert attempt.failure_reasons == [first, second]


# %% attempts as steps of an RPL style template


def test_an_attempt_is_a_usable_sequence_step():
    """
    A step that ends itself is what a sequence needs to move on, which is what wrapping
    a task in an attempt buys.
    """
    first = Attempt(
        task=ConstTrueNode(name="first_task"), failure_monitors=[ConstFalseNode()]
    )
    second = Attempt(
        task=ConstTrueNode(name="second_task"), failure_monitors=[ConstFalseNode()]
    )

    _compile_and_tick(Sequence(nodes=[first, second]))

    assert first.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert second.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_failed_attempt_makes_its_sequence_report_a_failure():
    """
    A step that can never succeed used to leave a sequence waiting forever, because a
    task short of its goal never ends.

    An attempt ends on its failure monitor instead, which is the outcome the sequence
    was already looking for.
    """
    failing_step = Attempt(
        task=ConstFalseNode(name="task"),
        failure_monitors=[CountTicks(ticks=TICKS_UNTIL_GIVING_UP, name="gave_up")],
    )
    sequence = Sequence(
        nodes=[
            failing_step,
            Attempt(
                task=ConstTrueNode(name="never_reached"),
                failure_monitors=[ConstFalseNode()],
            ),
        ]
    )

    _compile_and_tick(sequence)

    assert failing_step.life_cycle_state == LifeCycleValues.FAILED
    assert sequence.last_observation_state == ObservationStateValues.FALSE


def test_a_task_that_fails_on_its_own_makes_its_sequence_report_a_failure():
    """
    A task may declare that it cannot continue, and the sequence running it has to
    report that rather than stay open forever.
    """
    task = NodeDeclaringItsOwnFailure(name="task")
    sequence = Sequence(nodes=[task])

    _compile_and_tick(sequence)

    assert task.life_cycle_state == LifeCycleValues.FAILED
    assert sequence.life_cycle_state == LifeCycleValues.FAILED
    assert sequence.last_observation_state == ObservationStateValues.FALSE
