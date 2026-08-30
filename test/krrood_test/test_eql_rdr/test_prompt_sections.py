"""
Tests for the declarative prompt sections the expert's header is assembled from.

Two guarantees per section: :meth:`PromptSection.applicable` fires it on exactly the
situations it names, and :meth:`PromptSection.lines` emits the phrases that situation
promises the expert. The render context's own predicates, which the sections decide by,
are covered first.
"""

from __future__ import annotations

from krrood.entity_query_language.rdr.answer_vocabulary import (
    AnswerName,
)
import unittest

# %% shared helpers and domain types from the peer test modules
from krrood.entity_query_language.rdr.conclusion_domain import (
    ConclusionValidator,
)
from krrood.entity_query_language.rdr.expert import ConditionsValidator
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
)
from krrood.entity_query_language.rdr.interactive import IPythonInterface

from krrood.entity_query_language.rdr.prompt_sections import (
    PROMPT_SECTIONS,
    PromptSection,
    PromptSectionName,
    RenderContext,
)

from .animal import Animal, Species

# %% context builders reused from the no-target rendering tests
from .test_no_target_rendering import (
    _make_animal,
    _zoo_rdr,
    _conclusion_request,
    _no_rule_context,
    _current_conclusion_context,
)

# %% Section-name constants — used to look up the section by name rather than
# position so tests stay robust if the list is reordered.

_SECTIONS_BY_NAME = {section.name: section for section in PROMPT_SECTIONS}


def _section(name: PromptSectionName) -> PromptSection:
    """
    :param name: The situation whose section to look up.
    :return: The section registered for that situation.
    :raises KeyError: If no section in :data:`PROMPT_SECTIONS` declares that name.
    """
    if name not in _SECTIONS_BY_NAME:
        raise KeyError(
            f"Section '{name}' not in PROMPT_SECTIONS. "
            f"Available: {list(_SECTIONS_BY_NAME)}"
        )
    return _SECTIONS_BY_NAME[name]


# %% Minimal helpers for building a RenderContext


def _make_palette():
    """
    Return a no-colour Palette from IPythonInterface so tests are ANSI-free.
    """
    return IPythonInterface(use_color=False).palette


def _conclusion_answer_request(rdr):
    """
    Build a standard AnswerName.CONCLUSION AnswerRequest for the zoo RDR domain.
    """
    domain = rdr.conclusion_domain
    return AnswerRequest(
        name=AnswerName.CONCLUSION,
        validate=ConclusionValidator(domain=domain, allow_unset=False),
        example=domain.example_for(AnswerName.CONCLUSION),
        default=...,
    )


def _conditions_answer_request(rdr):
    """
    Build a standard AnswerName.CONDITIONS (conditions) AnswerRequest.
    """
    return AnswerRequest(
        name=AnswerName.CONDITIONS,
        validate=ConditionsValidator(),
        example=f"{AnswerName.CONDITIONS} = case_variable.some_attr == True",
    )


def _no_target_no_current_context(case, rdr):
    """
    CaseContext: no target, no current conclusion (labelling, no rule fired).
    """
    return _no_rule_context(case, rdr)


def _no_target_with_current_context(case, rdr, current=None):
    """
    CaseContext: no target, current conclusion set.
    """
    if current is None:
        current = Species.fish
    return _current_conclusion_context(case, rdr, current)


def _with_target_no_current_context(case, rdr, target=None):
    """
    CaseContext: target set, no current conclusion (ground-truth, no rule fired).
    """
    if target is None:
        target = Species.bird
    return CaseContext(
        case_instance=case,
        case_variable=rdr.case_variable,
        current_conclusion=...,
        target_conclusion=target,
        conclusion_domain=rdr.conclusion_domain,
    )


def _with_target_and_current_context(case, rdr, target=None, current=None):
    """
    CaseContext: both target and current conclusion set (conflict scenario).
    """
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


def _make_render_context(case_context, requests, palette=None):
    """
    Build a RenderContext from a CaseContext and a list of AnswerRequests.
    """
    if palette is None:
        palette = _make_palette()
    return RenderContext(case=case_context, requests=requests, palette=palette)


# %% Group A — RenderContext property predicates


class TestRenderContextHasTarget(unittest.TestCase):
    """
    has_target delegates to the underlying CaseContext.target_conclusion sentinel check.
    """

    def test_has_target_is_false_when_no_target_supplied(self):
        """
        has_target returns False when target_conclusion is ....
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(render_context.has_target)

    def test_has_target_is_true_when_target_supplied(self):
        """
        has_target returns True when a concrete target_conclusion is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(render_context.has_target)


