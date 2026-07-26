"""
Unit tests for :class:`Expert`'s policy: what to ask, and how to validate the answer.

Exercises :meth:`Expert.ask_for_conditions`/:meth:`Expert.ask_for_rule` directly against a
hand-built :class:`CaseContext` and a stub :class:`ExpertInterface` — no
:class:`EQLSingleClassRDR` (that engine-level round trip belongs to ``d-core-single-class``'s
own test suite).
"""

from __future__ import annotations

import unittest

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
from krrood.entity_query_language.rdr.exceptions import (
    NoConclusionProvided,
    NoConditionsProvided,
)
from krrood.entity_query_language.rdr.expert import AnswerName, Expert, RuleAnswer
from krrood.entity_query_language.rdr.interface import (
    EXIT_NAME,
    CaseContext,
    ExpertInterface,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.utils import UNSET

from .animal import Animal, Species, make_animal


class AbortingInterface(ExpertInterface):
    """
    A test double that simulates the expert calling ``exit()`` immediately.
    """

    def _run(self, namespace, header, validate):
        namespace[EXIT_NAME]()


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


class TestAskForConditions(unittest.TestCase):
    def test_returns_the_interfaces_conditions_answer(self):
        case = make_animal("stingray", hair=False)
        case_variable = variable(Animal, domain=[])
        expression = case_variable.hair == True
        interface = FunctionInterface(
            answer_fn=lambda context, requests: {AnswerName.CONDITIONS: expression}
        )
        expert = Expert(interface=interface)

        result = expert.ask_for_conditions(_context(case, case_variable))

        self.assertIs(result, expression)

    def test_raises_no_conditions_provided_on_abort(self):
        case = make_animal("stingray")
        expert = Expert(interface=AbortingInterface())

        with self.assertRaises(NoConditionsProvided) as raised:
            expert.ask_for_conditions(_context(case))
        self.assertIs(raised.exception.case, case)


class TestAskForRule(unittest.TestCase):
    def setUp(self):
        self.domain = resolve_conclusion_domain(Animal, "species")

    def test_asks_conditions_when_conclusion_differs_from_current(self):
        case = make_animal("orca", aquatic=True)
        case_variable = variable(Animal, domain=[])
        expression = case_variable.aquatic == True

        def answer(context, requests):
            names = [r.name for r in requests]
            if AnswerName.CONCLUSION in names:
                return {AnswerName.CONCLUSION: Species.mammal}
            return {AnswerName.CONDITIONS: expression}

        expert = Expert(interface=FunctionInterface(answer_fn=answer))
        context = _context(
            case, case_variable, current_conclusion=UNSET, conclusion_domain=self.domain
        )

        result = expert.ask_for_rule(context)

        self.assertEqual(
            result, RuleAnswer(conclusion=Species.mammal, conditions=expression)
        )

    def test_keeps_current_conclusion_and_skips_conditions_when_unchanged(self):
        case = make_animal("orca", aquatic=True)
        calls = []

        def answer(context, requests):
            calls.append([r.name for r in requests])
            return {AnswerName.CONCLUSION: Species.mammal}

        expert = Expert(interface=FunctionInterface(answer_fn=answer))
        context = _context(
            case, current_conclusion=Species.mammal, conclusion_domain=self.domain
        )

        result = expert.ask_for_rule(context)

        self.assertEqual(result, RuleAnswer(conclusion=Species.mammal, conditions=None))
        self.assertEqual(
            len(calls), 1, "conditions must not be asked for an unchanged conclusion"
        )

    def test_keeps_current_conclusion_and_skips_conditions_when_left_unset(self):
        case = make_animal("orca", aquatic=True)
        calls = []

        def answer(context, requests):
            calls.append([r.name for r in requests])
            return {AnswerName.CONCLUSION: UNSET}

        expert = Expert(interface=FunctionInterface(answer_fn=answer))
        context = _context(
            case, current_conclusion=Species.mammal, conclusion_domain=self.domain
        )

        result = expert.ask_for_rule(context)

        self.assertEqual(result, RuleAnswer(conclusion=Species.mammal, conditions=None))
        self.assertEqual(
            len(calls),
            1,
            "conditions must not be asked when the conclusion is left unset",
        )

    def test_raises_no_conclusion_provided_on_abort(self):
        case = make_animal("orca")
        expert = Expert(interface=AbortingInterface())
        context = _context(
            case, current_conclusion=UNSET, conclusion_domain=self.domain
        )

        with self.assertRaises(NoConclusionProvided) as raised:
            expert.ask_for_rule(context)
        self.assertIs(raised.exception.case, case)


class TestSuggestedConclusion(unittest.TestCase):
    def setUp(self):
        self.domain = resolve_conclusion_domain(Animal, "species")
        self.validator = lambda value: self.domain.validate(value, allow_unset=False)

    def test_returns_first_validating_suggestion(self):
        class Suggests:
            def suggest(self, context):
                return Species.bird

        expert = Expert(
            interface=FunctionInterface(answer_fn=lambda c, r: {}), aids=[Suggests()]
        )
        context = _context(make_animal("eagle"), conclusion_domain=self.domain)

        self.assertEqual(
            expert._suggested_conclusion(context, self.validator), Species.bird
        )

    def test_skips_non_validating_suggestions(self):
        class SuggestsInvalid:
            def suggest(self, context):
                return "not-a-species"

        class SuggestsValid:
            def suggest(self, context):
                return Species.fish

        expert = Expert(
            interface=FunctionInterface(answer_fn=lambda c, r: {}),
            aids=[SuggestsInvalid(), SuggestsValid()],
        )
        context = _context(make_animal("tuna"), conclusion_domain=self.domain)

        self.assertEqual(
            expert._suggested_conclusion(context, self.validator), Species.fish
        )

    def test_returns_unset_when_no_aid_suggests(self):
        expert = Expert(interface=FunctionInterface(answer_fn=lambda c, r: {}))
        context = _context(make_animal("gecko"), conclusion_domain=self.domain)

        self.assertIs(expert._suggested_conclusion(context, self.validator), UNSET)


class TestAnswerName(unittest.TestCase):
    def test_members_are_plain_strings(self):
        self.assertEqual(AnswerName.CONDITIONS, "conditions")
        self.assertEqual(AnswerName.CONCLUSION, "conclusion")

    def test_example_assignment_is_built_over_case_variable(self):
        self.assertEqual(
            AnswerName.CONDITIONS.example_assignment,
            "conditions = case_variable.some_attr == True",
        )


if __name__ == "__main__":
    unittest.main()
