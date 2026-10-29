"""
Tests that queries evaluated against a :class:`~krrood.planning.state.State` read the.

values it assigns to fluents - attributes, indexed elements, calls, symbolic functions
and predicates - and live values for every other fluent.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import (
    an,
    entity,
    flat_variable,
    variable,
)
from krrood.entity_query_language.ground_term import GroundTerm
from krrood.entity_query_language.predicate import symbolic_function
from krrood.planning.state import State

from ..dataset.blocks_world import (
    Block,
    IsOn,
    Shelf,
    SupportName,
    Table,
    is_table,
    tower_height,
)

# %% fixtures


@dataclass
class TwoTowers:
    """
    A blocksworld with block ``c`` on block ``a``, blocks ``a`` and ``b`` on the table,
    and a shelf holding ``a`` and ``b`` in its slots.
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

    shelf: Shelf
    """
    The shelf whose slots hold ``a`` and ``b``.
    """

    @property
    def blocks(self) -> list[Block]:
        """
        :return: Every block of the world.
        """
        return [self.a, self.b, self.c]

    @property
    def b_on_c(self) -> GroundTerm:
        """
        :return: The fluent that puts ``b`` onto ``c`` when assigned ``c``.
        """
        return GroundTerm.attribute(self.b, "support")


@pytest.fixture
def two_towers() -> TwoTowers:
    """
    :return: A fresh :class:`TwoTowers` world for each test.
    """
    table = Table("table")
    a = Block("a", table)
    b = Block("b", table)
    return TwoTowers(
        table=table, a=a, b=b, c=Block("c", a), shelf=Shelf("shelf", [a, b])
    )


def blocks_on(blocks: list[Block], support: Block | Table) -> list[Block]:
    """
    :param blocks: The blocks to query over.
    :param support: The block or table the selected blocks rest on.
    :return: The blocks resting on *support*, evaluated in the current context.
    """
    block = variable(Block, blocks)
    return an(entity(block).where(block.support == support)).tolist()


# %% reading assigned and unassigned attributes


def test_query_under_state_reads_assigned_value(two_towers):
    state = State().with_assignments({two_towers.b_on_c: two_towers.c})

    with state.as_current():
        result = blocks_on(two_towers.blocks, two_towers.c)

    assert result == [two_towers.b]


def test_unassigned_fluents_keep_their_live_values(two_towers):
    state = State().with_assignments({two_towers.b_on_c: two_towers.c})

    with state.as_current():
        result = blocks_on(two_towers.blocks, two_towers.table)

    assert result == [two_towers.a]


def test_state_never_changes_live_objects(two_towers):
    state = State().with_assignments({two_towers.b_on_c: two_towers.c})

    with state.as_current():
        blocks_on(two_towers.blocks, two_towers.c)

    assert two_towers.b.support is two_towers.table


def test_query_outside_state_reads_live_values(two_towers):
    State().with_assignments({two_towers.b_on_c: two_towers.c})

    assert blocks_on(two_towers.blocks, two_towers.c) == []


def test_assigning_an_attribute_the_instance_lacks_gives_it_a_value(two_towers):
    state = State().with_assignments(
        {GroundTerm.attribute(two_towers.table, "support"): two_towers.a}
    )
    table = variable(Table, [two_towers.table])
    query = an(entity(table).where(table.support == two_towers.a))

    with state.as_current():
        result = query.tolist()

    assert result == [two_towers.table]


# %% fluents of every kind


def test_query_reads_assigned_indexed_element(two_towers):
    state = State().with_assignments(
        {GroundTerm.index(two_towers.shelf.slots, 0): two_towers.c}
    )
    shelf = variable(Shelf, [two_towers.shelf])

    with state.as_current():
        result = an(entity(shelf.slots[0])).tolist()

    assert result == [two_towers.c]


def test_index_by_expression_reads_the_same_fluent_as_index_by_value(two_towers):
    state = State().with_assignments(
        {GroundTerm.index(two_towers.shelf.slots, 0): two_towers.c}
    )
    shelf = variable(Shelf, [two_towers.shelf])
    slot = variable(int, [0, 1])

    with state.as_current():
        result = an(entity(shelf.slots[slot])).tolist()

    assert result == [two_towers.c, two_towers.b]