class TestRenderContextHasCurrentConclusion(unittest.TestCase):
    """
    has_current_conclusion delegates to the underlying CaseContext sentinel check.
    """

    def test_has_current_conclusion_is_false_when_no_rule_fired(self):
        """
        has_current_conclusion returns False when current_conclusion is ....
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(render_context.has_current_conclusion)

    def test_has_current_conclusion_is_true_when_rule_fired(self):
        """
        has_current_conclusion returns True when a concrete current_conclusion is set.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_with_current_context(case, rdr, Species.fish)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(render_context.has_current_conclusion)


class TestRenderContextIsConclusionRequest(unittest.TestCase):
    """
    is_conclusion_request is True iff any request.name == AnswerName.CONCLUSION.
    """

    def test_is_conclusion_request_true_when_conclusion_request_present(self):
        """
        is_conclusion_request is True when requests contains a AnswerName.CONCLUSION
        request.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(render_context.is_conclusion_request)

    def test_is_conclusion_request_false_when_only_conditions_request_present(self):
        """
        is_conclusion_request is False when only a conditions (AnswerName.CONDITIONS)
        request is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertFalse(render_context.is_conclusion_request)


class TestRenderContextIsConditionsRequest(unittest.TestCase):
    """
    is_conditions_request is True iff any request.name == AnswerName.CONDITIONS.
    """

    def test_is_conditions_request_true_when_conditions_request_present(self):
        """
        is_conditions_request is True when requests contains an AnswerName.CONDITIONS
        request.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(render_context.is_conditions_request)

    def test_is_conditions_request_false_when_only_conclusion_request_present(self):
        """
        is_conditions_request is False when only a conclusion (AnswerName.CONCLUSION)
        request is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(render_context.is_conditions_request)


# %% Group B — PromptSection.applicable: each section fires on the right context


class TestGroundTruthConclusionSectionApplicable(unittest.TestCase):
    """
    Section 'ground_truth_conclusion' is applicable iff has_target is True.
    """

    def test_applicable_when_target_is_set(self):
        """
        ground_truth_conclusion.applicable returns True when a target is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.GROUND_TRUTH_CONCLUSION).applicable(
                render_context
            )
        )

    def test_not_applicable_when_no_target(self):
        """
        ground_truth_conclusion.applicable returns False when no target is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.GROUND_TRUTH_CONCLUSION).applicable(
                render_context
            )
        )


class TestCurrentConclusionVsTargetSectionApplicable(unittest.TestCase):
    """
    Section 'current_conclusion_vs_target' is applicable iff has_target is True.
    """

    def test_applicable_when_target_is_set(self):
        """
        current_conclusion_vs_target.applicable returns True when target is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.CURRENT_CONCLUSION_VS_TARGET).applicable(
                render_context
            )
        )

    def test_not_applicable_when_no_target(self):
        """
        current_conclusion_vs_target.applicable returns False when no target.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.CURRENT_CONCLUSION_VS_TARGET).applicable(
                render_context
            )
        )


class TestNoRuleFiredKnownTargetSectionApplicable(unittest.TestCase):
    """
    Section 'no_rule_fired_known_target': applicable when has_target and NOT
    has_current.
    """

    def test_applicable_when_target_set_and_no_current(self):
        """
        no_rule_fired_known_target.applicable returns True when target set, no current.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.NO_RULE_FIRED_KNOWN_TARGET).applicable(
                render_context
            )
        )

    def test_not_applicable_when_no_target(self):
        """
        no_rule_fired_known_target.applicable returns False when no target.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.NO_RULE_FIRED_KNOWN_TARGET).applicable(
                render_context
            )
        )

    def test_not_applicable_when_target_set_and_current_set(self):
        """
        no_rule_fired_known_target.applicable returns False when both target and current
        are set.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.NO_RULE_FIRED_KNOWN_TARGET).applicable(
                render_context
            )
        )


class TestConflictResolutionSectionApplicable(unittest.TestCase):
    """
    Section 'conflict_resolution': applicable when has_target, has_current, current !=
    target.
    """

    def test_applicable_when_target_and_current_differ(self):
        """
        conflict_resolution.applicable returns True when target and current conclusions
        differ.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(
            case, rdr, target=Species.bird, current=Species.fish
        )
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.CONFLICT_RESOLUTION).applicable(render_context)
        )

    def test_not_applicable_when_no_target(self):
        """
        conflict_resolution.applicable returns False when no target is set.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_with_current_context(case, rdr, Species.fish)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.CONFLICT_RESOLUTION).applicable(render_context)
        )

    def test_not_applicable_when_current_equals_target(self):
        """
        conflict_resolution.applicable returns False when current == target (no
        conflict).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(
            case, rdr, target=Species.bird, current=Species.bird
        )
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.CONFLICT_RESOLUTION).applicable(render_context)
        )


