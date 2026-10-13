"""
Tests for holding still before a statechart blocks its tick: a node choosing its child
or a compile only happens once everything the executor drives is at rest, and the
statechart keeps ticking until then.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List, Optional

from cramph.composites import (
    ChildChooser,
    ChildChooserAccess,
    CompositeNodeChoosingItsChild,
)
from cramph.context import StatechartContext
from cramph.data_types import ObservationStateValues
from cramph.executor import (
    ExecutorExtension,
    StatechartExecutor,
    TickingExecutorExtension,
)
from cramph.node import StatechartNode
from cramph.nodes_for_testing import NodeSucceedingOnObservingTrue
from cramph.statechart import Statechart

# %% mimics


@dataclass
class ExtensionComingToRest(TickingExecutorExtension):
    """
    An executor extension that reports rest only after it was asked to hold still a few
    times, the way a decelerating robot does.
    """

    questions_until_at_rest: int
    """
    How many more times it answers that it is not at rest yet.
    """

    questions: int = 0
    """
    How often it was asked to hold still.
    """

    def before_recompile(self, executor: StatechartExecutor) -> bool:
        self.questions += 1
        if self.questions_until_at_rest == 0:
            return True
        self.questions_until_at_rest -= 1
        return False


@dataclass
class ChooserNotingTheTick(ChildChooser):
    """
    Chooses one prepared child, noting the tick it was asked on.
    """

    executor: StatechartExecutor
    """
    The executor whose ticks are counted.
    """

    child: StatechartNode
    """
    The child to choose.
    """

    asked_on_ticks: List[int] = field(default_factory=list)
    """
    The tick of every question.
    """

    def choose_child(
        self, node: CompositeNodeChoosingItsChild, context
    ) -> Optional[StatechartNode]:
        self.asked_on_ticks.append(self.executor.tick_count)
        return self.child


@dataclass
class ExtensionRecordingCompiles(TickingExecutorExtension):
    """
    An executor extension that records in which order it was told about compiling.
    """

    events: List[str] = field(default_factory=list)
    """
    The hooks that ran, in order, each by its method name.
    """

    def before_recompile(self, executor: StatechartExecutor) -> bool:
        self.events.append(self.before_recompile.__name__)
        return True

    def after_compile(self, executor: StatechartExecutor) -> None:
        self.events.append(self.after_compile.__name__)


def _choosing_statechart(
    statechart_context: StatechartContext, extension: ExecutorExtension
) -> tuple[StatechartExecutor, ChooserNotingTheTick, CompositeNodeChoosingItsChild]:
    """
    :return: An executor with `extension`, the chooser its context asks and the node
        choosing its child, compiled.
    """
    executor = StatechartExecutor(context=statechart_context, extensions=[extension])
    chooser = ChooserNotingTheTick(
        executor=executor,
        child=NodeSucceedingOnObservingTrue(
            name="child", observation=ObservationStateValues.TRUE
        ),
    )
    executor.context.add_extension(ChildChooserAccess(chooser=chooser))
    statechart = Statechart(context=executor.context)
    choosing = CompositeNodeChoosingItsChild(name="choosing")
    statechart.add_node(choosing)
    executor.compile(statechart)
    return executor, chooser, choosing


# %% choosing only at rest


def test_a_node_chooses_its_child_only_once_the_extensions_are_at_rest(
    statechart_context,
):
    extension = ExtensionComingToRest(questions_until_at_rest=3)
    executor, chooser, _ = _choosing_statechart(statechart_context, extension)

    for _ in range(5):
        executor.tick()

    assert chooser.asked_on_ticks == [3]


def test_the_statechart_keeps_ticking_while_the_extensions_come_to_rest(
    statechart_context,
):
    extension = ExtensionComingToRest(questions_until_at_rest=3)
    executor, chooser, choosing = _choosing_statechart(statechart_context, extension)

    executor.tick()
    executor.tick()

    assert executor.tick_count == 2
    assert choosing.children == []
    assert extension.questions == 3


def test_the_extensions_are_asked_to_hold_still_once_per_choice(statechart_context):
    """
    Choosing the child compiles the statechart again, which must not ask a second time.
    """
    extension = ExtensionRecordingCompiles()

    _choosing_statechart(statechart_context, extension)

    assert extension.events == [
        ExtensionRecordingCompiles.after_compile.__name__,
        ExtensionRecordingCompiles.before_recompile.__name__,
        ExtensionRecordingCompiles.after_compile.__name__,
    ]
