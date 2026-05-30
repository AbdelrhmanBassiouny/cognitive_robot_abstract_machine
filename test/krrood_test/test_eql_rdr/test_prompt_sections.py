# Usage: workon cram2 && python -m pytest test/krrood_test/test_eql_rdr/test_prompt_sections.py -q -p no:cacheprovider
"""
Surgical tests for the declarative EQL-RDR prompt system.

The tests are organised in six groups that mirror the implementation phases:

  Group A  — RenderContext property predicates (has_target, has_current_conclusion,
              is_conclusion_request, is_conditions_request)
  Group B  — PromptSection.applicable: each of the 10 sections fires/suppresses correctly
  Group C  — PromptSection.lines: each section emits the contractually required phrases
  Group D  — prompt_examples.py: pick_case_attribute, build_conclusion_example,
              build_conditions_example
  Group E  — magics._make_assign_exit_magic factory (without a real IPython shell)
  Group F  — CaseTableRenderer wrapping contract (long values wrap, not truncate)

Every test verifies exactly one guarantee and is named to describe it precisely.
"""

from __future__ import annotations

import io
import sys
import unittest
from dataclasses import dataclass

from typing_extensions import Optional

# ---------------------------------------------------------------------------
# Imports from existing test peer modules (shared helpers + domain types)
# ---------------------------------------------------------------------------
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
from krrood.entity_query_language.rdr.expert import (
    ANSWER_NAME,
    CONCLUSION_NAME,
    make_conclusion_validator,
)
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
)
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.utils import UNSET

# New modules under test — will raise ImportError until the source is written, which
# is the correct signal to the implementing agent.
from krrood.entity_query_language.rdr.prompt_sections import (  # noqa: E402
    PROMPT_SECTIONS,
    RenderContext,
)
from krrood.entity_query_language.rdr.prompt_examples import (  # noqa: E402
    AttributeRef,
    build_conclusion_example,
    build_conditions_example,
    pick_case_attribute,
)
from krrood.entity_query_language.rdr.magics import (  # noqa: E402
    _make_assign_exit_magic,
)

from .animal import Animal, Species
from .test_correct_drawer import (
    RDRTestCorrectDrawer,
    RDRTestCorrectHandle,
    RDRTestCorrectContainer,
)

# ---------------------------------------------------------------------------
# Re-use the helpers from the existing no-target-rendering test module
# ---------------------------------------------------------------------------
from .test_no_target_rendering import (
    _make_animal,
    _zoo_rdr,
    _iface,
    _conclusion_request,
    _no_rule_context,
    _current_conclusion_context,
)

# ---------------------------------------------------------------------------
# Section-name constants — used to look up the section by name rather than
# position so tests stay robust if the list is reordered.
# ---------------------------------------------------------------------------

_SECTION_NAMES = {s.name: s for s in PROMPT_SECTIONS}


def _section(name: str):
    """Return the PromptSection with the given name, or raise KeyError with a clear message."""
    if name not in _SECTION_NAMES:
        raise KeyError(
            f"Section '{name}' not in PROMPT_SECTIONS. "
            f"Available: {list(_SECTION_NAMES)}"
        )
    return _SECTION_NAMES[name]


# ---------------------------------------------------------------------------
# Minimal helpers for building a RenderContext
# ---------------------------------------------------------------------------


def _make_palette():
    """Return a no-colour Palette from IPythonInterface so tests are ANSI-free."""
    return IPythonInterface(use_color=False).palette


def _conclusion_req(rdr):
    """Build a standard CONCLUSION_NAME AnswerRequest for the zoo RDR domain."""
    domain = rdr.conclusion_domain
    return AnswerRequest(
        name=CONCLUSION_NAME,
        validate=make_conclusion_validator(domain, allow_unset=False),
        example=domain.example_for(CONCLUSION_NAME),
        default=UNSET,
    )


def _conditions_req(rdr):
    """Build a standard ANSWER_NAME (conditions) AnswerRequest."""
    from krrood.entity_query_language.rdr.expert import _validate_conditions

    return AnswerRequest(
        name=ANSWER_NAME,
        validate=_validate_conditions,
        example=f"{ANSWER_NAME} = case_variable.some_attr == True",
    )


