"""
Tests for the ``DataclassException`` hierarchy the Expert policy split introduces:

conditions/conclusion validation failures and the shared no-answer-provided exception.
"""

from __future__ import annotations

import pytest


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

#: The conclusion domain every conclusion-side exception here reports against.
SPECIES_DOMAIN = resolve_conclusion_domain(Animal, "species")


class TestNoAnswerProvidedException:
    def test_names_the_case_and_the_missing_answer(self):
        case = make_animal("otter")
        error = NoAnswerProvided(case=case, answer_name=AnswerName.CONDITIONS)
        assert repr(case) in str(error)
        assert "conditions" in str(error)

    def test_covers_both_conditions_and_conclusion(self):
        case = make_animal("otter")
        for answer_name in AnswerName:
            error = NoAnswerProvided(case=case, answer_name=answer_name)
            assert answer_name in str(error)


class TestNoAnswerProvidedSubclasses:
    def test_no_conditions_provided_presets_the_answer_name(self):
        case = make_animal("otter")
        error = NoConditionsProvided(case=case)
        assert isinstance(error, NoAnswerProvided)
        assert error.answer_name == AnswerName.CONDITIONS

    def test_no_conclusion_provided_presets_the_answer_name(self):
        case = make_animal("otter")
        error = NoConclusionProvided(case=case)
        assert isinstance(error, NoAnswerProvided)
        assert error.answer_name == AnswerName.CONCLUSION


class TestConditionsExceptions:
    def test_conditions_required_names_both_namespace_variables(self):
        error = ConditionsRequired(
            answer_name=AnswerName.CONDITIONS, case_variable_name="case_variable"
        )
        assert "conditions" in str(error)
        assert "case_variable" in str(error)

    def test_conditions_not_an_expression_names_the_offending_value(self):
        error = ConditionsNotAnExpression(
            value=42,
            answer_name=AnswerName.CONDITIONS,
            case_variable_name="case_variable",
            case_instance_name="case_instance",
        )
        assert "int" in str(error)
        assert "case_instance" in str(error)


class TestConclusionExceptions:
    def test_conclusion_required_is_not_a_wrong_conclusion_provided(self):
        # ConclusionRequired means nothing was given at all, distinct from the
        # WrongConclusionProvided family (something was given, but it's wrong).
        error = ConclusionRequired(domain=SPECIES_DOMAIN)
        assert not isinstance(error, WrongConclusionProvided)
        assert SPECIES_DOMAIN.hint() in str(error)

    def test_wrong_conclusion_provided_is_abstract(self):
        with pytest.raises(TypeError):
            WrongConclusionProvided(domain=SPECIES_DOMAIN)

    def test_conclusion_may_not_be_none_is_a_wrong_conclusion_provided(self):
        error = ConclusionMayNotBeNone(domain=SPECIES_DOMAIN)
        assert isinstance(error, WrongConclusionProvided)
        assert SPECIES_DOMAIN.hint() in str(error)

    def test_conclusion_not_in_domain_is_a_wrong_conclusion_provided(self):
        error = ConclusionNotInDomain(value="mammal", domain=SPECIES_DOMAIN)
        assert isinstance(error, WrongConclusionProvided)
        assert "mammal" in str(error)
        assert SPECIES_DOMAIN.display() in str(error)

    def test_conclusion_wrong_type_is_a_wrong_conclusion_provided(self):
        error = ConclusionWrongType(value=5, domain=SPECIES_DOMAIN)
        assert isinstance(error, WrongConclusionProvided)
        assert "int" in str(error)
        assert SPECIES_DOMAIN.type_display in str(error)

    def test_conclusion_exceptions_preset_the_answer_name(self):
        assert (
            ConclusionRequired(domain=SPECIES_DOMAIN).answer_name
            == AnswerName.CONCLUSION
        )
        assert (
            ConclusionMayNotBeNone(domain=SPECIES_DOMAIN).answer_name
            == AnswerName.CONCLUSION
        )
        assert (
            ConclusionNotInDomain(value="mammal", domain=SPECIES_DOMAIN).answer_name
            == AnswerName.CONCLUSION
        )
        assert (
            ConclusionWrongType(value=5, domain=SPECIES_DOMAIN).answer_name
            == AnswerName.CONCLUSION
        )
