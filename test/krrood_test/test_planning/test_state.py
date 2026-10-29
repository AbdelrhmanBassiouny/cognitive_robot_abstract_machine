"""
Tests that queries evaluated against a :class:`~krrood.planning.state.State` read the
values it assigns to fluents, and live values for every other attribute.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.predicate import symbolic_function
from krrood.planning.state import Fluent, State

from ..dataset.blocks_world import Block, Table

# %% fixtures


@dataclass
class TwoTowers:
    """
    A blocksworld with block ``c`` on block ``a``, and blocks ``a`` and ``b`` on the
    table.
    """

    table: Table
    """
    The table both towers stand on.
    """

    a: Block
    """
    The bottom block of the first tower.
    """

    b: Block
    """
    The only block of the second tower.
    """

    c: Block
    """
    The top block of the first tower.
    """

    @property
    def blocks(self) -> list[Block]:
        """
        :return: Every block of the world.
        """
        return [self.a, self.b, self.c]


@pytest.fixture
def two_towers() -> TwoTowers:
    """
    :return: A fresh :class:`TwoTowers` world for each test.
    """
    table = Table("table")
    a = Block("a", table)
    return TwoTowers(table=table, a=a, b=Block("b", table), c=Block("c", a))


def blocks_on(blocks: list[Block], support: Block | Table) -> list[Block]:
    """
    :param blocks: The blocks to query over.
    :param support: The block or table the selected blocks rest on.
    :return: The blocks resting on *support*, evaluated in the current context.
    """
    block = variable(Block, blocks)
    return an(entity(block).where(block.support == support)).tolist()


# %% reading assigned and unassigned fluents


def test_query_under_state_reads_assigned_value(two_towers):
    state = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})

    with state.as_current():
        result = blocks_on(two_towers.blocks, two_towers.c)

    assert result == [two_towers.b]


def test_unassigned_fluents_keep_their_live_values(two_towers):
    state = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})

    with state.as_current():
        result = blocks_on(two_towers.blocks, two_towers.table)

    assert result == [two_towers.a]


def test_state_never_changes_live_objects(two_towers):
    state = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})

    with state.as_current():
        blocks_on(two_towers.blocks, two_towers.c)

    assert two_towers.b.support is two_towers.table


def test_query_outside_state_reads_live_values(two_towers):
    State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})

    assert blocks_on(two_towers.blocks, two_towers.c) == []


def test_every_query_under_state_reads_it(two_towers):
    state = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})

    with state.as_current():
        on_c = blocks_on(two_towers.blocks, two_towers.c)
        on_table = blocks_on(two_towers.blocks, two_towers.table)

    assert (on_c, on_table) == ([two_towers.b], [two_towers.a])


def test_query_started_during_another_evaluation_reads_state(two_towers):
    """
    A query started from inside a running evaluation, here by a symbolic function, reads
    the same state as the evaluation that started it.
    """

    @symbolic_function
    def is_covered(candidate: Block) -> bool:
        return blocks_on(two_towers.blocks, candidate) != []

    state = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(is_covered(block))).tolist()

    assert result == [two_towers.a, two_towers.c]


# %% building states


def test_with_assignments_leaves_the_original_state_unchanged(two_towers):
    state = State()

    state.with_assignments({Fluent(two_towers.b, "support"): two_towers.c})

    assert state.assignments == {}


def test_later_assignment_replaces_an_earlier_one(two_towers):
    fluent = Fluent(two_towers.b, "support")

    state = (
        State()
        .with_assignments({fluent: two_towers.c})
        .with_assignments({fluent: two_towers.a})
    )

    assert state.assignments == {fluent: two_towers.a}


def test_fluents_identify_instances_by_identity(two_towers):
    """
    Two blocks that compare equal are still different objects, so assigning a fluent of
    one never assigns the other.
    """
    first = Block("d", two_towers.table)
    second = Block("d", two_towers.table)
    state = State().with_assignments({Fluent(first, "support"): two_towers.c})

    with state.as_current():
        result = blocks_on([first, second], two_towers.table)

    assert result == [second]


# %% comparing states


def test_states_with_the_same_assignments_are_equal_and_hash_alike(two_towers):
    first = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})
    second = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})

    assert (first, hash(first)) == (second, hash(second))


def test_states_with_different_assignments_differ(two_towers):
    first = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.c})
    second = State().with_assignments({Fluent(two_towers.b, "support"): two_towers.a})

    assert first != second
