"""``@symbolic_function`` verbalization: boolean predicates read as clauses, value functions as nouns.

A boolean symbolic function reads as a predicate clause — copular for an ``is_…`` name, verb-first
otherwise — instead of the generic *"a TypeName, where …"* decomposition. It composes with the rest
of the grammar (placed under *"such that …"*, negated inline). A value (non-bool) function is not a
truth value, so it reads as a noun naming the value it computes (``quarter(month)`` → *"a quarter"*),
and a grouped report names such a key by that noun (*"For each year and quarter, report …"*).
"""

import krrood.entity_query_language.factories as eql
from krrood.entity_query_language.factories import variable, entity, an, a, not_, set_of
from krrood.entity_query_language.predicate import length, symbolic_function
from krrood.entity_query_language.verbalization.grammar.instantiated.planner import (
    InstantiatedPlanner,
)
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression


@symbolic_function
def parity(number: int) -> int:
    return number % 2


@symbolic_function
def get_quarter(month: int) -> int:
    return (month - 1) // 3 + 1


@symbolic_function
def is_one_month(period: int) -> bool:
    return True


@symbolic_function
def is_even(number: int) -> bool:
    return number % 2 == 0


@symbolic_function
def divides(divisor: int, dividend: int) -> bool:
    return dividend % divisor == 0


def test_copular_function_reads_as_a_copular_clause():
    assert verbalize_expression(is_one_month(variable(int, []))) == "an int is one month"


def test_function_reads_as_a_predicate_in_where_with_coreference():
    number = variable(int, [])
    assert (
        verbalize_expression(an(entity(number).where(is_even(number))))
        == "Find an int such that it is even"
    )


def test_function_negates_inline():
    number = variable(int, [])
    assert (
        verbalize_expression(an(entity(number).where(not_(is_even(number)))))
        == "Find an int such that it is not even"
    )


def test_verb_first_function_has_a_subject_and_an_object():
    assert (
        verbalize_expression(divides(variable(int, []), variable(int, [])))
        == "int 1 divides int 2"
    )


def test_value_function_is_not_treated_as_a_predicate_clause():
    # length returns int, so it is a value, not a predicate -- the clause rule must not claim it.
    assert not InstantiatedPlanner.is_boolean_symbolic_function(length(variable(list, [])))


def test_value_function_reads_as_the_value_of_its_arguments():
    # A non-bool function names the value it computes AND what it is computed from: "the parity of an
    # int" -- a genitive over its argument -- not a bare floating "a parity", and not the verbose
    # "a parity, where the number of the parity is ..." decomposition.
    assert verbalize_expression(parity(variable(int, []))) == "the parity of an int"


def test_getter_named_value_function_drops_the_get_prefix():
    # A stray imperative getter still reads as the noun it computes over its argument: get_quarter ->
    # "the quarter of an int".
    assert verbalize_expression(get_quarter(variable(int, []))) == "the quarter of an int"


def test_value_function_over_an_attribute_chain_reads_its_path():
    # The argument's full navigation is read out, so the value is grounded in the entity it derives
    # from -- this is what lets a ranked/grouped report over the value reframe instead of bracketing.
    from krrood.entity_query_language.verbalization.example_domain import Employee

    employee = variable(Employee, [])
    assert (
        verbalize_expression(a(set_of(get_quarter(employee.salary))))
        == "Find the quarter of the salary of an Employee"
    )


def test_grouped_report_names_a_value_function_key_as_a_noun():
    # A symbolic-function GROUP BY key is still named compactly by the value it computes (a bare label
    # like an attribute key) -- "For each parity, report ...", never decomposed or the raw callable.
    numbers = variable(int, [])
    grouping = parity(numbers)
    text = verbalize_expression(a(set_of(grouping, eql.sum(numbers)).grouped_by(grouping)))
    assert text == "For each parity, report the sum of ints"


def test_ranked_grouped_report_by_a_value_key_reads_as_a_sentence_not_a_tuple():
    # The motivating case: grouping by a value function and taking the single row with the highest
    # aggregate must read as a plain sentence, never "the highest (a, b)".
    numbers = variable(int, [])
    grouping = parity(numbers)
    total = eql.sum(numbers)
    text = verbalize_expression(
        a(set_of(grouping, total).grouped_by(grouping).ordered_by(total, descending=True).limit(1))
    )
    assert text == "Find the parity of an int with the highest sum of ints"
    assert "(" not in text
