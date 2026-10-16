from __future__ import annotations

import pytest
from typing_extensions import List

from cramph.composites import (
    Attempt,
    CramLanguageNode,
    Parallel,
    Sequence,
    TryAll,
    TryInOrder,
)
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.exceptions import (
    ChildCannotBeWrappedError,
    NodeAlreadyAChildError,
    NodeIsNotAChildError,
    NotRunByLanguageNodeError,
    StatechartAlreadyCompiledError,
    TopLevelNodeCannotBeWrappedError,
)
from cramph.executor import StatechartExecutor
from cramph.node import EndStatechart, StatechartNode
from cramph.nodes_for_testing import (
    ConstFalseNode,
    ConstTrueNode,
    NodeFailingOnObservingFalse,
    NodeObservingAFixedValue,
    NodeSucceedingOnObservingTrue,
)
from cramph.statechart import Statechart

# %% helpers


def _succeeding(name: str) -> NodeSucceedingOnObservingTrue:
    """
    :return: A node that succeeds as soon as it observes, which it does right away.
    """
    return NodeSucceedingOnObservingTrue(
        name=name, observation=ObservationStateValues.TRUE
    )


def _failing(name: str) -> NodeFailingOnObservingFalse:
    """
    :return: A node that fails as soon as it observes, which it does right away.
    """
    return NodeFailingOnObservingFalse(
        name=name, observation=ObservationStateValues.FALSE
    )


def _run(
    executor: StatechartExecutor, statechart: Statechart, goal: StatechartNode
) -> None:
    """
    Compiles `statechart` with an end once `goal` ended, and ticks it until then.
    """
    statechart.add_node(EndStatechart.when_true(goal))
    executor.compile(statechart)
    executor.tick_until_end(timeout=100)


def _start_order(
    statechart: Statechart, nodes: List[StatechartNode]
) -> List[StatechartNode]:
    """
    :return: Those of `nodes` that started, ordered by the tick they started in.
    """
    first_running_tick = {}
    for node in nodes:
        history = statechart.history.get_life_cycle_history_of_node(node)
        started = [
            tick
            for tick, state in enumerate(history)
            if state != LifeCycleValues.NOT_STARTED
        ]
        if started:
            first_running_tick[node] = started[0]
    assert len(set(first_running_tick.values())) == len(first_running_tick)
    return sorted(first_running_tick, key=first_running_tick.get)


# %% sequence