class TestLabellingHasCurrentSectionApplicable(unittest.TestCase):
    """
    Section 'labelling_has_current': applicable when NOT has_target and has_current.
    """

    def test_applicable_when_no_target_and_current_set(self):
        """
        labelling_has_current.applicable returns True when no target, current set.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_with_current_context(case, rdr, Species.fish)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.LABELLING_HAS_CURRENT).applicable(render_context)
        )

    def test_not_applicable_when_target_set(self):
        """
        labelling_has_current.applicable returns False when a target is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.LABELLING_HAS_CURRENT).applicable(render_context)
        )

    def test_not_applicable_when_no_current(self):
        """
        labelling_has_current.applicable returns False when current is ....
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.LABELLING_HAS_CURRENT).applicable(render_context)
        )


class TestLabellingFiredAnchorSectionApplicable(unittest.TestCase):
    """
    Section 'labelling_fired_anchor': applicable when NOT has_target, has_current, and
    trace has firing_anchor.
    """

    def test_applicable_when_no_target_current_set_and_anchor_present(self):
        """
        labelling_fired_anchor.applicable is True when trace.firing_anchor is set.
        """
        case = _make_animal()
        rdr = _zoo_rdr()

        # Seed a rule so the trace carries a real firing_anchor.
        from krrood.entity_query_language.rdr.interface import FunctionInterface
        from krrood.entity_query_language.rdr.expert import Expert

        def _fish_answer(context, requests):
            """
            :param context: The case being labelled.
            :param requests: The answers asked for.
            :return: A condition over the case variable justifying the label.
            """
            return {AnswerName.CONDITIONS: context.case_variable.backbone == True}

        fish_expert = Expert(interface=FunctionInterface(answer_function=_fish_answer))
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

        case_context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=trace.conclusion,
            conclusion_domain=rdr.conclusion_domain,
            trace=trace,
        )
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.LABELLING_FIRED_ANCHOR).applicable(
                render_context
            )
        )

    def test_not_applicable_when_no_current(self):
        """
        labelling_fired_anchor.applicable returns False when current is ....
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.LABELLING_FIRED_ANCHOR).applicable(
                render_context
            )
        )

    def test_not_applicable_when_trace_has_no_anchor(self):
        """
        labelling_fired_anchor.applicable returns False when trace.firing_anchor is
        None.
        """
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
        case_context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=Species.fish,
            conclusion_domain=rdr.conclusion_domain,
            trace=trace,
        )
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.LABELLING_FIRED_ANCHOR).applicable(
                render_context
            )
        )


class TestLabellingNoRuleSectionApplicable(unittest.TestCase):
    """
    Section 'labelling_no_rule': applicable when NOT has_target and NOT has_current.
    """

    def test_applicable_when_no_target_and_no_current(self):
        """
        labelling_no_rule.applicable returns True when no target and no rule fired.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.LABELLING_NO_RULE).applicable(render_context)
        )

    def test_not_applicable_when_current_is_set(self):
        """
        labelling_no_rule.applicable returns False when a current conclusion exists.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_with_current_context(case, rdr, Species.fish)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.LABELLING_NO_RULE).applicable(render_context)
        )