def _no_target_no_current_ctx(case, rdr):
    """CaseContext: no target, no current conclusion (labelling, no rule fired)."""
    return _no_rule_context(case, rdr)


def _no_target_with_current_ctx(case, rdr, current=None):
    """CaseContext: no target, current conclusion set."""
    if current is None:
        current = Species.fish
    return _current_conclusion_context(case, rdr, current)


def _with_target_no_current_ctx(case, rdr, target=None):
    """CaseContext: target set, no current conclusion (ground-truth, no rule fired)."""
    if target is None:
        target = Species.bird
    return CaseContext(
        case_instance=case,
        case_variable=rdr.case_variable,
        current_conclusion=UNSET,
        target_conclusion=target,
        conclusion_domain=rdr.conclusion_domain,
    )


def _with_target_and_current_ctx(case, rdr, target=None, current=None):
    """CaseContext: both target and current conclusion set (conflict scenario)."""
    if target is None:
        target = Species.bird
    if current is None:
        current = Species.fish
    return CaseContext(
        case_instance=case,
        case_variable=rdr.case_variable,
        current_conclusion=current,
        target_conclusion=target,
        conclusion_domain=rdr.conclusion_domain,
    )


def _make_render_context(case_ctx, requests, palette=None):
    """Build a RenderContext from a CaseContext and a list of AnswerRequests."""
    if palette is None:
        palette = _make_palette()
    return RenderContext(case=case_ctx, requests=requests, palette=palette)


# ---------------------------------------------------------------------------
# Group A — RenderContext property predicates
# ---------------------------------------------------------------------------


class TestRenderContextHasTarget(unittest.TestCase):
    """has_target delegates to the underlying CaseContext.target_conclusion sentinel check."""

    def test_has_target_is_false_when_no_target_supplied(self):
        """has_target returns False when target_conclusion is UNSET."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(rc.has_target)

    def test_has_target_is_true_when_target_supplied(self):
        """has_target returns True when a concrete target_conclusion is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(rc.has_target)


class TestRenderContextHasCurrentConclusion(unittest.TestCase):
    """has_current_conclusion delegates to the underlying CaseContext sentinel check."""

    def test_has_current_conclusion_is_false_when_no_rule_fired(self):
        """has_current_conclusion returns False when current_conclusion is UNSET."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(rc.has_current_conclusion)

    def test_has_current_conclusion_is_true_when_rule_fired(self):
        """has_current_conclusion returns True when a concrete current_conclusion is set."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_with_current_ctx(case, rdr, Species.fish)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(rc.has_current_conclusion)


class TestRenderContextIsConclusionRequest(unittest.TestCase):
    """is_conclusion_request is True iff any request.name == CONCLUSION_NAME."""

    def test_is_conclusion_request_true_when_conclusion_request_present(self):
        """is_conclusion_request is True when requests contains a CONCLUSION_NAME request."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(rc.is_conclusion_request)

    def test_is_conclusion_request_false_when_only_conditions_request_present(self):
        """is_conclusion_request is False when only a conditions (ANSWER_NAME) request is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertFalse(rc.is_conclusion_request)


class TestRenderContextIsConditionsRequest(unittest.TestCase):
    """is_conditions_request is True iff any request.name == ANSWER_NAME."""

    def test_is_conditions_request_true_when_conditions_request_present(self):
        """is_conditions_request is True when requests contains an ANSWER_NAME request."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(rc.is_conditions_request)

    def test_is_conditions_request_false_when_only_conclusion_request_present(self):
        """is_conditions_request is False when only a conclusion (CONCLUSION_NAME) request is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(rc.is_conditions_request)


# ---------------------------------------------------------------------------
# Group B — PromptSection.applicable: each section fires on the right context
# ---------------------------------------------------------------------------


class TestGroundTruthConclusionSectionApplicable(unittest.TestCase):
    """Section 'ground_truth_conclusion' is applicable iff has_target is True."""

    def test_applicable_when_target_is_set(self):
        """ground_truth_conclusion.applicable returns True when a target is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(_section("ground_truth_conclusion").applicable(rc))

    def test_not_applicable_when_no_target(self):
        """ground_truth_conclusion.applicable returns False when no target is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("ground_truth_conclusion").applicable(rc))


