"""Boolean ``@symbolic_function`` predicates verbalize as clauses.

A boolean symbolic function reads as a predicate clause — copular for an ``is_…`` name, verb-first
otherwise — instead of the generic *"a TypeName, where …"* decomposition. It composes with the rest
of the grammar (placed under *"such that …"*, negated inline). A value (non-bool) function is left to
the generic form.
"""

from krrood.entity_query_language.factories import variable, entity, an, not_
from krrood.entity_query_language.predicate import length, symbolic_function
from krrood.entity_query_language.verbalization.grammar.instantiated.planner import (
    InstantiatedPlanner,
)
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression


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