class TestAllowedValuesSectionApplicable(unittest.TestCase):
    """
    Section 'allowed_values': applicable when NOT has_target and domain is not None.
    """

    def test_applicable_when_no_target_and_domain_present(self):
        """
        allowed_values.applicable returns True when no target and a domain is available.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.ALLOWED_VALUES).applicable(render_context)
        )

    def test_not_applicable_when_target_is_set(self):
        """
        allowed_values.applicable returns False when a target conclusion is present.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.ALLOWED_VALUES).applicable(render_context)
        )

    def test_not_applicable_when_domain_is_none(self):
        """
        allowed_values.applicable returns False when conclusion_domain is None.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=...,
            conclusion_domain=None,
        )
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertFalse(
            _section(PromptSectionName.ALLOWED_VALUES).applicable(render_context)
        )


class TestContextualExampleSectionApplicable(unittest.TestCase):
    """
    Section 'contextual_example': always applicable.
    """

    def test_applicable_for_no_target_no_current_context(self):
        """
        contextual_example.applicable returns True for the labelling/no-rule scenario.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.CONTEXTUAL_EXAMPLE).applicable(render_context)
        )

    def test_applicable_for_target_with_current_context(self):
        """
        contextual_example.applicable returns True for the conflict scenario.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.CONTEXTUAL_EXAMPLE).applicable(render_context)
        )


class TestHelpHintSectionApplicable(unittest.TestCase):
    """
    Section 'help_hint': always applicable.
    """

    def test_applicable_for_no_target_context(self):
        """
        help_hint.applicable returns True for a no-target context.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.HELP_HINT).applicable(render_context)
        )

    def test_applicable_for_target_context(self):
        """
        help_hint.applicable returns True for a has-target context.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertTrue(
            _section(PromptSectionName.HELP_HINT).applicable(render_context)
        )


# %% Group C — PromptSection.lines: each section emits the contractually required phrases


def _lines_of(section_name: str, render_context: RenderContext):
    """
    Return the concatenated lines produced by the named section as a single string.
    """
    return "\n".join(_section(section_name).lines(render_context))


class TestGroundTruthConclusionLines(unittest.TestCase):
    """
    Section 'ground_truth_conclusion' must include the target conclusion value.
    """

    def test_contains_ground_truth_label(self):
        """
        Lines contain 'Ground-truth conclusion:'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr, Species.bird)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "Ground-truth conclusion:",
            _lines_of(PromptSectionName.GROUND_TRUTH_CONCLUSION, render_context),
        )

    def test_contains_target_value_repr(self):
        """
        Lines contain a repr-like reference to the target conclusion value.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr, Species.bird)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "bird", _lines_of(PromptSectionName.GROUND_TRUTH_CONCLUSION, render_context)
        )


class TestCurrentConclusionVsTargetLines(unittest.TestCase):
    """
    Section 'current_conclusion_vs_target' must include the current-conclusion label.
    """

    def test_contains_current_conclusion_label(self):
        """
        Lines contain 'Current conclusion:'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "Current conclusion:",
            _lines_of(PromptSectionName.CURRENT_CONCLUSION_VS_TARGET, render_context),
        )

    def test_contains_current_value_repr(self):
        """
        Lines contain a repr-like reference to the current conclusion value.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(case, rdr, current=Species.fish)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "fish",
            _lines_of(PromptSectionName.CURRENT_CONCLUSION_VS_TARGET, render_context),
        )


class TestNoRuleFiredKnownTargetLines(unittest.TestCase):
    """
    Section 'no_rule_fired_known_target' must describe the no-rule-fired situation and
    prompt for a condition.
    """

    def test_contains_no_rule_fired_phrase(self):
        """
        Lines contain 'No rule fired'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "No rule fired",
            _lines_of(PromptSectionName.NO_RULE_FIRED_KNOWN_TARGET, render_context),
        )

    def test_contains_write_condition_phrase(self):
        """
        Lines contain 'condition' (prompt to write a condition that fires).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "condition",
            _lines_of(PromptSectionName.NO_RULE_FIRED_KNOWN_TARGET, render_context),
        )


class TestConflictResolutionLines(unittest.TestCase):
    """
    Section 'conflict_resolution' must describe the conflict and request an exceptional
    condition.
    """

    def test_contains_concluded_phrase(self):
        """
        Lines contain 'concluded' (the condition concluded the current value).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(
            case, rdr, target=Species.bird, current=Species.fish
        )
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "concluded",
            _lines_of(PromptSectionName.CONFLICT_RESOLUTION, render_context),
        )

    def test_contains_while_it_should_be_phrase(self):
        """
        Lines contain 'while it should be' (the expected target contrast).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(
            case, rdr, target=Species.bird, current=Species.fish
        )
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "while it should be",
            _lines_of(PromptSectionName.CONFLICT_RESOLUTION, render_context),
        )

    def test_contains_provide_a_condition_phrase(self):
        """
        Lines contain 'Provide a condition' (call to action).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_and_current_context(
            case, rdr, target=Species.bird, current=Species.fish
        )
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "Provide a condition",
            _lines_of(PromptSectionName.CONFLICT_RESOLUTION, render_context),
        )


