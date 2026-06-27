"""Symbolic-operation verbalization: a boolean :class:`Predicate` reads as a clause, a value
:class:`SymbolicFunction` as a noun.

A :class:`Predicate` reads as a predicate clause — copular for an ``Is…`` name, verb-first otherwise
— instead of the generic *"a TypeName, where …"* decomposition. It composes with the rest of the
grammar (placed under *"such that …"*, negated inline). A :class:`SymbolicFunction` is not a truth
value, so it reads as a noun naming the value it computes (``Quarter`` → *"the quarter of …"*), and a
grouped report names such a key by that noun (*"For each year and quarter, report …"*).
"""

from dataclasses import dataclass

import krrood.entity_query_language.factories as eql
from krrood.entity_query_language.factories import variable, entity, an, a, not_, set_of
from krrood.entity_query_language.predicate import (
    length,
    Length,
    Predicate,
    SymbolicCallable,
    SymbolicFunction,
    functional_form,
)
from krrood.entity_query_language.verbalization.fragments.base import WordFragment
from krrood.entity_query_language.verbalization.grammar.instantiated.planner import (
    InstantiatedPlanner,
)
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import Noun


@dataclass(eq=False)
class _RemainingLoad(SymbolicFunction):
    """A value SymbolicFunction with a custom noun surface, used to test the class form."""

    capacity: int
    """The capacity it is computed from."""

    load: int
    """The load it is computed from."""

    def __call__(self) -> int:
        return self.capacity - self.load

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return Noun(WordFragment(text="the remaining load")).as_fragment()


def test_symbolic_function_and_predicate_share_a_base():
    # Both are self-verbalizing symbolic callables, so the construction machinery lives in one base.
    assert issubclass(Predicate, SymbolicCallable)
    assert issubclass(SymbolicFunction, SymbolicCallable)


def test_symbolic_function_subclass_uses_its_custom_fragment():
    # A SymbolicFunction subclass names its value through its own _verbalization_fragment_ (a noun
    # phrase) -- like a Predicate names its clause -- rather than the decorator's default surface.
    numbers = variable(int, [])
    assert (
        verbalize_expression(a(set_of(_RemainingLoad(numbers, numbers))))
        == "Find the remaining load"
    )


def test_symbolic_function_subclass_evaluates_via_call():
    assert _RemainingLoad._construct_normally_(capacity=10, load=3)() == 7


@dataclass(eq=False)
class _Doubled(SymbolicFunction):
    """A single-argument value SymbolicFunction, used to test query evaluation."""

    number: int
    """The number it doubles."""

    def __call__(self) -> int:
        return self.number * 2

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return Noun(WordFragment(text="the doubled number")).as_fragment()


def test_migrated_length_keeps_its_surface_and_value():
    # `length` is a SymbolicFunction class behind a functional_form wrapper: the name keeps its
    # default surface ("the length of ...") and its computed value.
    assert issubclass(Length, SymbolicFunction)
    assert verbalize_expression(a(set_of(length(variable(list, []))))) == "Find the length of a list"
    items = variable(list, domain=[[1, 2], [], [3, 4, 5]])
    lengths = sorted(next(iter(row.values())) for row in a(set_of(length(items))).tolist())
    assert lengths == [0, 2, 3]


def test_symbolic_function_binds_its_computed_value_in_a_query():
    # In a query a value SymbolicFunction binds what it COMPUTES (constructed AND called), not the
    # constructed instance.
    numbers = variable(int, domain=[1, 2, 3])
    rows = a(set_of(_Doubled(numbers))).tolist()
    values = sorted(next(iter(row.values())) for row in rows)
    assert values == [2, 4, 6]


@dataclass(eq=False)
class Parity(SymbolicFunction):
    number: int

    def __call__(self) -> int:
        return self.number % 2


parity = functional_form(Parity)


@dataclass(eq=False)
class GetQuarter(SymbolicFunction):
    month: int

    def __call__(self) -> int:
        return (self.month - 1) // 3 + 1


get_quarter = functional_form(GetQuarter)


@dataclass(eq=False)
class IsOneMonth(Predicate):
    period: int

    def __call__(self) -> bool:
        return True


is_one_month = functional_form(IsOneMonth)


@dataclass(eq=False)
class IsEven(Predicate):
    number: int

    def __call__(self) -> bool:
        return self.number % 2 == 0


is_even = functional_form(IsEven)


@dataclass(eq=False)
class Divides(Predicate):
    divisor: int
    dividend: int

    def __call__(self) -> bool:
        return self.dividend % self.divisor == 0


divides = functional_form(Divides)


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
    # length returns int, so it is a value, not a predicate -- it must not render as a clause.
    assert not InstantiatedPlanner.renders_as_predicate_clause(length(variable(list, [])))


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


@dataclass(eq=False)
class _Tripled(SymbolicFunction):
    """A value SymbolicFunction with NO fragment override, to test the inherited default surface."""

    number: int
    """The number it triples."""

    def __call__(self) -> int:
        return self.number * 3


@dataclass(eq=False)
class _IsPositive(Predicate):
    """A Predicate with NO fragment override, to test the inherited default clause surface."""

    number: int
    """The number checked for positivity."""

    def __call__(self) -> bool:
        return self.number > 0


def test_value_function_inherits_the_name_based_default_surface():
    # With no override, a SymbolicFunction reads through the inherited default "the <name> of <args>"
    # -- so a value operation needs no per-class fragment.
    assert (
        verbalize_expression(a(set_of(_Tripled(variable(int, [])))))
        == "Find the tripled of an int"
    )


def test_predicate_inherits_the_name_based_default_clause():
    # With no override, a Predicate reads through the inherited default clause, negating inline under
    # a where with coreference.
    number = variable(int, [])
    assert (
        verbalize_expression(an(entity(number).where(_IsPositive(number))))
        == "Find an int such that it is positive"
    )


def test_preview_shows_the_inherited_default_value_surface():
    # preview_verbalization lets a developer SEE the default surface (args as field-named placeholders)
    # and decide inherit-vs-override -- here the name "Tripled" is not a noun, so the awkward reading
    # is exactly the signal to override.
    assert Length.preview_verbalization() == "the length of iterable"
    assert _Tripled.preview_verbalization() == "the tripled of number"


def test_preview_shows_the_inherited_default_predicate_clause():
    assert _IsPositive.preview_verbalization() == "number is positive"


def test_preview_shows_a_custom_override_surface():
    # An overridden _verbalization_fragment_ is previewed too, so the same tool confirms the override.
    assert _RemainingLoad.preview_verbalization() == "the remaining load"


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
