"""
Tests for the no-ground-truth ("labelling") header rendering in IPythonInterface.

Each test verifies exactly one rendering guarantee of the labelling path:
  - _labelling_lines dispatched when has_target is False
  - no-rule-fired message
  - current-conclusion message with repr of the value
  - "It fired on <condition>" line only when trace.firing_anchor is set
  - enumerable vs. open domain display ("Choose one of:" vs. "Conclusion type:")
  - hint line: always %help, %aid only when aids present
  - aid.present() output folded into header, and called only once per _build_namespace
  - namespace injection: Species injected for enumerable, not for open domain
  - _AID_TEXT_KEY present iff aids non-empty
  - ground-truth (has_target) path still shows "Ground-truth conclusion:"
  - _help_text includes domain-example and %aid only when aids configured

Usage: workon cram2 && python -m pytest test/krrood_test/test_eql_rdr/test_no_target_rendering.py -q -p no:cacheprovider
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from typing_extensions import Optional

from krrood.entity_query_language.rdr.aid import ConclusionAid
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
from krrood.entity_query_language.rdr.expert import (
    CONCLUSION_NAME,
    Expert,
    make_conclusion_validator,
)
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.interactive import (
    AID_MAGIC,
    HELP_MAGIC,
    IPythonInterface,
    _AID_TEXT_KEY,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.utils import UNSET

from .animal import Animal, Species
from .test_conclusion_domain import Doc, Tag

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _make_animal() -> Animal:
    """Construct a minimal Animal without loading the zoo dataset."""
    return Animal(
        name="testanimal",
        hair=True,
        feathers=False,
        eggs=False,
        milk=True,
        airborne=False,
        aquatic=False,
        predator=False,
        toothed=True,
        backbone=True,
        breathes=True,
        venomous=False,
        fins=False,
        legs=4,
        tail=True,
        domestic=True,
        catsize=True,
        species=None,
    )


def _zoo_rdr() -> EQLSingleClassRDR:
    """Return a fresh (empty) RDR for the zoo domain."""
    return EQLSingleClassRDR(Animal, "species")


def _iface() -> IPythonInterface:
    """Return a plain (no-color) IPythonInterface."""
    return IPythonInterface(use_color=False)


def _conclusion_request(domain):
    """Build the standard conclusion AnswerRequest for a domain."""
    return AnswerRequest(
        name=CONCLUSION_NAME,
        validate=make_conclusion_validator(domain, allow_unset=False),
        example=domain.example_for(CONCLUSION_NAME),
        default=UNSET,
    )


def _no_rule_context(case, rdr, aids=None):
    """CaseContext with no current conclusion and no target (labelling, no rule fired)."""
    return CaseContext(
        case_instance=case,
        case_variable=rdr.case_variable,
        current_conclusion=UNSET,
        conclusion_domain=rdr.conclusion_domain,
        aids=aids or [],
    )


def _current_conclusion_context(case, rdr, current, trace=None, aids=None):
    """CaseContext with a current conclusion but no target (labelling, rule fired wrong)."""
    return CaseContext(
        case_instance=case,
        case_variable=rdr.case_variable,
        current_conclusion=current,
        conclusion_domain=rdr.conclusion_domain,
        trace=trace,
        aids=aids or [],
    )


def _render(iface, context, requests=None, errors=None):
    """Call _build_namespace then _render_header and return the header string."""
    if requests is None:
        requests = [_conclusion_request(context.conclusion_domain)]
    if errors is None:
        errors = {}
    iface._build_namespace(context, requests)
    return iface._render_header(context, requests, errors)


# ---------------------------------------------------------------------------
# Test 1: no-rule-fired, no-target — labelling intro lines
# ---------------------------------------------------------------------------


class TestNoRuleFiredNoTargetHeader(unittest.TestCase):
    def test_no_rule_fired_message_present(self):
        """Header contains 'No rule fired — what should this case conclude?' when no rule fired."""
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(_iface(), _no_rule_context(case, rdr))
        self.assertIn("No rule fired", header)
        self.assertIn("what should this case conclude", header)

    def test_choose_one_of_lists_species_members(self):
        """Header contains 'Choose one of:' and lists Species members for enumerable domain."""
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(_iface(), _no_rule_context(case, rdr))
        self.assertIn("Choose one of:", header)
        self.assertIn("Species.mammal", header)
        self.assertIn("Species.molusc", header)

    def test_set_conclusion_and_justify_line_present(self):
        """Header contains 'Set the conclusion, then justify it with a condition.'"""
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(_iface(), _no_rule_context(case, rdr))
        self.assertIn("conclusion", header)
        self.assertIn("condition", header)
        self.assertIn("Set the", header)


# ---------------------------------------------------------------------------
# Test 2: current-conclusion-set, no-target
# ---------------------------------------------------------------------------


class TestCurrentConclusionNoTargetHeader(unittest.TestCase):
    def test_currently_concludes_phrase_present(self):
        """Header contains 'currently concludes' when a rule has fired."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(case, rdr, Species.fish)
        header = _render(_iface(), context)
        self.assertIn("currently concludes", header)

    def test_current_conclusion_repr_present(self):
        """Header contains repr(current_conclusion) in the 'currently concludes' line."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(case, rdr, Species.fish)
        header = _render(_iface(), context)
        self.assertIn(repr(Species.fish), header)

    def test_what_should_it_be_phrase_present(self):
        """Header contains 'what SHOULD it be?' when a rule has fired and no target."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(case, rdr, Species.fish)
        header = _render(_iface(), context)
        self.assertIn("what SHOULD it be?", header)


