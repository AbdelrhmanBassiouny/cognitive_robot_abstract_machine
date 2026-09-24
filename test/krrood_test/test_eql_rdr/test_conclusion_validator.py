"""
Tests for the domain-aware conclusion validator and the answer-default plumbing.

Covers each layer of :meth:`ConclusionDomain.validator` (unset / None / enumerable /
isinstance / open) and that ``AnswerRequest.default`` seeds the namespace (so the
conclusion can be seeded with ``...``, distinct from a deliberate ``None``).
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    AnswerValidator,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.answer_vocabulary import (
    AnswerName,
    NamespaceName,
)

from .animal import Animal, Species
from .test_conclusion_domain import Colour, Doc, Light, RequiredColour, Tag


@dataclass
class _AlwaysValid(AnswerValidator):
    """
    A no-op :class:`AnswerValidator` test double for plumbing tests that never exercise
    validation itself.
    """

    def validate(self, value):
        return None


#: The conclusion domain of an ``Optional[Species]`` attribute.
SPECIES_DOMAIN = resolve_conclusion_domain(Animal, "species")

#: The conclusion domain of a non-``Optional`` enum attribute.
REQUIRED_COLOUR_DOMAIN = resolve_conclusion_domain(RequiredColour, "colour")

#: The conclusion domain of a ``bool`` attribute.
LIGHT_ON_DOMAIN = resolve_conclusion_domain(Light, "on")


class TestConclusionValidatorEnumerable:
    def test_member_accepted(self):
        validate = SPECIES_DOMAIN.validator(allow_unset=False)
        assert validate(Species.mammal) is None

    def test_non_member_rejected_with_member_list(self):
        validate = SPECIES_DOMAIN.validator(allow_unset=False)
        error = validate("mammal")
        assert error is not None
        assert "must be one of" in str(error)
        assert "Species.mammal" in str(error)

    def test_none_accepted_when_optional(self):
        validate = SPECIES_DOMAIN.validator(allow_unset=False)
        assert validate(None) is None

    def test_unset_rejected_when_not_allowed(self):
        validate = SPECIES_DOMAIN.validator(allow_unset=False)
        error = validate(...)
        assert error is not None
        assert "No rule fired" in str(error)

    def test_unset_accepted_when_allowed(self):
        validate = SPECIES_DOMAIN.validator(allow_unset=True)
        assert validate(...) is None


class TestConclusionValidatorRequiredEnum:
    def test_none_rejected_when_not_optional(self):
        validate = REQUIRED_COLOUR_DOMAIN.validator(allow_unset=False)
        error = validate(None)
        assert error is not None
        assert "may not be None" in str(error)

    def test_member_accepted(self):
        validate = REQUIRED_COLOUR_DOMAIN.validator(allow_unset=False)
        assert validate(Colour.red) is None


class TestConclusionValidatorOpenType:
    def test_optional_str_accepts_str_and_none_rejects_other(self):
        domain = resolve_conclusion_domain(Doc, "label")  # Optional[str]
        validate = domain.validator(allow_unset=False)
        assert validate("hello") is None
        assert validate(None) is None
        error = validate(5)
        assert error is not None
        assert "must be a str" in str(error)

    def test_required_str_rejects_none(self):
        domain = resolve_conclusion_domain(Tag, "name")  # str, non-Optional
        validate = domain.validator(allow_unset=False)
        assert validate("x") is None
        assert validate(None) is not None


class TestConclusionValidatorBool:
    def test_bool_accepted(self):
        validate = LIGHT_ON_DOMAIN.validator(allow_unset=False)
        assert validate(True) is None
        assert validate(False) is None

    def test_non_bool_rejected(self):
        validate = LIGHT_ON_DOMAIN.validator(allow_unset=False)
        assert validate("yes") is not None

    def test_int_rejected_by_bool_domain(self):
        # Regression: 1 == True in Python, so a naive membership check would accept int 1.
        validate = LIGHT_ON_DOMAIN.validator(allow_unset=False)
        assert validate(1) is not None


class TestAnswerDefaultPlumbing:
    def test_answer_request_default_is_none_by_default(self):
        request = AnswerRequest(
            name=AnswerName.CONDITIONS, validate=_AlwaysValid(), example="x = 1"
        )
        assert request.default is None

    def test_build_namespace_seeds_request_default(self):
        context = CaseContext(
            case_instance=object(), case_variable=variable(Animal, domain=[])
        )
        interface = FunctionInterface(answer_function=lambda c, r: {})
        request = AnswerRequest(
            name=AnswerName.CONCLUSION,
            validate=_AlwaysValid(),
            example="x",
            default=...,
        )
        namespace = interface._build_namespace(context, [request])
        assert namespace[AnswerName.CONCLUSION] is ...
        assert NamespaceName.CASE_INSTANCE in namespace

    def test_case_context_defaults(self):
        context = CaseContext(
            case_instance=object(), case_variable=variable(Animal, domain=[])
        )
        assert context.conclusion_domain is None
        assert context.helpers == []
