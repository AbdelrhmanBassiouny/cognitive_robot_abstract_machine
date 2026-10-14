from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List, Optional

from cramph.composites import (
    Attempt,
    ChildChooser,
    ChildChooserAccess,
    CompositeNodeChoosingItsChild,
    RepeatUntil,
)
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.executor import StatechartExecutor, TickingExecutorExtension
from cramph.monitors import CountNodeResets, CountTicks
from cramph.node import EndStatechart, StatechartNode
from cramph.nodes_for_testing import (
    ConstFalseNode,
    NodeFailingOnObservingFalse,
    NodeSucceedingOnObservingTrue,
)
from cramph.statechart import Statechart

# %% mimics


@dataclass
class ChooserAnsweringInTurn(ChildChooser):
    """
    Has no choice for the first few questions, then gives the prepared children one
    after another, then says no child is left.
    """

    children: List[Optional[StatechartNode]]
    """
    The children still to give, in order, None for no child left.
    """

    unanswered_questions: int = 0
    """
    How many questions are still answered with having no choice yet.
    """

    asked_nodes: List[CompositeNodeChoosingItsChild] = field(default_factory=list)
    """
    Every node that asked, once per question.
    """

    def has_choice_for(self, node: CompositeNodeChoosingItsChild) -> bool:
        self.asked_nodes.append(node)
        if self.unanswered_questions == 0:
            return True
        self.unanswered_questions -= 1
        return False

    def choose_child(
        self, node: CompositeNodeChoosingItsChild, context
    ) -> Optional[StatechartNode]:
        if not self.children:
            return None
        return self.children.pop(0)


@dataclass
class ExtensionCountingCompiles(TickingExecutorExtension):
    """
    An executor extension that counts how often it was told the statechart compiled.
    """

    compile_count: int = 0
    """
    How often :meth:`after_compile` ran.
    """

    def after_compile(self, executor: StatechartExecutor) -> None:
        self.compile_count += 1


# %% helpers


def _succeeding_child(name: str) -> NodeSucceedingOnObservingTrue:
    """
    :return: A node that succeeds on the tick after it starts.
    """
    return NodeSucceedingOnObservingTrue(
        name=name, observation=ObservationStateValues.TRUE
    )


def _failing_child(name: str) -> NodeFailingOnObservingFalse:
    """
    :return: A node that fails on the tick after it starts.
    """
    return NodeFailingOnObservingFalse(
        name=name, observation=ObservationStateValues.FALSE
    )


def _undecided_child(name: str) -> NodeSucceedingOnObservingTrue:
    """
    :return: A node that never ends on its own.
    """
    return NodeSucceedingOnObservingTrue(
        name=name, observation=ObservationStateValues.UNKNOWN
    )


def _run_count(statechart: Statechart, node: StatechartNode) -> int:
    """
    :return: How often `node` went from not started to running.
    """
    life_cycles = statechart.history.get_life_cycle_history_of_node(node)
    return sum(
        previous == LifeCycleValues.NOT_STARTED and current == LifeCycleValues.RUNNING
        for previous, current in zip(life_cycles, life_cycles[1:])
    )


def _run_repeated_until_decided(
    executor: StatechartExecutor,
    chooser: ChildChooser,
    task: StatechartNode,
    resets_until_stopped: int,
) -> Statechart:
    """
    Run `task` again whenever it failed, until it succeeds or was reset
    `resets_until_stopped` times.

    :return: The statechart that ran.
    """
    executor.context.add_extension(ChildChooserAccess(chooser=chooser))
    statechart = Statechart(context=executor.context)
    loop = RepeatUntil(
        name="loop",
        task=task,
        stop_retry_monitor=CountNodeResets(
            name="counter", node=task, target=resets_until_stopped
        ),
    )
    statechart.add_node(loop)
    statechart.add_node(EndStatechart.when_true(loop))
    statechart.add_node(EndStatechart.when_failed(loop))
    executor.compile(statechart)
    executor.tick_until_end(timeout=60)
    return statechart


