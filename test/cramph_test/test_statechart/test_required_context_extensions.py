from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cramph.node import SucceedsOnObservingTrue
from cramph.context import ContextExtension, StatechartContext
from cramph.data_types import ObservationStateValues
from cramph.exceptions import NodesMissingContextExtensionsError
from cramph.executor import StatechartExecutor
from cramph.node import CompositeNode
from cramph.nodes_for_testing import NodeSucceedingOnObservingTrue
from cramph.statechart import Statechart
from krrood.ormatic.utils import classproperty

# %% mimics


@dataclass
class ExtensionANodeRequires(ContextExtension):
    """
    A context extension a node declares it requires.
    """


@dataclass
class ExtensionASpecializedNodeRequires(ContextExtension):
    """
    A context extension only a specialized node declares it requires.
    """


@dataclass(eq=False, repr=False, kw_only=True)
class NodeRequiringAnExtension(NodeSucceedingOnObservingTrue):
    """
    A node that declares a context extension it requires.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (ExtensionANodeRequires,)


@dataclass(eq=False, repr=False, kw_only=True)
class SpecializedNodeRequiringAnotherExtension(NodeRequiringAnExtension):
    """
    A node that requires an extension on top of the one its base class requires.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (
            ExtensionASpecializedNodeRequires,
        )


@dataclass(eq=False, repr=False, kw_only=True)
class CompositeRequiringAnExtension(SucceedsOnObservingTrue, CompositeNode):
    """
    A composite node that declares a context extension it requires and remembers whether
    it expanded.
    """

    expanded: bool = field(default=False, init=False)
    """
    Whether :meth:`expand` ran.
    """

    @classproperty
    def required_context_extensions(cls) -> tuple[type[ContextExtension], ...]:
        return super().required_context_extensions + (ExtensionANodeRequires,)

    def expand(self, context: StatechartContext) -> None:
        self.expanded = True


@dataclass
class ExtensionACompositeReadsWhileExpanding(ContextExtension):
    """
    A context extension a composite node reads only to create its children.
    """


@dataclass(eq=False, repr=False, kw_only=True)
class CompositeReadingAnExtensionWhileExpanding(SucceedsOnObservingTrue, CompositeNode):
    """
    A composite node that declares a context extension it reads only while it expands,
    remembers whether it expanded, and then runs one child.
    """

    expanded: bool = field(default=False, init=False)
    """
    Whether :meth:`expand` ran.
    """

    @classproperty
    def context_extensions_required_to_expand(
        cls,
    ) -> tuple[type[ContextExtension], ...]:
        return super().context_extensions_required_to_expand + (
            ExtensionACompositeReadsWhileExpanding,
        )

    def expand(self, context: StatechartContext) -> None:
        self.expanded = True
        self._add_child_to_statechart(
            NodeSucceedingOnObservingTrue(
                name="child", observation=ObservationStateValues.TRUE
            )
        )


# %% declaring


def test_a_node_requires_no_extension_unless_it_declares_one():
    assert NodeSucceedingOnObservingTrue.required_context_extensions == ()


def test_a_node_requires_what_its_base_class_requires():
    assert SpecializedNodeRequiringAnotherExtension.required_context_extensions == (
        ExtensionANodeRequires,
        ExtensionASpecializedNodeRequires,
    )


def test_a_composite_node_requires_no_extension_to_expand_unless_it_declares_one():
    assert CompositeRequiringAnExtension.context_extensions_required_to_expand == ()


# %% checking at compile


def test_compiling_raises_for_a_node_missing_a_required_extension(
    statechart_context: StatechartContext,
):
    statechart = Statechart(context=statechart_context)
    statechart.add_node(
        node := NodeRequiringAnExtension(
            name="requiring", observation=ObservationStateValues.TRUE
        )
    )

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.compile()

    assert raised.value.nodes_by_missing_extension == {ExtensionANodeRequires: [node]}


def test_compiling_reports_every_missing_extension_at_once(
    statechart_context: StatechartContext,
):
    statechart = Statechart(context=statechart_context)
    statechart.add_node(
        first := NodeRequiringAnExtension(
            name="first", observation=ObservationStateValues.TRUE
        )
    )
    statechart.add_node(
        second := SpecializedNodeRequiringAnotherExtension(
            name="second", observation=ObservationStateValues.TRUE
        )
    )

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.compile()

    assert raised.value.nodes_by_missing_extension == {
        ExtensionANodeRequires: [first, second],
        ExtensionASpecializedNodeRequires: [second],
    }


def test_compiling_succeeds_once_the_required_extension_is_registered(
    statechart_context: StatechartContext,
):
    statechart_context.add_extension(ExtensionANodeRequires())
    statechart = Statechart(context=statechart_context)
    statechart.add_node(
        NodeRequiringAnExtension(
            name="requiring", observation=ObservationStateValues.TRUE
        )
    )

    statechart.compile()

    assert statechart.is_compiled


def test_a_node_joining_a_compiled_statechart_is_checked(
    statechart_executor: StatechartExecutor,
):
    statechart = Statechart(context=statechart_executor.context)
    statechart.add_node(
        NodeSucceedingOnObservingTrue(
            name="first", observation=ObservationStateValues.TRUE
        )
    )
    statechart_executor.compile(statechart)

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.add_node(
            node := NodeRequiringAnExtension(
                name="joining", observation=ObservationStateValues.TRUE
            )
        )

    assert list(raised.value.nodes_by_missing_extension) == [ExtensionANodeRequires]


# %% checking before a composite node expands


def test_a_composite_node_is_checked_before_it_expands(
    statechart_context: StatechartContext,
):
    statechart = Statechart(context=statechart_context)
    composite = CompositeRequiringAnExtension(name="composite")

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.add_node(composite)

    assert raised.value.nodes_by_missing_extension == {
        ExtensionANodeRequires: [composite]
    }
    assert not composite.expanded


def test_a_composite_node_is_checked_for_what_it_reads_while_expanding(
    statechart_context: StatechartContext,
):
    statechart = Statechart(context=statechart_context)
    composite = CompositeReadingAnExtensionWhileExpanding(name="composite")

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.add_node(composite)

    assert raised.value.nodes_by_missing_extension == {
        ExtensionACompositeReadsWhileExpanding: [composite]
    }
    assert not composite.expanded


def test_a_composite_node_expanded_elsewhere_compiles_without_what_it_read_to_expand(
    statechart_context: StatechartContext,
):
    context_it_expands_in = StatechartContext(world=statechart_context.world)
    context_it_expands_in.add_extension(ExtensionACompositeReadsWhileExpanding())
    expanded_elsewhere = Statechart(context=context_it_expands_in)
    expanded_elsewhere.add_node(
        CompositeReadingAnExtensionWhileExpanding(name="composite")
    )

    received = Statechart.from_json(
        expanded_elsewhere.to_json(), context=statechart_context
    )
    received.compile()

    assert received.is_compiled
