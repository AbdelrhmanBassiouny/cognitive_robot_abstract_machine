"""
Tests for the typed predicate-clause vocabulary and its automatic negation.

A predicate states only the affirmative, present-tense clause from typed part-of-speech elements
(``Noun`` / ``Verb`` / ``Copula`` / ``Preposition`` / ``Adjective``); the morphology pass inflects
the verb (agreement) and a wrapping ``Not`` negates it automatically — a verb with do-support, a
copula with suppletion.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

import pytest
from typing_extensions import Any

from krrood.entity_query_language.factories import (
    an,
    and_,
    entity,
    for_all,
    variable,
)
from krrood.entity_query_language.operators.core_logical_operators import Not
from krrood.entity_query_language.predicate import Predicate
from krrood.entity_query_language.verbalization import morphology
from krrood.entity_query_language.verbalization.exceptions import (
    NonFragmentPredicateError,
)
from krrood.entity_query_language.verbalization.example_domain import (
    Department,
    IsReachable,
    Location,
    StaffMember,
    WorksIn,
)
from krrood.entity_query_language.verbalization.fragments.base import (
    flatten_fragment_to_plain_text,
    RoleFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import (
    GrammaticalNumber,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.rendering.realization import (
    realize_tree,
)
from krrood.entity_query_language.verbalization.grammar.conditions.predication import (
    negate_clause,
)
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.rendering.morphology_processor import (
    MorphologyProcessor,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    All,
    clause,
    Copula,
    Noun,
    Preposition,
    Verb,
)

# ── verb morphology ──────────────────────────────────────────────────────────────


def test_third_person_singular_regular_and_irregular():
    assert morphology.third_person_singular("work") == "works"
    assert morphology.third_person_singular("contain") == "contains"
    assert morphology.third_person_singular("have") == "has"
    assert morphology.third_person_singular("go") == "goes"


def _verb_leaf(
    lemma: str,
    *,
    number: GrammaticalNumber = GrammaticalNumber.SINGULAR,
    negated: bool = False,
):
    return RoleFragment(
        text=lemma, role=SemanticRole.VERB, number=number, negated=negated
    )


def test_morphology_realizes_verb_present_tense():
    assert MorphologyProcessor().rewrite(_verb_leaf("work")).text == "works"
    assert (
        MorphologyProcessor()
        .rewrite(_verb_leaf("work", number=GrammaticalNumber.PLURAL))
        .text
        == "work"
    )


def test_morphology_realizes_verb_do_support_negation():
    assert MorphologyProcessor().rewrite(_verb_leaf("work", negated=True)).text == (
        "does not work"
    )
    assert (
        MorphologyProcessor()
        .rewrite(_verb_leaf("work", number=GrammaticalNumber.PLURAL, negated=True))
        .text
        == "do not work"
    )


def test_morphology_realizes_negated_copula():
    copula = RoleFragment(text="is", role=SemanticRole.OPERATOR, negated=True)
    assert MorphologyProcessor().rewrite(copula).text == "is not"
    plural_copula = RoleFragment(
        text="is",
        role=SemanticRole.OPERATOR,
        number=GrammaticalNumber.PLURAL,
        negated=True,
    )
    assert MorphologyProcessor().rewrite(plural_copula).text == "are not"


# ── typed clause vocabulary ──────────────────────────────────────────────────────


def test_verb_element_is_a_verb_role_leaf_carrying_the_lemma():
    leaf = Verb("work").as_fragment()
    assert leaf.role is SemanticRole.VERB
    assert leaf.text == "work"


def test_clause_joins_constituents_in_order():
    built = clause(Noun("Employee"), Verb("work"), Preposition.IN, Noun("Department"))
    # Realization lowers the noun phrases (articles) and inflects the verb for agreement.
    assert (
        flatten_fragment_to_plain_text(realize_tree(built))
        == "an Employee works in a Department"
    )


# ── negate_clause (feature marking) ──────────────────────────────────────────────


def test_negate_clause_marks_the_verb_head():
    built = clause(Noun("Employee"), Verb("work"), Preposition.IN, Noun("Department"))
    negated = negate_clause(built)
    assert negated.parts[1].negated is True


def test_negate_clause_returns_none_without_a_verb_or_copula():
    built = clause(Noun("Employee"), Noun("Department"))
    assert negate_clause(built) is None


# ── end-to-end: affirmative and automatically negated predicates ─────────────────


def test_copula_predicate_affirmative_and_negated():
    assert verbalize_expression(IsReachable(variable(Location, []))) == (
        "a Location is reachable"
    )
    assert verbalize_expression(Not(IsReachable(variable(Location, [])))) == (
        "a Location is not reachable"
    )


def test_verb_predicate_affirmative_and_negated_with_do_support():
    employee, department = variable(StaffMember, []), variable(Department, [])
    assert verbalize_expression(WorksIn(employee, department)) == (
        "a StaffMember works in a Department"
    )
    assert verbalize_expression(Not(WorksIn(employee, department))) == (
        "a StaffMember does not work in a Department"
    )


# ── subject-aware clause: pronominalisation and agreement ────────────────────────


def test_clause_subject_pronominalises_in_singular_scope():
    """A predicate whose subject is the singular discourse subject reads *"it"*, not *"the …"*."""
    location = variable(Location, [])
    assert verbalize_expression(an(entity(location).where(IsReachable(location)))) == (
        "Find a Location such that it is reachable"
    )


def test_clause_subject_pronominalises_and_copula_agrees_with_plural_population():
    """Under ``for_all`` the subject is a plural population — *"they"* and *"are"*."""
    location = variable(Location, [])
    assert verbalize_expression(for_all(location, IsReachable(location))) == (
        "for all Locations, they are reachable"
    )


def test_clause_verb_agrees_with_plural_population():
    """A lexical verb (not a copula) likewise agrees with the plural population — *"work"*."""
    employee, department = variable(StaffMember, []), variable(Department, [])
    assert verbalize_expression(for_all(employee, WorksIn(employee, department))) == (
        "for all StaffMembers, they work in a Department"
    )


def test_clause_subject_keeps_noun_phrase_outside_a_subject_scope():
    """A plain predicate (no enclosing subject) keeps its first-mention noun phrase — *"a Location"*."""
    assert verbalize_expression(IsReachable(variable(Location, []))) == (
        "a Location is reachable"
    )


# ── opt-in: render an operand variable by its field name ─────────────────────────


@dataclass(eq=False)
class _Approaches(Predicate):
    """A predicate that names its operand by its field name (its role), not its type."""

    target_location: Any
    """The place approached — verbalized as *"target location"*, not its type name."""

    def __call__(self) -> bool:
        return True

    @classmethod
    def _verbalization_fragment_(cls, operands: Any) -> Any:
        return clause(Verb("approach"), Noun(operands.target_location.by_field_name()))


def test_operand_renders_by_field_name_when_opted_in():
    """``by_field_name`` names the operand variable by its humanised field name, not its type."""
    assert verbalize_expression(_Approaches(variable(Location, []))) == (
        "approaches a target location"
    )


def test_field_name_alias_is_shared_across_mentions_with_coreference():
    """The alias is the variable's display name everywhere, so a re-mention corefers to it
    (*"a target location … the target location"*), not to the type noun."""
    location = variable(Location, [])
    assert verbalize_expression(and_(_Approaches(location), IsReachable(location))) == (
        "approaches a target location, and the target location is reachable"
    )


class _Mode(enum.Enum):
    HIGH = 1
    LOW = 2


def test_noun_renders_a_raw_value_through_the_value_lexicon():
    """``Noun`` accepts a raw value (not only a head word or constituent), lexicalising it the same
    way the value lexicon does — an enum member as its name."""
    assert flatten_fragment_to_plain_text(Noun(_Mode.HIGH).as_fragment()) == "HIGH"
    assert flatten_fragment_to_plain_text(Noun(42).as_fragment()) == "42"


# ── fragments are required ───────────────────────────────────────────────────────


def test_predicate_returning_a_string_template_is_rejected():
    """A hook returning a string (an old-style template) rather than a VerbalizationFragment is an error."""

    @dataclass(eq=False)
    class SaysHello(Predicate):
        who: Any

        def __call__(self) -> bool:
            return True

        @classmethod
        def _verbalization_fragment_(cls, fields):
            return "{who} says hello"  # a string template — no longer supported

    with pytest.raises(NonFragmentPredicateError):
        verbalize_expression(SaysHello(variable(Location, [])))


# ── universal quantifier ───────────────────────────────────────────────────────


def test_all_quantifier_pluralizes_subject_and_agrees_copula():
    # All makes the quantified subject (the first noun after it) plural and agrees the copula; the
    # morphology pass does the inflection ("element" -> "elements", "is" -> "are").
    assert (
        flatten_fragment_to_plain_text(
            realize_tree(clause(All(), Noun("element"), Copula(), Adjective("close")))
        )
        == "all elements are close"
    )


def test_all_quantifier_agrees_a_verb():
    assert (
        flatten_fragment_to_plain_text(
            realize_tree(clause(All(), Noun("robot"), Verb("work")))
        )
        == "all robots work"
    )


def test_all_quantifier_only_pluralizes_the_quantified_subject():
    # "all elements of an array" -- only the fronted subject ("element") is pluralized, not a later
    # noun ("array").
    assert (
        flatten_fragment_to_plain_text(
            realize_tree(
                clause(
                    All(),
                    Noun("element"),
                    Preposition.OF,
                    Noun("array"),
                    Copula(),
                    Adjective("close"),
                )
            )
        )
        == "all elements of an array are close"
    )