class TestLabellingHasCurrentLines(unittest.TestCase):
    """
    Section 'labelling_has_current' must tell the expert the current conclusion and ask
    whether it is correct.
    """

    def test_contains_currently_concludes_phrase(self):
        """
        Lines contain 'currently concludes'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_with_current_context(case, rdr, Species.fish)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn(
            "currently concludes",
            _lines_of(PromptSectionName.LABELLING_HAS_CURRENT, render_context),
        )

    def test_contains_is_that_correct_phrase(self):
        """
        Lines contain 'is that correct'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_with_current_context(case, rdr, Species.fish)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn(
            "is that correct",
            _lines_of(PromptSectionName.LABELLING_HAS_CURRENT, render_context),
        )

    def test_contains_ctrl_d_phrase(self):
        """
        Lines contain 'CTRL+D' (shortcut for accepting the current conclusion).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_with_current_context(case, rdr, Species.fish)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn(
            "CTRL+D", _lines_of(PromptSectionName.LABELLING_HAS_CURRENT, render_context)
        )


class TestLabellingFiredAnchorLines(unittest.TestCase):
    """
    Section 'labelling_fired_anchor' must mention the anchor that fired.
    """

    def test_contains_fired_on_phrase(self):
        """
        Lines contain 'It fired on'.
        """
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
        case_context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=Species.fish,
            conclusion_domain=rdr.conclusion_domain,
            trace=trace,
        )
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn(
            "It fired on",
            _lines_of(PromptSectionName.LABELLING_FIRED_ANCHOR, render_context),
        )


class TestLabellingNoRuleLines(unittest.TestCase):
    """
    Section 'labelling_no_rule' must ask for a conclusion without a 'Set the'
    instruction.
    """

    def test_contains_no_rule_fired_phrase(self):
        """
        Lines contain 'No rule fired'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn(
            "No rule fired",
            _lines_of(PromptSectionName.LABELLING_NO_RULE, render_context),
        )

    def test_does_not_contain_set_the_phrase(self):
        """
        Lines do NOT contain 'Set the' (removed per Phase 2 wording change).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertNotIn(
            "Set the", _lines_of(PromptSectionName.LABELLING_NO_RULE, render_context)
        )


class TestAllowedValuesLines(unittest.TestCase):
    """
    Section 'allowed_values' must show enumerable members or the type name.
    """

    def test_enumerable_domain_contains_choose_one_of(self):
        """
        Lines contain 'Choose one of:' for an enumerable (Species) domain.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn(
            "Choose one of:",
            _lines_of(PromptSectionName.ALLOWED_VALUES, render_context),
        )

    def test_open_domain_contains_conclusion_type(self):
        """
        Lines contain 'Conclusion type:' for an open (str) domain.
        """
        from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
        from .test_conclusion_domain import Tag

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
        self.assertIn(
            "Conclusion type:",
            _lines_of(PromptSectionName.ALLOWED_VALUES, render_context),
        )


class TestHelpHintLines(unittest.TestCase):
    """
    Section 'help_hint' must always reference %help.
    """

    def test_contains_percent_help(self):
        """
        Lines contain '%help'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn("%help", _lines_of(PromptSectionName.HELP_HINT, render_context))


class TestContextualExampleLines(unittest.TestCase):
    """
    Section 'contextual_example' dispatches to %conclusion or %conditions depending on
    the request.
    """

    def test_lines_for_conclusion_request_contain_conclusion_magic(self):
        """
        Lines contain '%conclusion' when the request is a conclusion (no-target)
        request.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _no_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conclusion_answer_request(rdr)]
        )
        self.assertIn(
            "%conclusion",
            _lines_of(PromptSectionName.CONTEXTUAL_EXAMPLE, render_context),
        )

    def test_lines_for_conditions_request_contain_conditions_magic(self):
        """
        Lines contain '%conditions' when the request is a conditions (has-target)
        request.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        case_context = _with_target_no_current_context(case, rdr)
        render_context = _make_render_context(
            case_context, [_conditions_answer_request(rdr)]
        )
        self.assertIn(
            "%conditions",
            _lines_of(PromptSectionName.CONTEXTUAL_EXAMPLE, render_context),
        )


if __name__ == "__main__":
    unittest.main()