def _run_choosing_node(
    executor: StatechartExecutor,
    chooser: ChildChooser,
    end_node_factory=EndStatechart.when_true,
) -> CompositeNodeChoosingItsChild:
    """
    Run a statechart holding one choosing node until it ends the statechart.

    :return: The choosing node.
    """
    executor.context.add_extension(ChildChooserAccess(chooser=chooser))
    statechart = Statechart(context=executor.context)
    choosing_node = CompositeNodeChoosingItsChild(name="choosing")
    statechart.add_node(choosing_node)
    statechart.add_node(end_node_factory(choosing_node))
    executor.compile(statechart)
    executor.tick_until_end(timeout=30)
    return choosing_node


# %% choosing


def test_the_node_succeeds_with_the_child_it_chose(
    statechart_executor: StatechartExecutor,
):
    child = _succeeding_child("child")

    choosing_node = _run_choosing_node(
        statechart_executor, ChooserAnsweringInTurn([child])
    )

    assert choosing_node.children == [child]
    assert child.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert choosing_node.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_failed_child_makes_the_node_choose_again(
    statechart_executor: StatechartExecutor,
):
    failing = _failing_child("failing")
    succeeding = _succeeding_child("succeeding")

    choosing_node = _run_choosing_node(
        statechart_executor,
        ChooserAnsweringInTurn([failing, succeeding]),
    )

    assert choosing_node.children == [failing, succeeding]
    assert failing.life_cycle_state == LifeCycleValues.FAILED
    assert choosing_node.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_no_child_left_fails_the_node(statechart_executor: StatechartExecutor):
    choosing_node = _run_choosing_node(
        statechart_executor,
        ChooserAnsweringInTurn([]),
        end_node_factory=EndStatechart.when_failed,
    )

    assert choosing_node.children == []
    assert choosing_node.life_cycle_state == LifeCycleValues.FAILED


def test_a_pending_choice_is_asked_again_on_the_next_tick(
    statechart_executor: StatechartExecutor,
):
    child = _succeeding_child("child")
    chooser = ChooserAnsweringInTurn([child], unanswered_questions=2)

    choosing_node = _run_choosing_node(statechart_executor, chooser)

    assert chooser.asked_nodes == [choosing_node] * 3
    assert choosing_node.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_node_that_is_not_running_is_not_asked(
    statechart_executor: StatechartExecutor,
):
    chooser = ChooserAnsweringInTurn([_succeeding_child("child")])
    statechart_executor.context.add_extension(ChildChooserAccess(chooser=chooser))
    statechart = Statechart(context=statechart_executor.context)
    never_true = ConstFalseNode(name="never true")
    statechart.add_node(never_true)
    choosing_node = CompositeNodeChoosingItsChild(name="choosing")
    choosing_node.start_condition = never_true.observes_true
    statechart.add_node(choosing_node)

    statechart_executor.compile(statechart)
    statechart_executor.tick()

    assert chooser.asked_nodes == []
    assert choosing_node.life_cycle_state == LifeCycleValues.NOT_STARTED


def test_choosing_keeps_the_state_and_history_of_the_nodes_already_there(
    statechart_executor: StatechartExecutor,
):
    chooser = ChooserAnsweringInTurn([_succeeding_child("child")])
    statechart_executor.context.add_extension(ChildChooserAccess(chooser=chooser))
    statechart = Statechart(context=statechart_executor.context)
    earlier = _succeeding_child("earlier")
    statechart.add_node(earlier)
    choosing_node = CompositeNodeChoosingItsChild(name="choosing")
    choosing_node.start_condition = earlier.is_succeeded
    statechart.add_node(choosing_node)
    statechart.add_node(EndStatechart.when_true(choosing_node))
    statechart_executor.compile(statechart)
    statechart_executor.tick()
    assert earlier.life_cycle_state == LifeCycleValues.SUCCEEDED
    recorded_before_choosing = len(statechart.history)

    statechart_executor.tick_until_end(timeout=30)

    assert earlier.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert len(statechart.history) == recorded_before_choosing + (
        statechart_executor.tick_count - 1
    )