class TestCurrentConclusionVsTargetSectionApplicable(unittest.TestCase):
    """Section 'current_conclusion_vs_target' is applicable iff has_target is True."""

    def test_applicable_when_target_is_set(self):
        """current_conclusion_vs_target.applicable returns True when target is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(_section("current_conclusion_vs_target").applicable(rc))

    def test_not_applicable_when_no_target(self):
        """current_conclusion_vs_target.applicable returns False when no target."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("current_conclusion_vs_target").applicable(rc))


class TestNoRuleFiredKnownTargetSectionApplicable(unittest.TestCase):
    """Section 'no_rule_fired_known_target': applicable when has_target and NOT has_current."""

    def test_applicable_when_target_set_and_no_current(self):
        """no_rule_fired_known_target.applicable returns True when target set, no current."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(_section("no_rule_fired_known_target").applicable(rc))

    def test_not_applicable_when_no_target(self):
        """no_rule_fired_known_target.applicable returns False when no target."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("no_rule_fired_known_target").applicable(rc))

    def test_not_applicable_when_target_set_and_current_set(self):
        """no_rule_fired_known_target.applicable returns False when both target and current are set."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertFalse(_section("no_rule_fired_known_target").applicable(rc))


class TestConflictResolutionSectionApplicable(unittest.TestCase):
    """Section 'conflict_resolution': applicable when has_target, has_current, current != target."""

    def test_applicable_when_target_and_current_differ(self):
        """conflict_resolution.applicable returns True when target and current conclusions differ."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(
            case, rdr, target=Species.bird, current=Species.fish
        )
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(_section("conflict_resolution").applicable(rc))

    def test_not_applicable_when_no_target(self):
        """conflict_resolution.applicable returns False when no target is set."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_with_current_ctx(case, rdr, Species.fish)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("conflict_resolution").applicable(rc))

    def test_not_applicable_when_current_equals_target(self):
        """conflict_resolution.applicable returns False when current == target (no conflict)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(
            case, rdr, target=Species.bird, current=Species.bird
        )
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertFalse(_section("conflict_resolution").applicable(rc))


class TestLabellingHasCurrentSectionApplicable(unittest.TestCase):
    """Section 'labelling_has_current': applicable when NOT has_target and has_current."""

    def test_applicable_when_no_target_and_current_set(self):
        """labelling_has_current.applicable returns True when no target, current set."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_with_current_ctx(case, rdr, Species.fish)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(_section("labelling_has_current").applicable(rc))

    def test_not_applicable_when_target_set(self):
        """labelling_has_current.applicable returns False when a target is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertFalse(_section("labelling_has_current").applicable(rc))

    def test_not_applicable_when_no_current(self):
        """labelling_has_current.applicable returns False when current is UNSET."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("labelling_has_current").applicable(rc))


class TestLabellingFiredAnchorSectionApplicable(unittest.TestCase):
    """Section 'labelling_fired_anchor': applicable when NOT has_target, has_current, and trace has firing_anchor."""

    def test_applicable_when_no_target_current_set_and_anchor_present(self):
        """labelling_fired_anchor.applicable is True when trace.firing_anchor is set."""
        from krrood.entity_query_language.rdr.observer import ClassificationTrace

        case = _make_animal()
        rdr = _zoo_rdr()

        # Seed a rule so the trace carries a real firing_anchor.
        from krrood.entity_query_language.rdr.interface import FunctionInterface
        from krrood.entity_query_language.rdr.expert import Expert

        def _fish_fn(ctx, reqs):
            return {"conditions": ctx.case_variable.backbone == True}

        fish_expert = Expert(interface=FunctionInterface(answer_fn=_fish_fn))
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
        trace = rdr._trace(case)
        self.assertIsNotNone(trace.firing_anchor)

        ctx = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=trace.conclusion,
            conclusion_domain=rdr.conclusion_domain,
            trace=trace,
        )
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(_section("labelling_fired_anchor").applicable(rc))

    def test_not_applicable_when_no_current(self):
        """labelling_fired_anchor.applicable returns False when current is UNSET."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("labelling_fired_anchor").applicable(rc))

    def test_not_applicable_when_trace_has_no_anchor(self):
        """labelling_fired_anchor.applicable returns False when trace.firing_anchor is None."""
        from krrood.entity_query_language.rdr.observer import ClassificationTrace

        case = _make_animal()
        rdr = _zoo_rdr()
        trace = ClassificationTrace(
            rule_tree_root=None,
            satisfied_condition_ids=None,
            evaluated_expression_ids=None,
            firing_anchor=None,
            conclusion=Species.fish,
        )
        ctx = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=Species.fish,
            conclusion_domain=rdr.conclusion_domain,
            trace=trace,
        )
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("labelling_fired_anchor").applicable(rc))