def test_query_reads_assigned_method_call(two_towers):
    state = State().with_assignments(
        {GroundTerm.call(two_towers.a.rests_on, two_towers.table): False}
    )
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(block.rests_on(two_towers.table))).tolist()

    assert result == [two_towers.b]


def test_query_reads_assigned_symbolic_function(two_towers):
    state = State().with_assignments({GroundTerm.call(tower_height, two_towers.b): 3})
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(tower_height(block) == 3)).tolist()

    assert result == [two_towers.b]


def test_query_reads_assigned_predicate(two_towers):
    state = State().with_assignments(
        {GroundTerm.call(IsOn, two_towers.a, two_towers.table): False}
    )
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(IsOn(block, two_towers.table))).tolist()

    assert result == [two_towers.b]


def test_query_reads_assigned_symbolic_function_class(two_towers):
    state = State().with_assignments({GroundTerm.call(SupportName, two_towers.b): "a"})
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(SupportName(block) == "a")).tolist()

    assert result == [two_towers.b, two_towers.c]


# %% one fluent, written in several ways


def test_call_names_one_fluent_however_its_arguments_are_passed(two_towers):
    positional = GroundTerm.call(two_towers.a.rests_on, two_towers.table)
    by_name = GroundTerm.call(two_towers.a.rests_on, support=two_towers.table)
    with_default = GroundTerm.call(
        two_towers.a.rests_on, two_towers.table, directly=True
    )

    assert positional == by_name == with_default


def test_bound_method_names_the_same_fluent_as_its_function_with_the_receiver(
    two_towers,
):
    assert GroundTerm.call(two_towers.a.rests_on, two_towers.table) == GroundTerm.call(
        Block.rests_on, two_towers.a, two_towers.table
    )


def test_decorated_symbolic_function_names_the_same_fluent_as_the_function(
    two_towers,
):
    assert GroundTerm.call(tower_height, two_towers.b) == GroundTerm.call(
        tower_height.__wrapped__, two_towers.b
    )


def test_assignment_by_keyword_is_read_by_a_positional_call(two_towers):
    state = State().with_assignments(
        {GroundTerm.call(two_towers.a.rests_on, support=two_towers.table): False}
    )
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(block.rests_on(two_towers.table))).tolist()

    assert result == [two_towers.b]


def test_different_arguments_name_different_fluents(two_towers):
    assert GroundTerm.call(two_towers.a.rests_on, two_towers.table) != GroundTerm.call(
        two_towers.a.rests_on, two_towers.table, directly=False
    )


# %% how arguments are compared


def test_fluents_identify_unhashable_instances_by_identity(two_towers):
    """
    Two blocks that compare equal are still different objects, so assigning a fluent of
    one never assigns the other.
    """
    first = Block("d", two_towers.table)
    second = Block("d", two_towers.table)
    state = State().with_assignments(
        {GroundTerm.attribute(first, "support"): two_towers.c}
    )

    with state.as_current():
        result = blocks_on([first, second], two_towers.table)

    assert result == [second]


def test_fluents_compare_hashable_arguments_by_value(two_towers):
    key = 1000
    equal_key = int("1000")

    assert GroundTerm.index(two_towers.shelf.slots, key) == GroundTerm.index(
        two_towers.shelf.slots, equal_key
    )


# %% fluents read through other fluents


def test_attribute_of_an_assigned_attribute_reads_the_new_value(two_towers):
    state = State().with_assignments({two_towers.b_on_c: two_towers.c})
    block = variable(Block, [two_towers.b])

    with state.as_current():
        result = an(entity(block.support.support)).tolist()

    assert result == [two_towers.a]


def test_symbolic_function_receives_assigned_attribute_as_argument(two_towers):
    state = State().with_assignments({two_towers.b_on_c: two_towers.c})
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(is_table(block.support))).tolist()

    assert result == [two_towers.a]