# ---------------------------------------------------------------------------
# Test 3: "It fired on <condition>" line — with and without trace
# ---------------------------------------------------------------------------


class TestFiredOnLineWithTrace(unittest.TestCase):
    def test_fired_on_line_absent_when_trace_is_none(self):
        """'It fired on' line is absent when trace is None (no trace supplied)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(
            case, rdr, current=Species.fish, trace=None
        )
        header = _render(_iface(), context)
        self.assertNotIn("It fired on", header)

    def test_fired_on_line_present_when_trace_has_anchor(self):
        """'It fired on' line is present when trace.firing_anchor is set."""
        case = _make_animal()
        rdr = _zoo_rdr()

        # Seed a backbone→fish rule so we get a real trace with a firing anchor.
        def _fish_expert_fn(context, requests):
            return {"conditions": context.case_variable.backbone == True}

        fish_expert = Expert(interface=FunctionInterface(answer_fn=_fish_expert_fn))
        # Use a "fish-like" animal (backbone=True).
        fish_case = Animal(
            name="fishcase",
            hair=False,
            feathers=False,
            eggs=True,
            milk=False,
            airborne=False,
            aquatic=True,
            predator=True,
            toothed=True,
            backbone=True,
            breathes=False,
            venomous=False,
            fins=True,
            legs=0,
            tail=True,
            domestic=False,
            catsize=False,
            species=None,
        )
        rdr.fit_case(fish_case, Species.fish, fish_expert)

        # Now get a trace for our test case (backbone=True → fires fish rule).
        trace = rdr._trace(case)
        self.assertIsNotNone(
            trace.firing_anchor,
            "Expected firing_anchor to be set after fitting a backbone rule",
        )
        context = _current_conclusion_context(
            case, rdr, current=trace.conclusion, trace=trace
        )
        header = _render(_iface(), context)
        self.assertIn("It fired on", header)

    def test_fired_on_line_absent_when_firing_anchor_is_none(self):
        """'It fired on' line is absent when trace is present but firing_anchor is None."""
        from krrood.entity_query_language.rdr.observer import ClassificationTrace

        case = _make_animal()
        rdr = _zoo_rdr()
        # Build a synthetic trace with firing_anchor=None.
        trace = ClassificationTrace(
            rule_tree_root=None,
            satisfied_condition_ids=None,
            evaluated_expression_ids=None,
            firing_anchor=None,
            conclusion=UNSET,
        )
        context = _current_conclusion_context(
            case, rdr, current=Species.fish, trace=trace
        )
        header = _render(_iface(), context)
        self.assertNotIn("It fired on", header)


# ---------------------------------------------------------------------------
# Test 4: enumerable vs. open-type domain display
# ---------------------------------------------------------------------------


class TestAllowedValuesLines(unittest.TestCase):
    def test_enumerable_domain_shows_choose_one_of(self):
        """Enumerable domain (Species) → header contains 'Choose one of:'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(_iface(), _no_rule_context(case, rdr))
        self.assertIn("Choose one of:", header)

    def test_enumerable_domain_lists_all_members(self):
        """Enumerable domain → header lists every Species member."""
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(_iface(), _no_rule_context(case, rdr))
        for member in Species:
            self.assertIn(repr(member), header)

    def test_open_domain_shows_conclusion_type(self):
        """Open-type domain (Tag.name: str) → header contains 'Conclusion type: str'."""

        @dataclass
        class StrCase:
            label: str = ""

        rdr_str = EQLSingleClassRDR(Tag, "name")
        domain = rdr_str.conclusion_domain
        context = CaseContext(
            case_instance=Tag(name="hello"),
            case_variable=rdr_str.case_variable,
            current_conclusion=UNSET,
            conclusion_domain=domain,
        )
        request = _conclusion_request(domain)
        iface = _iface()
        iface._build_namespace(context, [request])
        header = iface._render_header(context, [request], {})
        self.assertIn("Conclusion type:", header)
        self.assertIn("str", header)

    def test_open_domain_does_not_show_choose_one_of(self):
        """Open-type domain (str) → header does NOT contain 'Choose one of:'."""
        rdr_str = EQLSingleClassRDR(Tag, "name")
        domain = rdr_str.conclusion_domain
        context = CaseContext(
            case_instance=Tag(name="hello"),
            case_variable=rdr_str.case_variable,
            current_conclusion=UNSET,
            conclusion_domain=domain,
        )
        request = _conclusion_request(domain)
        iface = _iface()
        iface._build_namespace(context, [request])
        header = iface._render_header(context, [request], {})
        self.assertNotIn("Choose one of:", header)