def test_a_step_inserted_before_another_runs_right_before_it(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, second, third = _succeeding("1"), _succeeding("2"), _succeeding("3")
    statechart.add_node(sequence := Sequence(nodes=[first, third]))

    sequence.insert_before(third, second)
    _run(statechart_executor, statechart, sequence)

    assert _start_order(statechart, [third, second, first]) == [first, second, third]
    assert sequence.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_step_inserted_before_the_first_one_runs_first(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, second = _succeeding("1"), _succeeding("2")
    statechart.add_node(sequence := Sequence(nodes=[second]))

    sequence.insert_before(second, first)
    _run(statechart_executor, statechart, sequence)

    assert _start_order(statechart, [second, first]) == [first, second]


def test_a_step_inserted_after_the_last_one_runs_last(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, second, third = _succeeding("1"), _succeeding("2"), _succeeding("3")
    statechart.add_node(sequence := Sequence(nodes=[first, second]))

    sequence.insert_after(second, third)
    _run(statechart_executor, statechart, sequence)

    assert _start_order(statechart, [third, second, first]) == [first, second, third]


def test_a_step_inserted_after_another_runs_right_after_it(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, second, third = _succeeding("1"), _succeeding("2"), _succeeding("3")
    statechart.add_node(sequence := Sequence(nodes=[first, third]))

    sequence.insert_after(first, second)
    _run(statechart_executor, statechart, sequence)

    assert _start_order(statechart, [third, second, first]) == [first, second, third]


def test_a_replaced_step_leaves_the_statechart_and_its_replacement_runs_in_its_place(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, replaced, third = _succeeding("1"), _succeeding("x"), _succeeding("3")
    second = _succeeding("2")
    statechart.add_node(sequence := Sequence(nodes=[first, replaced, third]))

    sequence.replace(replaced, second)
    _run(statechart_executor, statechart, sequence)

    assert replaced not in statechart.nodes
    assert _start_order(statechart, [third, second, first]) == [first, second, third]


def test_a_sequence_that_did_not_join_yet_only_changes_its_list(
    statechart_executor: StatechartExecutor,
):
    first, second, third = _succeeding("1"), _succeeding("2"), _succeeding("3")
    sequence = Sequence(nodes=[first, third])

    sequence.insert_before(third, second)

    assert sequence.nodes == [first, second, third]
    assert not second.belongs_to_statechart()


# %% trying alternatives in order


def test_an_inserted_alternative_starts_once_the_one_before_it_failed(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, second, third = _failing("1"), _failing("2"), _succeeding("3")
    statechart.add_node(alternatives := TryInOrder(nodes=[first, third]))

    alternatives.insert_after(first, second)
    _run(statechart_executor, statechart, alternatives)

    assert _start_order(statechart, [third, second, first]) == [first, second, third]
    assert alternatives.life_cycle_state == LifeCycleValues.SUCCEEDED


# %% children running side by side


def test_an_alternative_inserted_into_try_all_can_decide_it(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    failing = _failing("fails")
    statechart.add_node(alternatives := TryAll(nodes=[failing]))

    alternatives.insert_after(failing, _succeeding("works"))
    _run(statechart_executor, statechart, alternatives)

    assert alternatives.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_node_inserted_into_a_parallel_counts_towards_its_observation(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    at_goal = NodeObservingAFixedValue(observation=ObservationStateValues.TRUE)
    statechart.add_node(parallel := Parallel(nodes=[at_goal]))

    parallel.insert_after(
        at_goal, NodeObservingAFixedValue(observation=ObservationStateValues.FALSE)
    )
    statechart_executor.compile(statechart)
    statechart_executor.tick()

    assert parallel.observation_state == ObservationStateValues.FALSE


def test_a_parallel_can_still_arrive_through_a_node_inserted_after_it_joined(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    failing = _failing("fails")
    statechart.add_node(parallel := Parallel(nodes=[failing], minimum_success=1))

    parallel.insert_after(
        failing, NodeObservingAFixedValue(observation=ObservationStateValues.TRUE)
    )
    statechart_executor.compile(statechart)
    statechart_executor.tick()
    statechart_executor.tick()

    assert failing.life_cycle_state == LifeCycleValues.FAILED
    assert parallel.life_cycle_state == LifeCycleValues.RUNNING
    assert parallel.observation_state == ObservationStateValues.TRUE


# %% wrapping a node


def _at_goal(name: str) -> NodeObservingAFixedValue:
    """
    :return: A node that observes being at its goal and leaves ending it to its owner.
    """
    return NodeObservingAFixedValue(name=name, observation=ObservationStateValues.TRUE)


def test_a_wrapped_step_runs_inside_its_wrapper_where_it_ran_before(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, wrapped, third = _succeeding("1"), _at_goal("wrapped"), _succeeding("3")
    beside = _at_goal("beside")
    statechart.add_node(sequence := Sequence(nodes=[first, wrapped, third]))
    wrapper = Parallel(nodes=[beside])

    wrapper.wrap(wrapped)
    _run(statechart_executor, statechart, sequence)

    assert sequence.nodes == [first, wrapper, third]
    assert wrapper.nodes == [wrapped, beside]
    assert wrapped.parent_node is wrapper
    assert _start_order(statechart, [third, wrapper, first]) == [first, wrapper, third]
    assert sequence.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_wrapped_node_is_no_longer_ended_by_the_node_that_ran_it(
    statechart_executor: StatechartExecutor,
):
    """
    The sequence ended the step once it was at its goal; a parallel ends none of its
    nodes, so inside one the step keeps running while its sibling is not at its goal.
    """
    statechart = Statechart(context=statechart_executor.context)
    wrapped = _at_goal("wrapped")
    statechart.add_node(Sequence(nodes=[wrapped]))
    Parallel(
        nodes=[NodeObservingAFixedValue(observation=ObservationStateValues.FALSE)]
    ).wrap(wrapped)

    statechart_executor.compile(statechart)
    statechart_executor.tick()
    statechart_executor.tick()

    assert wrapped.life_cycle_state == LifeCycleValues.RUNNING


def test_wrapping_a_top_level_node_is_rejected(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    statechart.add_node(top_level := _at_goal("top level"))

    with pytest.raises(TopLevelNodeCannotBeWrappedError):
        Parallel(nodes=[_at_goal("beside")]).wrap(top_level)


def test_wrapping_a_node_its_owner_cannot_hand_over_is_rejected(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    task = _at_goal("task")
    statechart.add_node(Attempt(task=task, failure_monitors=[ConstFalseNode()]))

    with pytest.raises(ChildCannotBeWrappedError):
        Parallel(nodes=[_at_goal("beside")]).wrap(task)


def test_wrapping_a_node_of_a_compiled_statechart_is_rejected(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    wrapped = _at_goal("wrapped")
    statechart.add_node(sequence := Sequence(nodes=[wrapped]))
    statechart.add_node(EndStatechart.when_true(sequence))
    statechart_executor.compile(statechart)

    with pytest.raises(StatechartAlreadyCompiledError):
        Parallel(nodes=[_at_goal("beside")]).wrap(wrapped)


# %% the language node running a node


def test_the_language_node_running_a_nested_node_is_the_first_one_above_it(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    nested = _succeeding("nested")
    attempt = Attempt(name="attempt", task=nested, failure_monitors=[ConstFalseNode()])
    statechart.add_node(sequence := Sequence(nodes=[attempt]))

    assert CramLanguageNode.running(nested) is sequence


def test_a_step_inserted_before_a_nested_node_runs_before_what_holds_it(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first, nested = _succeeding("1"), _succeeding("nested")
    attempt = Attempt(name="attempt", task=nested, failure_monitors=[ConstFalseNode()])
    statechart.add_node(sequence := Sequence(nodes=[attempt]))

    CramLanguageNode.running(nested).insert_before(nested, first)
    _run(statechart_executor, statechart, sequence)

    assert _start_order(statechart, [attempt, first]) == [first, attempt]


def test_a_node_no_language_node_runs_has_none_running_it(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    statechart.add_node(top_level := _succeeding("top level"))

    with pytest.raises(NotRunByLanguageNodeError):
        CramLanguageNode.running(top_level)


# %% misuse


def test_inserting_next_to_a_node_the_goal_does_not_run_is_rejected(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    statechart.add_node(sequence := Sequence(nodes=[_succeeding("1")]))

    with pytest.raises(NodeIsNotAChildError):
        sequence.insert_before(_succeeding("stranger"), _succeeding("2"))


def test_inserting_a_node_the_goal_already_runs_is_rejected(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    first = _succeeding("1")
    statechart.add_node(sequence := Sequence(nodes=[first]))

    with pytest.raises(NodeAlreadyAChildError):
        sequence.insert_after(first, first)