class TestLabellingNoRuleSectionApplicable(unittest.TestCase):
    """Section 'labelling_no_rule': applicable when NOT has_target and NOT has_current."""

    def test_applicable_when_no_target_and_no_current(self):
        """labelling_no_rule.applicable returns True when no target and no rule fired."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(_section("labelling_no_rule").applicable(rc))

    def test_not_applicable_when_current_is_set(self):
        """labelling_no_rule.applicable returns False when a current conclusion exists."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_with_current_ctx(case, rdr, Species.fish)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertFalse(_section("labelling_no_rule").applicable(rc))


class TestAllowedValuesSectionApplicable(unittest.TestCase):
    """Section 'allowed_values': applicable when NOT has_target and domain is not None."""

    def test_applicable_when_no_target_and_domain_present(self):
        """allowed_values.applicable returns True when no target and a domain is available."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(_section("allowed_values").applicable(rc))

    def test_not_applicable_when_target_is_set(self):
        """allowed_values.applicable returns False when a target conclusion is present."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertFalse(_section("allowed_values").applicable(rc))

    def test_not_applicable_when_domain_is_none(self):
        """allowed_values.applicable returns False when conclusion_domain is None."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=UNSET,
            conclusion_domain=None,
        )
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertFalse(_section("allowed_values").applicable(rc))


class TestContextualExampleSectionApplicable(unittest.TestCase):
    """Section 'contextual_example': always applicable."""

    def test_applicable_for_no_target_no_current_context(self):
        """contextual_example.applicable returns True for the labelling/no-rule scenario."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(_section("contextual_example").applicable(rc))

    def test_applicable_for_target_with_current_context(self):
        """contextual_example.applicable returns True for the conflict scenario."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(_section("contextual_example").applicable(rc))


class TestHelpHintSectionApplicable(unittest.TestCase):
    """Section 'help_hint': always applicable."""

    def test_applicable_for_no_target_context(self):
        """help_hint.applicable returns True for a no-target context."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertTrue(_section("help_hint").applicable(rc))

    def test_applicable_for_target_context(self):
        """help_hint.applicable returns True for a has-target context."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertTrue(_section("help_hint").applicable(rc))


# ---------------------------------------------------------------------------
# Group C — PromptSection.lines: each section emits the contractually required phrases
# ---------------------------------------------------------------------------


def _lines_of(section_name: str, rc: RenderContext):
    """Return the concatenated lines produced by the named section as a single string."""
    return "\n".join(_section(section_name).lines(rc))


class TestGroundTruthConclusionLines(unittest.TestCase):
    """Section 'ground_truth_conclusion' must include the target conclusion value."""

    def test_contains_ground_truth_label(self):
        """lines contain 'Ground-truth conclusion:'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr, Species.bird)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn(
            "Ground-truth conclusion:", _lines_of("ground_truth_conclusion", rc)
        )

    def test_contains_target_value_repr(self):
        """lines contain a repr-like reference to the target conclusion value."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr, Species.bird)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("bird", _lines_of("ground_truth_conclusion", rc))


class TestCurrentConclusionVsTargetLines(unittest.TestCase):
    """Section 'current_conclusion_vs_target' must include the current-conclusion label."""

    def test_contains_current_conclusion_label(self):
        """lines contain 'Current conclusion:'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn(
            "Current conclusion:", _lines_of("current_conclusion_vs_target", rc)
        )

    def test_contains_current_value_repr(self):
        """lines contain a repr-like reference to the current conclusion value."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(case, rdr, current=Species.fish)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("fish", _lines_of("current_conclusion_vs_target", rc))


class TestNoRuleFiredKnownTargetLines(unittest.TestCase):
    """Section 'no_rule_fired_known_target' must describe the no-rule-fired situation and prompt for a condition."""

    def test_contains_no_rule_fired_phrase(self):
        """lines contain 'No rule fired'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("No rule fired", _lines_of("no_rule_fired_known_target", rc))

    def test_contains_write_condition_phrase(self):
        """lines contain 'condition' (prompt to write a condition that fires)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("condition", _lines_of("no_rule_fired_known_target", rc))


class TestConflictResolutionLines(unittest.TestCase):
    """Section 'conflict_resolution' must describe the conflict and request an exceptional condition."""

    def test_contains_concluded_phrase(self):
        """lines contain 'concluded' (the condition concluded the current value)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(
            case, rdr, target=Species.bird, current=Species.fish
        )
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("concluded", _lines_of("conflict_resolution", rc))

    def test_contains_while_it_should_be_phrase(self):
        """lines contain 'while it should be' (the expected target contrast)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(
            case, rdr, target=Species.bird, current=Species.fish
        )
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("while it should be", _lines_of("conflict_resolution", rc))

    def test_contains_provide_a_condition_phrase(self):
        """lines contain 'Provide a condition' (call to action)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_and_current_ctx(
            case, rdr, target=Species.bird, current=Species.fish
        )
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("Provide a condition", _lines_of("conflict_resolution", rc))


