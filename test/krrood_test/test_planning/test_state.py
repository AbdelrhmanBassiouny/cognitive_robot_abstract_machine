"""
Tests that queries evaluated against a :class:`~krrood.planning.state.State` read the.

values its facts give fluents - attributes, indexed elements, calls, symbolic functions
and predicates - and live values for every other fluent.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import (
    a,
    flat_variable,
    literal,
    not_,
    variable,
)
from krrood.entity_query_language.predicate import symbolic_function
from krrood.planning.exceptions import (
    ConditionIsNotAFact,
    FactValueIsNotConstant,
    MissingFluent,
)
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
    def b_on_c(self) -> State:
        """
        :return: The state that puts ``b`` onto ``c``.
        """
        return State().with_facts(literal(self.b).support == self.c)


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
    return a(Block)(support=support).from_(blocks).tolist()


# %% reading assigned and unassigned attributes


def test_query_under_state_reads_assigned_value(two_towers):
    with two_towers.b_on_c.as_current():
        result = blocks_on(two_towers.blocks, two_towers.c)

    assert result == [two_towers.b]


def test_unassigned_fluents_keep_their_live_values(two_towers):
    with two_towers.b_on_c.as_current():
        result = blocks_on(two_towers.blocks, two_towers.table)

    assert result == [two_towers.a]


def test_state_never_changes_live_objects(two_towers):
    with two_towers.b_on_c.as_current():
        blocks_on(two_towers.blocks, two_towers.c)

    assert two_towers.b.support is two_towers.table


def test_query_outside_state_reads_live_values(two_towers):
    two_towers.b_on_c

    assert blocks_on(two_towers.blocks, two_towers.c) == []


# %% fluents of every kind


def test_query_reads_assigned_indexed_element(two_towers):
    state = State().with_facts(literal(two_towers.shelf).slots[0] == two_towers.c)

    with state.as_current():
        result = a(a(Shelf).from_([two_towers.shelf]).slots[0]).tolist()

    assert result == [two_towers.c]


def test_index_by_expression_reads_the_same_fluent_as_index_by_value(two_towers):
    state = State().with_facts(literal(two_towers.shelf).slots[0] == two_towers.c)
    slot = variable(int, [0, 1])

    with state.as_current():
        result = a(a(Shelf).from_([two_towers.shelf]).slots[slot]).tolist()

    assert result == [two_towers.c, two_towers.b]


def test_query_reads_assigned_method_call(two_towers):
    state = State().with_facts(
        literal(two_towers.a).rests_on(two_towers.table) == False
    )
    block = a(Block).from_(two_towers.blocks)

    with state.as_current():
        result = block.where(block.rests_on(two_towers.table)).tolist()

    assert result == [two_towers.b]


def test_query_reads_assigned_symbolic_function(two_towers):
    state = State().with_facts(tower_height(literal(two_towers.b)) == 3)
    block = a(Block).from_(two_towers.blocks)

    with state.as_current():
        result = block.where(tower_height(block) == 3).tolist()

    assert result == [two_towers.b]


def test_query_reads_assigned_predicate(two_towers):
    state = State().with_facts(
        not_(IsOn(literal(two_towers.a), literal(two_towers.table)))
    )
    block = a(Block).from_(two_towers.blocks)

    with state.as_current():
        result = block.where(IsOn(block, two_towers.table)).tolist()

    assert result == [two_towers.b]


def test_query_reads_assigned_symbolic_function_class(two_towers):
    state = State().with_facts(SupportName(literal(two_towers.b)) == "a")
    block = a(Block).from_(two_towers.blocks)

    with state.as_current():
        result = block.where(SupportName(block) == "a").tolist()

    assert result == [two_towers.b, two_towers.c]


# %% facts about every binding of a variable


def test_fact_about_a_variable_assigns_the_fluent_of_each_of_its_values(two_towers):
    state = State().with_facts(
        variable(Block, [two_towers.a, two_towers.b]).support == two_towers.c
    )

    with state.as_current():
        result = blocks_on(two_towers.blocks, two_towers.c)

    assert result == [two_towers.a, two_towers.b]


def test_fact_about_a_match_assigns_only_the_fluents_of_its_matches(two_towers):
    state = State().with_facts(
        a(Block)(support=two_towers.table).from_(two_towers.blocks).support
        == two_towers.c
    )

    with state.as_current():
        result = blocks_on(two_towers.blocks, two_towers.c)

    assert result == [two_towers.a, two_towers.b]


def test_fact_with_an_expression_index_assigns_every_element_it_reaches(two_towers):
    state = State().with_facts(
        literal(two_towers.shelf).slots[variable(int, [0, 1])] == two_towers.c
    )

    slot = variable(int, [0, 1])

    with state.as_current():
        result = a(a(Shelf).from_([two_towers.shelf]).slots[slot]).tolist()

    assert result == [two_towers.c, two_towers.c]


# %% conditions that are not facts


def test_assigning_an_attribute_the_instance_lacks_is_rejected(two_towers):
    with pytest.raises(MissingFluent):
        State().with_facts(literal(two_towers.table).support == two_towers.a)


def test_assigning_an_element_the_container_lacks_is_rejected(two_towers):
    with pytest.raises(MissingFluent):
        State().with_facts(literal(two_towers.shelf).slots[5] == two_towers.c)


def test_a_comparison_other_than_equality_is_not_a_fact(two_towers):
    with pytest.raises(ConditionIsNotAFact):
        State().with_facts(tower_height(literal(two_towers.b)) > 3)


def test_a_fact_cannot_take_its_value_from_an_expression(two_towers):
    with pytest.raises(FactValueIsNotConstant):
        State().with_facts(
            literal(two_towers.b).support == literal(two_towers.a).support
        )


# %% one fluent, written in several ways


def test_call_names_one_fluent_however_its_arguments_are_passed(two_towers):
    block = literal(two_towers.a)
    positional = State().with_facts(block.rests_on(two_towers.table) == False)
    by_name = State().with_facts(block.rests_on(support=two_towers.table) == False)
    with_default = State().with_facts(
        block.rests_on(two_towers.table, directly=True) == False
    )

    assert positional == by_name == with_default


def test_different_arguments_name_different_fluents(two_towers):
    block = literal(two_towers.a)

    assert State().with_facts(
        block.rests_on(two_towers.table) == False
    ) != State().with_facts(block.rests_on(two_towers.table, directly=False) == False)


def test_assignment_by_keyword_is_read_by_a_positional_call(two_towers):
    state = State().with_facts(
        literal(two_towers.a).rests_on(support=two_towers.table) == False
    )
    block = a(Block).from_(two_towers.blocks)

    with state.as_current():
        result = block.where(block.rests_on(two_towers.table)).tolist()

    assert result == [two_towers.b]


# %% how arguments are compared


def test_fluents_identify_unhashable_instances_by_identity(two_towers):
    """
    Two blocks that compare equal are still different objects, so assigning a fluent of
    one never assigns the other.
    """
    first = Block("d", two_towers.table)
    second = Block("d", two_towers.table)
    state = State().with_facts(literal(first).support == two_towers.c)

    with state.as_current():
        result = blocks_on([first, second], two_towers.table)

    assert result == [second]


def test_fluents_compare_hashable_arguments_by_value(two_towers):
    key = 1
    equal_key = int("1")
    slots = literal(two_towers.shelf).slots

    assert State().with_facts(slots[key] == two_towers.c) == State().with_facts(
        slots[equal_key] == two_towers.c
    )


# %% fluents read through other fluents


def test_attribute_of_an_assigned_attribute_reads_the_new_value(two_towers):
    with two_towers.b_on_c.as_current():
        result = a(a(Block).from_([two_towers.b]).support.support).tolist()

    assert result == [two_towers.a]


def test_symbolic_function_receives_assigned_attribute_as_argument(two_towers):
    block = a(Block).from_(two_towers.blocks)

    with two_towers.b_on_c.as_current():
        result = block.where(is_table(block.support)).tolist()

    assert result == [two_towers.a]


def test_python_body_reads_live_values_it_does_not_receive_as_arguments(two_towers):
    """
    :class:`IsOn` reads ``self.block.support`` in Python, so it sees ``b`` on the table
    although the state puts ``b`` on ``c``.
    """
    block = a(Block).from_(two_towers.blocks)

    with two_towers.b_on_c.as_current():
        result = block.where(IsOn(block, two_towers.c)).tolist()

    assert result == []


def test_flattening_an_assigned_collection_ranges_over_its_new_elements(two_towers):
    state = State().with_facts(literal(two_towers.shelf).slots == [two_towers.c])

    with state.as_current():
        result = a(flat_variable(a(Shelf).from_([two_towers.shelf]).slots)).tolist()

    assert result == [two_towers.c]


def test_index_into_an_assigned_collection_reads_its_new_elements(two_towers):
    state = State().with_facts(literal(two_towers.shelf).slots == [two_towers.c])

    with state.as_current():
        result = a(a(Shelf).from_([two_towers.shelf]).slots[0]).tolist()

    assert result == [two_towers.c]


# %% assigned derived fluents


def test_assigned_predicate_overrides_what_it_derives(two_towers):
    """
    An assigned fluent is not recomputed, even where it is derived from other fluents:

    ``c`` rests on ``a``, yet the state says it rests on the table.
    """
    state = State().with_facts(IsOn(literal(two_towers.c), literal(two_towers.table)))
    block = a(Block).from_(two_towers.blocks)

    with state.as_current():
        result = block.where(IsOn(block, two_towers.table)).tolist()

    assert result == two_towers.blocks


def test_assigned_call_is_never_computed(two_towers):
    computed_for = []

    @symbolic_function
    def height_counting_calls(block: Block) -> int:
        computed_for.append(block)
        return tower_height(block)

    state = State().with_facts(height_counting_calls(literal(two_towers.b)) == 5)
    block = a(Block).from_(two_towers.blocks)

    with state.as_current():
        block.where(height_counting_calls(block) > 0).tolist()

    assert two_towers.b not in computed_for


# %% evaluations under a state


def test_every_query_under_state_reads_it(two_towers):
    with two_towers.b_on_c.as_current():
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

    block = a(Block).from_(two_towers.blocks)

    with two_towers.b_on_c.as_current():
        result = block.where(is_covered(block)).tolist()

    assert result == [two_towers.a, two_towers.c]


# %% building states


def test_with_facts_leaves_the_original_state_unchanged(two_towers):
    state = State()

    state.with_facts(literal(two_towers.b).support == two_towers.c)

    assert state.assignments == {}


def test_later_fact_replaces_an_earlier_one(two_towers):
    state = two_towers.b_on_c.with_facts(literal(two_towers.b).support == two_towers.a)

    assert state == State().with_facts(literal(two_towers.b).support == two_towers.a)


def test_later_fact_replaces_one_written_another_way(two_towers):
    block = literal(two_towers.a)
    state = (
        State()
        .with_facts(block.rests_on(two_towers.table) == False)
        .with_facts(block.rests_on(support=two_towers.table, directly=True) == True)
    )

    assert list(state.assignments.values()) == [True]


# %% comparing states


def test_states_with_the_same_facts_are_equal_and_hash_alike(two_towers):
    first = two_towers.b_on_c
    second = State().with_facts(literal(two_towers.b).support == two_towers.c)

    assert (first, hash(first)) == (second, hash(second))


def test_states_with_different_facts_differ(two_towers):
    assert two_towers.b_on_c != State().with_facts(
        literal(two_towers.b).support == two_towers.a
    )
