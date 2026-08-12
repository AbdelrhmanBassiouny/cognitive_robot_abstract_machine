"""
Tests for the ``DataclassException`` hierarchy the Expert policy split introduces:

conditions/conclusion validation failures and the shared no-answer-provided exception.
"""

from __future__ import annotations

import unittest

from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
from krrood.entity_query_language.rdr.exceptions import (
    ConclusionMayNotBeNone,
    ConclusionNotInDomain,
    ConclusionRequired,
    ConclusionWrongType,
    ConditionsNotAnExpression,
    ConditionsRequired,
    NoAnswerProvided,
    NoConclusionProvided,
    NoConditionsProvided,
    WrongConclusionProvided,
)
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName

from .animal import Animal, Species, make_animal


class TestNoAnswerProvidedException(unittest.TestCase):
    def test_names_the_case_and_the_missing_answer(self):
        case = make_animal("otter")
        error = NoAnswerProvided(case=case, answer_name=AnswerName.CONDITIONS)
        self.assertIn(repr(case), str(error))
        self.assertIn("conditions", str(error))

    def test_covers_both_conditions_and_conclusion(self):
        case = make_animal("otter")
        for answer_name in AnswerName:
            error = NoAnswerProvided(case=case, answer_name=answer_name)
            self.assertIn(answer_name, str(error))


class TestNoAnswerProvidedSubclasses(unittest.TestCase):
    def test_no_conditions_provided_presets_the_answer_name(self):
        case = make_animal("otter")
        error = NoConditionsProvided(case=case)
        self.assertIsInstance(error, NoAnswerProvided)
        self.assertEqual(error.answer_name, AnswerName.CONDITIONS)

    def test_no_conclusion_provided_presets_the_answer_name(self):
        case = make_animal("otter")
        error = NoConclusionProvided(case=case)
        self.assertIsInstance(error, NoAnswerProvided)
        self.assertEqual(error.answer_name, AnswerName.CONCLUSION)


class TestConditionsExceptions(unittest.TestCase):
    def test_conditions_required_names_both_namespace_variables(self):
        error = ConditionsRequired(
            answer_name=AnswerName.CONDITIONS, case_variable_name="case_variable"
        )
        self.assertIn("conditions", str(error))
        self.assertIn("case_variable", str(error))

    def test_conditions_not_an_expression_names_the_offending_value(self):
        error = ConditionsNotAnExpression(
            value=42,
            answer_name=AnswerName.CONDITIONS,
            case_variable_name="case_variable",
            case_instance_name="case_instance",
        )
        self.assertIn("int", str(error))
        self.assertIn("case_instance", str(error))


class TestConclusionExceptions(unittest.TestCase):
    def setUp(self):
        self.domain = resolve_conclusion_domain(Animal, "species")

    def test_conclusion_required_is_not_a_wrong_conclusion_provided(self):
        # ConclusionRequired means nothing was given at all, distinct from the
        # WrongConclusionProvided family (something was given, but it's wrong).
        error = ConclusionRequired(domain=self.domain)
        self.assertNotIsInstance(error, WrongConclusionProvided)
        self.assertIn(self.domain.hint(), str(error))

    def test_wrong_conclusion_provided_is_abstract(self):
        with self.assertRaises(TypeError):
            WrongConclusionProvided(domain=self.domain)

    def test_conclusion_may_not_be_none_is_a_wrong_conclusion_provided(self):
        error = ConclusionMayNotBeNone(domain=self.domain)
        self.assertIsInstance(error, WrongConclusionProvided)
        self.assertIn(self.domain.hint(), str(error))

    def test_conclusion_not_in_domain_is_a_wrong_conclusion_provided(self):
        error = ConclusionNotInDomain(value="mammal", domain=self.domain)
        self.assertIsInstance(error, WrongConclusionProvided)
        self.assertIn("mammal", str(error))
        self.assertIn(self.domain.display(), str(error))

    def test_conclusion_wrong_type_is_a_wrong_conclusion_provided(self):
        error = ConclusionWrongType(value=5, domain=self.domain)
        self.assertIsInstance(error, WrongConclusionProvided)
        self.assertIn("int", str(error))
        self.assertIn(self.domain.type_display, str(error))

    def test_conclusion_exceptions_preset_the_answer_name(self):
        self.assertEqual(
            ConclusionRequired(domain=self.domain).answer_name, AnswerName.CONCLUSION
        )
        self.assertEqual(
            ConclusionMayNotBeNone(domain=self.domain).answer_name,
            AnswerName.CONCLUSION,
        )
        self.assertEqual(
            ConclusionNotInDomain(value="mammal", domain=self.domain).answer_name,
            AnswerName.CONCLUSION,
        )
        self.assertEqual(
            ConclusionWrongType(value=5, domain=self.domain).answer_name,
            AnswerName.CONCLUSION,
        )


if __name__ == "__main__":
    unittest.main()