# ---------------------------------------------------------------------------
# Test 5a: hint line always contains %help
# ---------------------------------------------------------------------------


class TestHintLineAlwaysContainsHelp(unittest.TestCase):
    def test_hint_contains_percent_help(self):
        """Hint line always contains '%help'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(_iface(), _no_rule_context(case, rdr))
        self.assertIn(f"%{HELP_MAGIC}", header)


# ---------------------------------------------------------------------------
# Test 5b: %aid appears in hint only when aids are present
# ---------------------------------------------------------------------------


class TestHintLineAidPresence(unittest.TestCase):
    def test_hint_contains_percent_aid_when_aids_present(self):
        """Hint line contains '%aid' when context.aids is non-empty."""

        class DummyAid(ConclusionAid):
            def present(self, context):
                return "AID_OUTPUT"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[DummyAid()])
        header = _render(_iface(), context)
        self.assertIn(f"%{AID_MAGIC}", header)

    def test_hint_does_not_contain_percent_aid_when_no_aids(self):
        """Hint line does NOT contain '%aid' when context.aids is empty."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[])
        header = _render(_iface(), context)
        self.assertNotIn(f"%{AID_MAGIC}", header)


# ---------------------------------------------------------------------------
# Test 6: aid present() output folded into header, called exactly once
# ---------------------------------------------------------------------------


class TestAidFolding(unittest.TestCase):
    def test_aid_present_output_appears_in_header(self):
        """Aid present() text is included in the rendered header."""

        class StaticAid(ConclusionAid):
            def present(self, context):
                return "PIXELS-HERE"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[StaticAid()])
        header = _render(_iface(), context)
        self.assertIn("PIXELS-HERE", header)

    def test_aid_present_called_once_regardless_of_render_calls(self):
        """aid.present() is called exactly once per _build_namespace, not per _render_header."""
        call_count = {"n": 0}

        class CountingAid(ConclusionAid):
            def present(self, context):
                call_count["n"] += 1
                return "COUNTED"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[CountingAid()])
        requests = [_conclusion_request(context.conclusion_domain)]
        iface = _iface()
        # _build_namespace triggers present(); subsequent _render_header calls reuse cache.
        iface._build_namespace(context, requests)
        iface._render_header(context, requests, {})
        iface._render_header(context, requests, {})
        iface._render_header(context, requests, {})
        self.assertEqual(call_count["n"], 1)


# ---------------------------------------------------------------------------
# Test 7: namespace injection of Enum type for enumerable domain
# ---------------------------------------------------------------------------


class TestNamespaceInjection(unittest.TestCase):
    def test_species_injected_for_enumerable_domain(self):
        """_build_namespace injects 'Species' key bound to the Species enum for zoo domain."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(context.conclusion_domain)]
        iface = _iface()
        ns = iface._build_namespace(context, requests)
        self.assertIn("Species", ns)
        self.assertIs(ns["Species"], Species)

    def test_enum_type_not_injected_for_open_domain(self):
        """An open-type (str) domain contributes no tab-completion bindings of its own.

        (We assert on ``namespace_bindings()`` rather than scanning the built namespace,
        because the captured caller scope legitimately contains any enums the test module
        imported — e.g. ``Species`` — independent of the domain injection under test.)
        """
        rdr_str = EQLSingleClassRDR(Tag, "name")
        domain = rdr_str.conclusion_domain
        self.assertFalse(domain.is_enumerable)
        self.assertEqual(domain.namespace_bindings(), {})


# ---------------------------------------------------------------------------
# Test 8: _AID_TEXT_KEY in namespace iff aids non-empty
# ---------------------------------------------------------------------------


class TestAidTextKeyInNamespace(unittest.TestCase):
    def test_aid_text_key_present_when_aids_non_empty(self):
        """_AID_TEXT_KEY is in the namespace when context.aids is non-empty."""

        class MinimalAid(ConclusionAid):
            def present(self, context):
                return "AID"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[MinimalAid()])
        requests = [_conclusion_request(context.conclusion_domain)]
        iface = _iface()
        ns = iface._build_namespace(context, requests)
        self.assertIn(_AID_TEXT_KEY, ns)

    def test_aid_text_key_absent_when_no_aids(self):
        """_AID_TEXT_KEY is NOT in the namespace when context.aids is empty."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[])
        requests = [_conclusion_request(context.conclusion_domain)]
        iface = _iface()
        ns = iface._build_namespace(context, requests)
        self.assertNotIn(_AID_TEXT_KEY, ns)