def test_a_choice_compiles_the_statechart_once(
    statechart_context,
):
    counting = ExtensionCountingCompiles()
    executor = StatechartExecutor(context=statechart_context, extensions=[counting])
    child = _succeeding_child("child")
    executor.context.add_extension(
        ChildChooserAccess(chooser=ChooserAnsweringInTurn([child]))
    )
    statechart = Statechart(context=executor.context)
    choosing_node = CompositeNodeChoosingItsChild(name="choosing")
    statechart.add_node(choosing_node)

    executor.compile(statechart)

    assert choosing_node.children == [child]
    assert counting.compile_count == 2


def test_the_node_observes_what_its_latest_child_observed(
    statechart_executor: StatechartExecutor,
):
    child: StatechartNode = _succeeding_child("child")

    choosing_node = _run_choosing_node(
        statechart_executor, ChooserAnsweringInTurn([child])
    )

    assert choosing_node.last_observation_state == ObservationStateValues.TRUE


@dataclass
class ExtensionHoldingStill(TickingExecutorExtension):
    """
    An executor extension that notes when it was told to hold still.
    """

    is_holding_still: bool = False
    """
    Whether :meth:`before_recompile` ran.
    """

    def before_recompile(self, executor: StatechartExecutor) -> bool:
        self.is_holding_still = True
        return True


@dataclass
class ChooserNotingWhetherTheExtensionHeldStill(ChildChooser):
    """
    Notes whether the extension held still by the time it was asked.
    """

    extension: ExtensionHoldingStill
    """
    The extension to look at.
    """

    child: StatechartNode
    """
    The child to choose.
    """

    held_still_when_asked: List[bool] = field(default_factory=list)
    """
    Whether the extension held still, once per question.
    """

    def choose_child(
        self, node: CompositeNodeChoosingItsChild, context
    ) -> Optional[StatechartNode]:
        self.held_still_when_asked.append(self.extension.is_holding_still)
        return self.child


def test_the_extensions_hold_still_before_a_node_chooses(statechart_context):
    """
    Choosing blocks the tick, so whatever an extension is driving is stopped first.
    """
    extension = ExtensionHoldingStill()
    executor = StatechartExecutor(context=statechart_context, extensions=[extension])
    chooser = ChooserNotingWhetherTheExtensionHeldStill(
        extension=extension, child=_succeeding_child("child")
    )
    executor.context.add_extension(ChildChooserAccess(chooser=chooser))
    statechart = Statechart(context=executor.context)
    statechart.add_node(CompositeNodeChoosingItsChild(name="choosing"))

    executor.compile(statechart)

    assert chooser.held_still_when_asked == [True]


# %% choosing again after a reset


def test_a_reset_node_chooses_again_instead_of_running_its_earlier_children(
    statechart_executor: StatechartExecutor,
):
    failing = _failing_child("failing")
    undecided = _undecided_child("undecided")
    succeeding = _succeeding_child("succeeding")
    chooser = ChooserAnsweringInTurn([failing, undecided, succeeding])
    choosing_node = CompositeNodeChoosingItsChild(name="choosing")
    attempt = Attempt(
        name="attempt",
        task=choosing_node,
        failure_monitors=[CountTicks(name="timeout", ticks=6)],
    )

    statechart = _run_repeated_until_decided(
        statechart_executor, chooser, attempt, resets_until_stopped=3
    )

    assert chooser.asked_nodes == [choosing_node] * 3
    assert choosing_node.children == [failing, undecided, succeeding]
    assert _run_count(statechart, failing) == 1
    assert _run_count(statechart, undecided) == 1
    assert choosing_node.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_a_node_that_ran_out_of_children_chooses_again_after_a_reset(
    statechart_executor: StatechartExecutor,
):
    succeeding = _succeeding_child("succeeding")
    chooser = ChooserAnsweringInTurn([None, succeeding])
    choosing_node = CompositeNodeChoosingItsChild(name="choosing")

    _run_repeated_until_decided(
        statechart_executor, chooser, choosing_node, resets_until_stopped=3
    )

    assert chooser.asked_nodes == [choosing_node] * 2
    assert choosing_node.children == [succeeding]
    assert not choosing_node.ran_out_of_children
    assert choosing_node.life_cycle_state == LifeCycleValues.SUCCEEDED