class TestLabellingHasCurrentLines(unittest.TestCase):
    """Section 'labelling_has_current' must tell the expert the current conclusion and ask whether it is correct."""

    def test_contains_currently_concludes_phrase(self):
        """lines contain 'currently concludes'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_with_current_ctx(case, rdr, Species.fish)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("currently concludes", _lines_of("labelling_has_current", rc))

    def test_contains_is_that_correct_phrase(self):
        """lines contain 'is that correct'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_with_current_ctx(case, rdr, Species.fish)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("is that correct", _lines_of("labelling_has_current", rc))

    def test_contains_ctrl_d_phrase(self):
        """lines contain 'CTRL+D' (shortcut for accepting the current conclusion)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_with_current_ctx(case, rdr, Species.fish)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("CTRL+D", _lines_of("labelling_has_current", rc))


class TestLabellingFiredAnchorLines(unittest.TestCase):
    """Section 'labelling_fired_anchor' must mention the anchor that fired."""

    def test_contains_fired_on_phrase(self):
        """lines contain 'It fired on'."""
        from krrood.entity_query_language.rdr.observer import ClassificationTrace
        from unittest.mock import MagicMock

        case = _make_animal()
        rdr = _zoo_rdr()
        # A fake anchor that round-trips through format_condition.
        fake_anchor = MagicMock()
        fake_anchor.__str__ = lambda self: "backbone == True"
        trace = ClassificationTrace(
            rule_tree_root=None,
            satisfied_condition_ids=None,
            evaluated_expression_ids=None,
            firing_anchor=fake_anchor,
            conclusion=Species.fish,
        )
        ctx = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=Species.fish,
            conclusion_domain=rdr.conclusion_domain,
            trace=trace,
        )
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("It fired on", _lines_of("labelling_fired_anchor", rc))


class TestLabellingNoRuleLines(unittest.TestCase):
    """Section 'labelling_no_rule' must ask for a conclusion without a 'Set the' instruction."""

    def test_contains_no_rule_fired_phrase(self):
        """lines contain 'No rule fired'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("No rule fired", _lines_of("labelling_no_rule", rc))

    def test_does_not_contain_set_the_phrase(self):
        """lines do NOT contain 'Set the' (removed per Phase 2 wording change)."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertNotIn("Set the", _lines_of("labelling_no_rule", rc))


class TestAllowedValuesLines(unittest.TestCase):
    """Section 'allowed_values' must show enumerable members or the type name."""

    def test_enumerable_domain_contains_choose_one_of(self):
        """lines contain 'Choose one of:' for an enumerable (Species) domain."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("Choose one of:", _lines_of("allowed_values", rc))

    def test_open_domain_contains_conclusion_type(self):
        """lines contain 'Conclusion type:' for an open (str) domain."""
        from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
        from .test_conclusion_domain import Tag

        rdr_str = EQLSingleClassRDR(Tag, "name")
        ctx = CaseContext(
            case_instance=Tag(name="hello"),
            case_variable=rdr_str.case_variable,
            current_conclusion=UNSET,
            conclusion_domain=rdr_str.conclusion_domain,
        )
        rc = _make_render_context(ctx, [_conclusion_request(rdr_str.conclusion_domain)])
        self.assertIn("Conclusion type:", _lines_of("allowed_values", rc))