# ---------------------------------------------------------------------------
# Test 9: ground-truth (has_target) path is unchanged
# ---------------------------------------------------------------------------


class TestGroundTruthPathUnchanged(unittest.TestCase):
    def test_ground_truth_header_contains_ground_truth_conclusion_label(self):
        """has_target=True → header contains 'Ground-truth conclusion:'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=UNSET,
            target_conclusion=Species.bird,
            conclusion_domain=rdr.conclusion_domain,
        )
        from krrood.entity_query_language.rdr.expert import (
            ANSWER_NAME,
            _validate_conditions,
        )

        request = AnswerRequest(
            name=ANSWER_NAME,
            validate=_validate_conditions,
            example=f"conditions = case_variable.some_attr == True",
        )
        iface = _iface()
        iface._build_namespace(context, [request])
        header = iface._render_header(context, [request], {})
        self.assertIn("Ground-truth conclusion:", header)

    def test_ground_truth_header_contains_target_value(self):
        """has_target=True → header contains repr of the target conclusion value."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=UNSET,
            target_conclusion=Species.bird,
            conclusion_domain=rdr.conclusion_domain,
        )
        from krrood.entity_query_language.rdr.expert import (
            ANSWER_NAME,
            _validate_conditions,
        )

        request = AnswerRequest(
            name=ANSWER_NAME,
            validate=_validate_conditions,
            example="conditions = case_variable.some_attr == True",
        )
        iface = _iface()
        iface._build_namespace(context, [request])
        header = iface._render_header(context, [request], {})
        self.assertIn("bird", header)

    def test_ground_truth_header_does_not_contain_no_rule_fired(self):
        """has_target=True → header does NOT contain the labelling 'No rule fired' message."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=UNSET,
            target_conclusion=Species.bird,
            conclusion_domain=rdr.conclusion_domain,
        )
        from krrood.entity_query_language.rdr.expert import (
            ANSWER_NAME,
            _validate_conditions,
        )

        request = AnswerRequest(
            name=ANSWER_NAME,
            validate=_validate_conditions,
            example="conditions = case_variable.some_attr == True",
        )
        iface = _iface()
        iface._build_namespace(context, [request])
        header = iface._render_header(context, [request], {})
        self.assertNotIn("No rule fired — what should this case conclude?", header)


# ---------------------------------------------------------------------------
# Test 10: _help_text includes domain example and %aid iff aids configured
# ---------------------------------------------------------------------------


class TestHelpText(unittest.TestCase):
    def test_help_text_includes_domain_example(self):
        """_help_text includes a domain-sourced example for the conclusion assignment."""
        case = _make_animal()
        rdr = _zoo_rdr()
        domain = rdr.conclusion_domain
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(domain)]
        iface = _iface()
        text = iface._help_text(context, requests)
        # The example is derived from the domain (e.g. "conclusion = Species.<member>")
        self.assertIn("conclusion = Species.", text)

    def test_help_text_includes_percent_aid_when_aids_present(self):
        """_help_text includes a '%aid' line when aids are configured."""

        class DummyAid(ConclusionAid):
            def present(self, context):
                return "X"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[DummyAid()])
        requests = [_conclusion_request(rdr.conclusion_domain)]
        iface = _iface()
        text = iface._help_text(context, requests)
        self.assertIn(f"%{AID_MAGIC}", text)

    def test_help_text_excludes_percent_aid_when_no_aids(self):
        """_help_text does NOT include '%aid' when no aids are configured."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, aids=[])
        requests = [_conclusion_request(rdr.conclusion_domain)]
        iface = _iface()
        text = iface._help_text(context, requests)
        self.assertNotIn(f"%{AID_MAGIC}", text)

    def test_help_text_always_includes_percent_show_tree(self):
        """_help_text always includes '%show_tree'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(rdr.conclusion_domain)]
        iface = _iface()
        text = iface._help_text(context, requests)
        self.assertIn("%show_tree", text)

    def test_help_text_always_includes_percent_help(self):
        """_help_text always includes '%help'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(rdr.conclusion_domain)]
        iface = _iface()
        text = iface._help_text(context, requests)
        self.assertIn(f"%{HELP_MAGIC}", text)


if __name__ == "__main__":
    unittest.main()
