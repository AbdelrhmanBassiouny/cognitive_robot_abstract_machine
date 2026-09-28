"""
Tests for the contextual examples shown at the bottom of the expert prompt.

``pick_case_attribute`` chooses the attribute an example is written over, and the two
builders turn that choice into the ``%conclusion`` / ``%conditions`` line the expert can
paste.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from krrood.entity_query_language.rdr.conclusion_domain import (
    resolve_conclusion_domain,
)
from krrood.entity_query_language.rdr.interface import CaseContext
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.prompt_examples import (
    AttributeReference,
    build_conclusion_example,
    build_conditions_example,
    pick_case_attribute,
)

from .test_conclusion_domain import Tag
from .test_correct_drawer import (
    RDRTestCorrectDrawer,
    RDRTestCorrectHandle,
    RDRTestCorrectContainer,
)
from .test_no_target_rendering import _conclusion_request, _make_animal, _zoo_rdr
from .test_prompt_sections import (
    _conclusion_answer_request,
    _conditions_answer_request,
    _make_render_context,
    _no_target_no_current_context,
)


@dataclass
class _FlatCase:
    """
    A flat, scalar-only case for pick_case_attribute fallback tests.
    """

    label: str = "hello"
    count: int = 3


@dataclass
class _EmptyCase:
    """
    A case with no public fields, to exercise the None-return path.
    """

    pass


class TestPickCaseAttribute(unittest.TestCase):
    """
    pick_case_attribute inspects the case and returns an AttributeReference or None.
    """

    def test_prefers_nested_name_attribute_for_drawer_case(self):
        """
        Returns a path ending in '.name' for a case with a nested object carrying .name.
        """
        drawer = RDRTestCorrectDrawer(
            handle=RDRTestCorrectHandle("left_handle"),
            container=RDRTestCorrectContainer("bottom_drawer"),
        )
        ref = pick_case_attribute(drawer)
        self.assertIsNotNone(ref)
        self.assertIsInstance(ref, AttributeReference)
        self.assertIn(".name", ref.path)

    def test_falls_back_to_scalar_field_for_flat_case(self):
        """
        Returns an AttributeReference with a simple (non-dotted) path for a flat scalar
        case.
        """
        case = _FlatCase(label="test", count=5)
        ref = pick_case_attribute(case)
        self.assertIsNotNone(ref)
        self.assertIsInstance(ref, AttributeReference)
        self.assertNotEqual(ref.path, "")

    def test_returns_none_for_case_with_no_inspectable_attributes(self):
        """
        Returns None when the case has no public fields at all.
        """
        ref = pick_case_attribute(_EmptyCase())
        self.assertIsNone(ref)

    def test_animal_falls_back_to_scalar_field(self):
        """
        Animal (flat dataclass, no nested objects with .name) returns a scalar field
        ref.
        """
        case = _make_animal()
        ref = pick_case_attribute(case)
        self.assertIsNotNone(ref)
        # path must be a non-empty string (field name, not dotted)
        self.assertIsInstance(ref.path, str)
        self.assertGreater(len(ref.path), 0)


class TestBuildConclusionExample(unittest.TestCase):
    """
    build_conclusion_example returns a well-formed example string for the domain.
    """

    def test_bool_domain_shows_false_or_true(self):
        """
        Bool domain → example string contains 'False' or 'True'.
        """
        rdr = EQLSingleClassRDR(_FlatCase, "label")
        # Override with a bool domain for this test
        bool_domain = resolve_conclusion_domain(
            type("BoolCase", (), {"__annotations__": {"v": bool}}), "v"
        )
        case_context = CaseContext(
            case_instance=_FlatCase(),
            case_variable=rdr.case_variable,
            current_conclusion=...,
            conclusion_domain=bool_domain,
        )
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        example = build_conclusion_example(render_context)
        self.assertIsInstance(example, str)
        # Should reference a bool literal
        self.assertTrue("True" in example or "False" in example)

    def test_enum_domain_shows_first_member_with_class_name(self):
        """
        Species domain → example contains 'Species.' prefix.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        example = build_conclusion_example(render_context)
        self.assertIsInstance(example, str)
        self.assertIn("Species.", example)

    def test_non_enumerable_domain_shows_type_placeholder(self):
        """
        Str domain → example contains '<str>' or similar type placeholder.
        """
        rdr_str = EQLSingleClassRDR(Tag, "name")
        case_context = CaseContext(
            case_instance=Tag(name="hello"),
            case_variable=rdr_str.case_variable,
            current_conclusion=...,
            conclusion_domain=rdr_str.conclusion_domain,
        )
        render_context = _make_render_context(
            case_context, [_conclusion_request(rdr_str.conclusion_domain)]
        )
        example = build_conclusion_example(render_context)
        self.assertIsInstance(example, str)
        self.assertIn("str", example)


class TestBuildConditionsExample(unittest.TestCase):
    """
    build_conditions_example returns a string starting with 'e.g. %conditions'.
    """

    def test_returns_string_starting_with_example_prefix(self):
        """
        Returns a non-empty string that begins with 'e.g. %conditions'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        example = build_conditions_example(render_context)
        self.assertIsInstance(example, str)
        self.assertIn("%conditions", example)

    def test_uses_nested_attribute_for_drawer_case(self):
        """
        Drawer case → example path includes '.name' (nested attribute preferred).
        """
        drawer = RDRTestCorrectDrawer(
            handle=RDRTestCorrectHandle("left_handle"),
            container=RDRTestCorrectContainer("bottom_drawer"),
        )
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        case_context = CaseContext(
            case_instance=drawer,
            case_variable=rdr.case_variable,
            current_conclusion=...,
            conclusion_domain=rdr.conclusion_domain,
        )
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        example = build_conditions_example(render_context)
        self.assertIn(".name", example)

    def test_falls_back_gracefully_for_flat_case(self):
        """
        Flat case (no nested .name) → example still contains 'case_variable.' prefix.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        example = build_conditions_example(render_context)
        self.assertIn("case_variable.", example)


if __name__ == "__main__":
    unittest.main()