class TestHelpHintLines(unittest.TestCase):
    """Section 'help_hint' must always reference %help."""

    def test_contains_percent_help(self):
        """lines contain '%help'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("%help", _lines_of("help_hint", rc))


class TestContextualExampleLines(unittest.TestCase):
    """Section 'contextual_example' dispatches to %conclusion or %conditions depending on the request."""

    def test_lines_for_conclusion_request_contain_conclusion_magic(self):
        """lines contain '%conclusion' when the request is a conclusion (no-target) request."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        self.assertIn("%conclusion", _lines_of("contextual_example", rc))

    def test_lines_for_conditions_request_contain_conditions_magic(self):
        """lines contain '%conditions' when the request is a conditions (has-target) request."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _with_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        self.assertIn("%conditions", _lines_of("contextual_example", rc))


# ---------------------------------------------------------------------------
# Group D — prompt_examples.py: pick_case_attribute, build_conclusion_example,
#           build_conditions_example
# ---------------------------------------------------------------------------


@dataclass
class _FlatCase:
    """A flat, scalar-only case for pick_case_attribute fallback tests."""

    label: str = "hello"
    count: int = 3


@dataclass
class _EmptyCase:
    """A case with no public fields, to exercise the None-return path."""

    pass


class TestPickCaseAttribute(unittest.TestCase):
    """pick_case_attribute inspects the case and returns an AttributeRef or None."""

    def test_prefers_nested_name_attribute_for_drawer_case(self):
        """Returns a path ending in '.name' for a case with a nested object carrying .name."""
        drawer = RDRTestCorrectDrawer(
            handle=RDRTestCorrectHandle("left_handle"),
            container=RDRTestCorrectContainer("bottom_drawer"),
        )
        ref = pick_case_attribute(drawer)
        self.assertIsNotNone(ref)
        self.assertIsInstance(ref, AttributeRef)
        self.assertIn(".name", ref.path)

    def test_falls_back_to_scalar_field_for_flat_case(self):
        """Returns an AttributeRef with a simple (non-dotted) path for a flat scalar case."""
        case = _FlatCase(label="test", count=5)
        ref = pick_case_attribute(case)
        self.assertIsNotNone(ref)
        self.assertIsInstance(ref, AttributeRef)
        self.assertNotEqual(ref.path, "")

    def test_returns_none_for_case_with_no_inspectable_attributes(self):
        """Returns None when the case has no public fields at all."""
        ref = pick_case_attribute(_EmptyCase())
        self.assertIsNone(ref)

    def test_animal_falls_back_to_scalar_field(self):
        """Animal (flat dataclass, no nested objects with .name) returns a scalar field ref."""
        case = _make_animal()
        ref = pick_case_attribute(case)
        self.assertIsNotNone(ref)
        # path must be a non-empty string (field name, not dotted)
        self.assertIsInstance(ref.path, str)
        self.assertGreater(len(ref.path), 0)


class TestBuildConclusionExample(unittest.TestCase):
    """build_conclusion_example returns a well-formed example string for the domain."""

    def test_bool_domain_shows_false_or_true(self):
        """bool domain → example string contains 'False' or 'True'."""
        from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

        rdr = EQLSingleClassRDR(_FlatCase, "label")
        # Override with a bool domain for this test
        bool_domain = resolve_conclusion_domain(
            type("BoolCase", (), {"__annotations__": {"v": bool}}), "v"
        )
        ctx = CaseContext(
            case_instance=_FlatCase(),
            case_variable=rdr.case_variable,
            current_conclusion=UNSET,
            conclusion_domain=bool_domain,
        )
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        example = build_conclusion_example(rc)
        self.assertIsInstance(example, str)
        # Should reference a bool literal
        self.assertTrue("True" in example or "False" in example)

    def test_enum_domain_shows_first_member_with_class_name(self):
        """Species domain → example contains 'Species.' prefix."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conclusion_req(rdr)])
        example = build_conclusion_example(rc)
        self.assertIsInstance(example, str)
        self.assertIn("Species.", example)

    def test_non_enumerable_domain_shows_type_placeholder(self):
        """str domain → example contains '<str>' or similar type placeholder."""
        from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
        from .test_conclusion_domain import Tag

        rdr_str = EQLSingleClassRDR(Tag, "name")
        ctx = CaseContext(
            case_instance=Tag(name="hello"),
            case_variable=rdr_str.case_variable,
            current_conclusion=UNSET,
            conclusion_domain=rdr_str.conclusion_domain,
        )
        rc = _make_render_context(ctx, [_conclusion_request(rdr_str.conclusion_domain)])
        example = build_conclusion_example(rc)
        self.assertIsInstance(example, str)
        self.assertIn("str", example)


