"""
Tests for the ``DataclassException`` hierarchy the Expert policy split introduces:

conditions/conclusion validation failures and the two `no answer provided` exceptions.
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
    ConditionsNotProvided,
    NoConclusionProvided,
    NoConditionsProvided,
)

from .animal import Animal, Species, make_animal


class TestNoAnswerProvidedExceptions(unittest.TestCase):
    def test_no_conditions_provided_names_the_case(self):
        case = make_animal("otter")
        error = NoConditionsProvided(case=case)
        self.assertIn(repr(case), str(error))

    def test_no_conclusion_provided_names_the_case(self):
        case = make_animal("otter")
        error = NoConclusionProvided(case=case)
        self.assertIn(repr(case), str(error))


class TestConditionsExceptions(unittest.TestCase):
    def test_conditions_not_provided_names_both_namespace_variables(self):
        error = ConditionsNotProvided(
            answer_name="conditions", case_variable_name="case_variable"
        )
        self.assertIn("conditions", str(error))
        self.assertIn("case_variable", str(error))

    def test_conditions_not_an_expression_names_the_offending_value(self):
        error = ConditionsNotAnExpression(
            value=42,
            answer_name="conditions",
            case_variable_name="case_variable",
            case_instance_name="case_instance",
        )
        self.assertIn("int", str(error))
        self.assertIn("case_instance", str(error))


class TestConclusionExceptions(unittest.TestCase):
    def setUp(self):
        self.domain = resolve_conclusion_domain(Animal, "species")

    def test_conclusion_required_names_the_domain_hint(self):
        error = ConclusionRequired(self.domain)
        self.assertIn(self.domain.hint(), str(error))

    def test_conclusion_may_not_be_none_names_the_domain_hint(self):
        error = ConclusionMayNotBeNone(self.domain)
        self.assertIn(self.domain.hint(), str(error))

    def test_conclusion_not_in_domain_names_the_value_and_members(self):
        error = ConclusionNotInDomain(value="mammal", domain=self.domain)
        self.assertIn("mammal", str(error))
        self.assertIn(self.domain.display(), str(error))

    def test_conclusion_wrong_type_names_the_value_and_expected_type(self):
        error = ConclusionWrongType(value=5, domain=self.domain)
        self.assertIn("int", str(error))
        self.assertIn(self.domain.type_display, str(error))


if __name__ == "__main__":
    unittest.main()