def test_flattening_an_assigned_collection_ranges_over_its_new_elements(two_towers):
    state = State().with_assignments(
        {GroundTerm.attribute(two_towers.shelf, "slots"): [two_towers.c]}
    )
    shelf = variable(Shelf, [two_towers.shelf])

    with state.as_current():
        result = an(entity(flat_variable(shelf.slots))).tolist()

    assert result == [two_towers.c]


def test_index_into_an_assigned_collection_reads_its_new_elements(two_towers):
    state = State().with_assignments(
        {GroundTerm.attribute(two_towers.shelf, "slots"): [two_towers.c]}
    )
    shelf = variable(Shelf, [two_towers.shelf])

    with state.as_current():
        result = an(entity(shelf.slots[0])).tolist()

    assert result == [two_towers.c]


# %% assigned derived fluents


def test_assigned_predicate_overrides_what_it_derives(two_towers):
    """
    An assigned fluent is not recomputed, even where it is derived from other fluents:

    ``c`` rests on ``a``, yet the state says it rests on the table.
    """
    state = State().with_assignments(
        {GroundTerm.call(IsOn, two_towers.c, two_towers.table): True}
    )
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(IsOn(block, two_towers.table))).tolist()

    assert result == two_towers.blocks


def test_assigned_call_is_never_computed(two_towers):
    computed_for = []

    @symbolic_function
    def height_counting_calls(block: Block) -> int:
        computed_for.append(block)
        return tower_height(block)

    state = State().with_assignments(
        {GroundTerm.call(height_counting_calls, two_towers.b): 5}
    )
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        an(entity(block).where(height_counting_calls(block) > 0)).tolist()

    assert two_towers.b not in computed_for


# %% evaluations under a state


def test_every_query_under_state_reads_it(two_towers):
    state = State().with_assignments({two_towers.b_on_c: two_towers.c})

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

    state = State().with_assignments({two_towers.b_on_c: two_towers.c})
    block = variable(Block, two_towers.blocks)

    with state.as_current():
        result = an(entity(block).where(is_covered(block))).tolist()

    assert result == [two_towers.a, two_towers.c]


# %% building states


def test_with_assignments_leaves_the_original_state_unchanged(two_towers):
    state = State()

    state.with_assignments({two_towers.b_on_c: two_towers.c})

    assert state.assignments == {}


def test_later_assignment_replaces_an_earlier_one(two_towers):
    state = (
        State()
        .with_assignments({two_towers.b_on_c: two_towers.c})
        .with_assignments({two_towers.b_on_c: two_towers.a})
    )

    assert state.assignments == {two_towers.b_on_c: two_towers.a}


def test_later_assignment_replaces_one_written_another_way(two_towers):
    state = (
        State()
        .with_assignments(
            {GroundTerm.call(two_towers.a.rests_on, two_towers.table): False}
        )
        .with_assignments(
            {
                GroundTerm.call(
                    Block.rests_on, two_towers.a, support=two_towers.table
                ): True
            }
        )
    )

    assert list(state.assignments.values()) == [True]


# %% comparing states


def test_states_with_the_same_assignments_are_equal_and_hash_alike(two_towers):
    first = State().with_assignments({two_towers.b_on_c: two_towers.c})
    second = State().with_assignments(
        {GroundTerm.attribute(two_towers.b, "support"): two_towers.c}
    )

    assert (first, hash(first)) == (second, hash(second))


def test_states_assigning_one_fluent_written_differently_are_equal(two_towers):
    first = State().with_assignments(
        {GroundTerm.call(two_towers.a.rests_on, two_towers.table): False}
    )
    second = State().with_assignments(
        {GroundTerm.call(Block.rests_on, two_towers.a, two_towers.table, True): False}
    )

    assert (first, hash(first)) == (second, hash(second))


def test_states_with_different_assignments_differ(two_towers):
    first = State().with_assignments({two_towers.b_on_c: two_towers.c})
    second = State().with_assignments({two_towers.b_on_c: two_towers.a})

    assert first != second
