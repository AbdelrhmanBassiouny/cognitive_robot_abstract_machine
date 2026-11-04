"""
Unit tests for :class:`Expert`'s policy: what to ask, and how to validate the answer.

Exercises :meth:`Expert.ask_for_conditions`/:meth:`Expert.ask_for_rule` directly against a
hand-built :class:`CaseContext` and a stub :class:`ExpertInterface` — no
:class:`EQLSingleClassRDR` (that engine-level round trip belongs to ``d-core-single-class``'s
own test suite).
"""

from __future__ import annotations

import pytest


from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
from krrood.entity_query_language.rdr.conclusion_helper import (
    ConclusionSuggester,
    ConclusionSupportPresenter,
)
from krrood.entity_query_language.rdr.exceptions import (
    NoConclusionProvided,
    NoConditionsProvided,
)
from krrood.entity_query_language.rdr.expert import AnswerName, Expert, RuleAnswer
from krrood.entity_query_language.rdr.interface import (
    CaseContext,
    ExpertInterface,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.answer_vocabulary import NamespaceName

from .animal import Animal, Species, make_animal


class AbortingInterface(ExpertInterface):
    """
    A test double that simulates the expert calling ``exit()`` immediately.
    """

    def _run(self, namespace, header, validate):
        namespace[NamespaceName.EXIT]()


def _context(case, case_variable=None, **overrides) -> CaseContext:
    """
    Build a :class:`CaseContext` for ``case``, with sensible test defaults.
    """
    return CaseContext(
        case_instance=case,
        case_variable=(
            case_variable if case_variable is not None else variable(Animal, domain=[])
        ),
        **overrides,
    )


#: The conclusion domain the expert validates answers against.
SPECIES_DOMAIN = resolve_conclusion_domain(Animal, "species")

#: A validator over that domain, for the paths where no conclusion yet stands.
SPECIES_VALIDATOR = SPECIES_DOMAIN.validator(allow_unset=False)


class TestAskForConditions:
    def test_returns_the_interfaces_conditions_answer(self):
        case = make_animal("stingray", hair=False)
        case_variable = variable(Animal, domain=[])
        expression = case_variable.hair == True
        interface = FunctionInterface(
            answer_function=lambda context, requests: {
                AnswerName.CONDITIONS: expression
            }
        )
        expert = Expert(interface=interface)

        result = expert.ask_for_conditions(_context(case, case_variable))

        assert result is expression

    def test_raises_no_conditions_provided_for_conditions_on_abort(self):
        case = make_animal("stingray")
        expert = Expert(interface=AbortingInterface())

        with pytest.raises(NoConditionsProvided) as raised:
            expert.ask_for_conditions(_context(case))
        assert raised.value.case is case
        assert raised.value.answer_name == AnswerName.CONDITIONS


class TestAskForRule:
    def test_asks_conditions_when_conclusion_differs_from_current(self):
        case = make_animal("orca", aquatic=True)
        case_variable = variable(Animal, domain=[])
        expression = case_variable.aquatic == True

        def answer(context, requests):
            names = [r.name for r in requests]
            if AnswerName.CONCLUSION in names:
                return {AnswerName.CONCLUSION: Species.mammal}
            return {AnswerName.CONDITIONS: expression}

        expert = Expert(interface=FunctionInterface(answer_function=answer))
        context = _context(
            case,
            case_variable,
            current_conclusion=...,
            conclusion_domain=SPECIES_DOMAIN,
        )

        result = expert.ask_for_rule(context)

        assert result == RuleAnswer(conclusion=Species.mammal, conditions=expression)

    def test_keeps_current_conclusion_and_skips_conditions_when_unchanged(self):
        case = make_animal("orca", aquatic=True)
        calls = []

        def answer(context, requests):
            calls.append([r.name for r in requests])
            return {AnswerName.CONCLUSION: Species.mammal}

        expert = Expert(interface=FunctionInterface(answer_function=answer))
        context = _context(
            case, current_conclusion=Species.mammal, conclusion_domain=SPECIES_DOMAIN
        )

        result = expert.ask_for_rule(context)

        assert result == RuleAnswer(conclusion=Species.mammal, conditions=None)
        assert len(calls) == 1

    def test_keeps_current_conclusion_and_skips_conditions_when_left_unset(self):
        case = make_animal("orca", aquatic=True)
        calls = []

        def answer(context, requests):
            calls.append([r.name for r in requests])
            return {AnswerName.CONCLUSION: ...}

        expert = Expert(interface=FunctionInterface(answer_function=answer))
        context = _context(
            case, current_conclusion=Species.mammal, conclusion_domain=SPECIES_DOMAIN
        )

        result = expert.ask_for_rule(context)

        assert result == RuleAnswer(conclusion=Species.mammal, conditions=None)
        assert len(calls) == 1

    def test_raises_no_conclusion_provided_for_conclusion_on_abort(self):
        case = make_animal("orca")
        expert = Expert(interface=AbortingInterface())
        context = _context(
            case, current_conclusion=..., conclusion_domain=SPECIES_DOMAIN
        )

        with pytest.raises(NoConclusionProvided) as raised:
            expert.ask_for_rule(context)
        assert raised.value.case is case
        assert raised.value.answer_name == AnswerName.CONCLUSION


class TestSuggestedConclusion:
    def test_returns_first_validating_suggestion(self):
        class Suggests(ConclusionSuggester):
            def suggest(self, context):
                return Species.bird

        expert = Expert(
            interface=FunctionInterface(answer_function=lambda c, r: {}),
            helpers=[Suggests()],
        )
        context = _context(make_animal("eagle"), conclusion_domain=SPECIES_DOMAIN)

        assert expert._suggested_conclusion(context, SPECIES_VALIDATOR) == Species.bird

    def test_skips_non_validating_suggestions(self):
        class SuggestsInvalid(ConclusionSuggester):
            def suggest(self, context):
                return "not-a-species"

        class SuggestsValid(ConclusionSuggester):
            def suggest(self, context):
                return Species.fish

        expert = Expert(
            interface=FunctionInterface(answer_function=lambda c, r: {}),
            helpers=[SuggestsInvalid(), SuggestsValid()],
        )
        context = _context(make_animal("tuna"), conclusion_domain=SPECIES_DOMAIN)

        assert expert._suggested_conclusion(context, SPECIES_VALIDATOR) == Species.fish

    def test_returns_ellipsis_when_no_helper_suggests(self):
        expert = Expert(interface=FunctionInterface(answer_function=lambda c, r: {}))
        context = _context(make_animal("gecko"), conclusion_domain=SPECIES_DOMAIN)

        assert expert._suggested_conclusion(context, SPECIES_VALIDATOR) is ...

    def test_a_helper_that_only_presents_is_passed_over(self):
        class Presents(ConclusionSupportPresenter):
            def present(self, context):
                return "a picture of the animal"

        class Suggests(ConclusionSuggester):
            def suggest(self, context):
                return Species.reptile

        expert = Expert(
            interface=FunctionInterface(answer_function=lambda c, r: {}),
            helpers=[Presents(), Suggests()],
        )
        context = _context(make_animal("gecko"), conclusion_domain=SPECIES_DOMAIN)

        assert (
            expert._suggested_conclusion(context, SPECIES_VALIDATOR) == Species.reptile
        )


class TestAnswerName:
    def test_members_are_plain_strings(self):
        assert AnswerName.CONDITIONS == "conditions"
        assert AnswerName.CONCLUSION == "conclusion"

    def test_example_assignment_is_built_over_case_variable(self):
        assert (
            AnswerName.CONDITIONS.example_assignment
            == "conditions = case_variable.some_attr == True"
        )
