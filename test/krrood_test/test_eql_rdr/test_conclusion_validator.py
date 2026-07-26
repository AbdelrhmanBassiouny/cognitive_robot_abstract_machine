"""
Tests for the domain-aware conclusion validator and the answer-default plumbing.

Covers each layer of ``make_conclusion_validator`` (unset / None / enumerable /
isinstance / open) and that ``AnswerRequest.default`` seeds the namespace (so the
conclusion can be seeded with ``UNSET``, distinct from a deliberate ``None``).
"""

from __future__ import annotations

import unittest

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
from krrood.entity_query_language.rdr.expert import make_conclusion_validator
from krrood.entity_query_language.rdr.interface import (
    CASE_INSTANCE_NAME,
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.utils import UNSET

from .animal import Animal, Species
from .test_conclusion_domain import Colour, Doc, Light, RequiredColour, Tag


class TestConclusionValidatorEnumerable(unittest.TestCase):
    def setUp(self):
        self.domain = resolve_conclusion_domain(Animal, "species")  # Optional[Species]

    def test_member_accepted(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        self.assertIsNone(validate(Species.mammal))

    def test_non_member_rejected_with_member_list(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        error = validate("mammal")
        self.assertIsNotNone(error)
        self.assertIn("must be one of", str(error))
        self.assertIn("Species.mammal", str(error))

    def test_none_accepted_when_optional(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        self.assertIsNone(validate(None))

    def test_unset_rejected_when_not_allowed(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        error = validate(UNSET)
        self.assertIsNotNone(error)
        self.assertIn("No rule fired", str(error))

    def test_unset_accepted_when_allowed(self):
        validate = make_conclusion_validator(self.domain, allow_unset=True)
        self.assertIsNone(validate(UNSET))


class TestConclusionValidatorRequiredEnum(unittest.TestCase):
    def setUp(self):
        self.domain = resolve_conclusion_domain(
            RequiredColour, "colour"
        )  # non-Optional

    def test_none_rejected_when_not_optional(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        error = validate(None)
        self.assertIsNotNone(error)
        self.assertIn("may not be None", str(error))

    def test_member_accepted(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        self.assertIsNone(validate(Colour.red))


class TestConclusionValidatorOpenType(unittest.TestCase):
    def test_optional_str_accepts_str_and_none_rejects_other(self):
        domain = resolve_conclusion_domain(Doc, "label")  # Optional[str]
        validate = make_conclusion_validator(domain, allow_unset=False)
        self.assertIsNone(validate("hello"))
        self.assertIsNone(validate(None))
        error = validate(5)
        self.assertIsNotNone(error)
        self.assertIn("must be a str", str(error))

    def test_required_str_rejects_none(self):
        domain = resolve_conclusion_domain(Tag, "name")  # str, non-Optional
        validate = make_conclusion_validator(domain, allow_unset=False)
        self.assertIsNone(validate("x"))
        self.assertIsNotNone(validate(None))


class TestConclusionValidatorBool(unittest.TestCase):
    def setUp(self):
        self.domain = resolve_conclusion_domain(Light, "on")

    def test_bool_accepted(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        self.assertIsNone(validate(True))
        self.assertIsNone(validate(False))

    def test_non_bool_rejected(self):
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        self.assertIsNotNone(validate("yes"))

    def test_int_rejected_by_bool_domain(self):
        # Regression: 1 == True in Python, so a naive membership check would accept int 1.
        validate = make_conclusion_validator(self.domain, allow_unset=False)
        self.assertIsNotNone(validate(1))


class TestAnswerDefaultPlumbing(unittest.TestCase):
    def test_answer_request_default_is_none_by_default(self):
        request = AnswerRequest(
            name="conditions", validate=lambda v: None, example="x = 1"
        )
        self.assertIsNone(request.default)

    def test_build_namespace_seeds_request_default(self):
        context = CaseContext(
            case_instance=object(), case_variable=variable(Animal, domain=[])
        )
        interface = FunctionInterface(answer_fn=lambda c, r: {})
        request = AnswerRequest(
            name="conclusion", validate=lambda v: None, example="x", default=UNSET
        )
        namespace = interface._build_namespace(context, [request])
        self.assertIs(namespace["conclusion"], UNSET)
        self.assertIn(CASE_INSTANCE_NAME, namespace)

    def test_case_context_defaults(self):
        context = CaseContext(
            case_instance=object(), case_variable=variable(Animal, domain=[])
        )
        self.assertIsNone(context.conclusion_domain)
        self.assertEqual(context.aids, [])


if __name__ == "__main__":
    unittest.main()