class TestBuildConditionsExample(unittest.TestCase):
    """build_conditions_example returns a string starting with 'e.g. %conditions'."""

    def test_returns_string_starting_with_example_prefix(self):
        """Returns a non-empty string that begins with 'e.g. %conditions'."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        example = build_conditions_example(rc)
        self.assertIsInstance(example, str)
        self.assertIn("%conditions", example)

    def test_uses_nested_attribute_for_drawer_case(self):
        """Drawer case → example path includes '.name' (nested attribute preferred)."""
        from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

        drawer = RDRTestCorrectDrawer(
            handle=RDRTestCorrectHandle("left_handle"),
            container=RDRTestCorrectContainer("bottom_drawer"),
        )
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        ctx = CaseContext(
            case_instance=drawer,
            case_variable=rdr.case_variable,
            current_conclusion=UNSET,
            conclusion_domain=rdr.conclusion_domain,
        )
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        example = build_conditions_example(rc)
        self.assertIn(".name", example)

    def test_falls_back_gracefully_for_flat_case(self):
        """Flat case (no nested .name) → example still contains 'case_variable.' prefix."""
        case = _make_animal()
        rdr = _zoo_rdr()
        ctx = _no_target_no_current_ctx(case, rdr)
        rc = _make_render_context(ctx, [_conditions_req(rdr)])
        example = build_conditions_example(rc)
        self.assertIn("case_variable.", example)


# ---------------------------------------------------------------------------
# Group E — magics._make_assign_exit_magic factory (without a real IPython shell)
# ---------------------------------------------------------------------------


class _FakeShell:
    """Minimal shell stub for testing _make_assign_exit_magic without IPython."""

    def __init__(self):
        self._force_exit = False
        self._exit_called = False

    def ask_exit(self):
        self._exit_called = True


class TestAssignExitMagic(unittest.TestCase):
    """_make_assign_exit_magic produces a callable that assigns, validates, and exits."""

    def _make_namespace_and_shell(self):
        namespace = {}
        shell = _FakeShell()
        return namespace, shell

    def test_valid_input_sets_variable_in_namespace(self):
        """A valid expression is evaluated and the target name is set in the namespace."""
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            return {}  # no errors

        magic = _make_assign_exit_magic(
            target_name="conclusion",
            shell=shell,
            namespace=namespace,
            validate=validate,
            palette=_make_palette(),
        )
        magic("42")
        self.assertIn("conclusion", namespace)
        self.assertEqual(namespace["conclusion"], 42)

    def test_valid_input_sets_force_exit_true(self):
        """A valid expression causes _force_exit to be set to True on the shell."""
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            return {}

        magic = _make_assign_exit_magic(
            target_name="conclusion",
            shell=shell,
            namespace=namespace,
            validate=validate,
            palette=_make_palette(),
        )
        magic("42")
        self.assertTrue(shell._force_exit)

    def test_valid_input_calls_ask_exit(self):
        """A valid expression causes ask_exit() to be called on the shell."""
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            return {}

        magic = _make_assign_exit_magic(
            target_name="conclusion",
            shell=shell,
            namespace=namespace,
            validate=validate,
            palette=_make_palette(),
        )
        magic("42")
        self.assertTrue(shell._exit_called)

    def test_invalid_input_does_not_set_force_exit(self):
        """When validate() returns an error dict for the target name, _force_exit stays False."""
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            return {"conclusion": "bad value"}

        magic = _make_assign_exit_magic(
            target_name="conclusion",
            shell=shell,
            namespace=namespace,
            validate=validate,
            palette=_make_palette(),
        )
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            magic("99")
        finally:
            sys.stdout = old_stdout

        self.assertFalse(shell._force_exit)

    def test_invalid_input_does_not_call_ask_exit(self):
        """When validate() returns an error, ask_exit is NOT called."""
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            return {"conclusion": "bad value"}

        magic = _make_assign_exit_magic(
            target_name="conclusion",
            shell=shell,
            namespace=namespace,
            validate=validate,
            palette=_make_palette(),
        )
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            magic("99")
        finally:
            sys.stdout = old_stdout
        self.assertFalse(shell._exit_called)

    def test_unevaluatable_expression_does_not_exit(self):
        """A syntax-error expression causes no exit: _force_exit stays False."""
        namespace, shell = self._make_namespace_and_shell()

        def validate():
            return {}

        magic = _make_assign_exit_magic(
            target_name="conclusion",
            shell=shell,
            namespace=namespace,
            validate=validate,
            palette=_make_palette(),
        )
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            magic("this is not valid python !!!!")
        except Exception:
            pass
        finally:
            sys.stdout = old_stdout
        self.assertFalse(shell._force_exit)

    def test_magic_can_reference_existing_namespace_names(self):
        """An expression referencing a name already in namespace resolves correctly."""
        namespace = {"Species": Species}
        shell = _FakeShell()

        def validate():
            return {}

        magic = _make_assign_exit_magic(
            target_name="conclusion",
            shell=shell,
            namespace=namespace,
            validate=validate,
            palette=_make_palette(),
        )
        magic("Species.mammal")
        self.assertEqual(namespace["conclusion"], Species.mammal)


# ---------------------------------------------------------------------------
# Group F — CaseTableRenderer wrapping contract
# ---------------------------------------------------------------------------


class TestCaseTableWrapping(unittest.TestCase):
    """CaseTableRenderer wraps long values instead of truncating them with ellipsis."""

    def test_long_value_wraps_not_truncates(self):
        """A value longer than value_width is present in full across multiple lines (no ellipsis)."""
        from krrood.entity_query_language.rdr.case_table import CaseTableRenderer

        long_str = "x" * 200
        # Force a very narrow max_width to guarantee the value exceeds value_width.
        renderer = CaseTableRenderer(min_column_width=24, max_width=40, use_color=False)

        @dataclass
        class WideCase:
            field_name: str = ""

        case = WideCase(field_name=long_str)
        rendered = renderer.render(case)
        # The full string must appear somewhere in the output (possibly wrapped across lines)
        self.assertIn("x" * 10, rendered)
        # And the ellipsis truncation marker must NOT be present
        self.assertNotIn("...", rendered)

    def test_short_value_unchanged(self):
        """A value shorter than value_width appears verbatim and without modification."""
        from krrood.entity_query_language.rdr.case_table import CaseTableRenderer

        @dataclass
        class NarrowCase:
            label: str = ""

        renderer = CaseTableRenderer(
            min_column_width=24, max_width=200, use_color=False
        )
        case = NarrowCase(label="hello")
        rendered = renderer.render(case)
        self.assertIn("hello", rendered)
        self.assertNotIn("...", rendered)


if __name__ == "__main__":
    unittest.main()
