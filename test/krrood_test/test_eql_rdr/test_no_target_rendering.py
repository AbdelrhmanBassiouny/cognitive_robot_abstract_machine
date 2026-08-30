"""
Tests for the no-ground-truth ("labelling") header rendering in IPythonInterface.

Each test verifies exactly one rendering guarantee of the labelling path:
  - _labelling_lines dispatched when has_target is False
  - no-rule-fired message
  - current-conclusion message with repr of the value
  - "It fired on <condition>" line only when trace.firing_anchor is set
  - enumerable vs. open domain display ("Choose one of:" vs. "Conclusion type:")
  - hint line: always %help, %helper only when helpers present
  - helper.present() output folded into header, and called only once per _build_namespace
  - namespace injection: Species injected for enumerable, not for open domain
  - NamespaceKey.HELPER_TEXT present iff helpers non-empty
  - ground-truth (has_target) path still shows "Ground-truth conclusion:"
  - _help_text includes domain-example and %helper only when helpers configured

Usage: workon cram2 && python -m pytest test/krrood_test/test_eql_rdr/test_no_target_rendering.py -q -p no:cacheprovider
"""

from __future__ import annotations

from krrood.entity_query_language.rdr.answer_vocabulary import (
    AnswerName,
)
import unittest
from dataclasses import dataclass


from krrood.entity_query_language.rdr.conclusion_helper import (
    ConclusionSupportPresenter,
)
from krrood.entity_query_language.rdr.conclusion_domain import (
    ConclusionValidator,
)
from krrood.entity_query_language.rdr.expert import ConditionsValidator, Expert
from krrood.entity_query_language.rdr.observer import ClassificationTrace
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.magics import MagicName, NamespaceKey
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR


from .animal import Animal, Species
from .test_conclusion_domain import Tag

# %% Helpers shared across tests


def _make_animal() -> Animal:
    """
    Construct a minimal Animal without loading the zoo dataset.
    """
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
    """
    Return a fresh (empty) RDR for the zoo domain.
    """
    return EQLSingleClassRDR(Animal, "species")


def ipython_interface() -> IPythonInterface:
    """
    Return a plain (no-color) IPythonInterface.
    """
    return IPythonInterface(use_color=False)


def _conclusion_request(domain):
    """
    Build the standard conclusion AnswerRequest for a domain.
    """
    return AnswerRequest(
        name=AnswerName.CONCLUSION,
        validate=ConclusionValidator(domain=domain, allow_unset=False),
        example=domain.example_for(AnswerName.CONCLUSION),
        default=...,
    )


def _no_rule_context(case, rdr, helpers=None):
    """
    CaseContext with no current conclusion and no target (labelling, no rule fired).
    """
    return CaseContext(
        case_instance=case,
        case_variable=rdr.case_variable,
        current_conclusion=...,
        conclusion_domain=rdr.conclusion_domain,
        helpers=helpers or [],
    )


def _current_conclusion_context(case, rdr, current, trace=None, helpers=None):
    """
    CaseContext with a current conclusion but no target (labelling, rule fired wrong).
    """
    return CaseContext(
        case_instance=case,
        case_variable=rdr.case_variable,
        current_conclusion=current,
        conclusion_domain=rdr.conclusion_domain,
        trace=trace,
        helpers=helpers or [],
    )


def _render(expert_interface, context, requests=None, errors=None):
    """
    Call _build_namespace then _render_header and return the header string.
    """
    if requests is None:
        requests = [_conclusion_request(context.conclusion_domain)]
    if errors is None:
        errors = {}
    expert_interface._build_namespace(context, requests)
    return expert_interface._render_header(context, requests, errors)


# %% no-rule-fired, no-target — labelling intro lines


class TestNoRuleFiredNoTargetHeader(unittest.TestCase):
    """
    The header shown when nothing fired and no ground truth is known.
    """

    def test_no_rule_fired_message_present(self):
        """
        Header contains 'No rule fired — what should this case conclude?' when no rule
        fired.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(ipython_interface(), _no_rule_context(case, rdr))
        self.assertIn("No rule fired", header)
        self.assertIn("what should this case conclude", header)

    def test_choose_one_of_lists_species_members(self):
        """
        Header contains 'Choose one of:' and lists Species members for enumerable
        domain.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(ipython_interface(), _no_rule_context(case, rdr))
        self.assertIn("Choose one of:", header)
        self.assertIn("Species.mammal", header)
        self.assertIn("Species.molusc", header)

    def test_no_set_the_line_in_no_conclusion_path(self):
        """
        Header does NOT contain 'Set the' in the no-rule-fired, no-target path.

        When only a conclusion is being requested the UI must not tell the expert to
        also justify it with a condition (that comes in a separate interaction).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(ipython_interface(), _no_rule_context(case, rdr))
        self.assertNotIn("Set the", header)


# %% current-conclusion-set, no-target


class TestCurrentConclusionNoTargetHeader(unittest.TestCase):
    """
    The header shown when a conclusion already stands and is up for confirmation.
    """

    def test_currently_concludes_phrase_present(self):
        """
        Header contains 'currently concludes' when a rule has fired.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(case, rdr, Species.fish)
        header = _render(ipython_interface(), context)
        self.assertIn("currently concludes", header)

    def test_current_conclusion_repr_present(self):
        """
        Header contains repr(current_conclusion) in the 'currently concludes' line.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(case, rdr, Species.fish)
        header = _render(ipython_interface(), context)
        self.assertIn(repr(Species.fish), header)

    def test_is_that_correct_phrase_present(self):
        """
        Header contains 'is that correct' and 'CTRL+D' when a rule has fired and no
        target.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(case, rdr, Species.fish)
        header = _render(ipython_interface(), context)
        self.assertIn("is that correct", header)
        self.assertIn("CTRL+D", header)


# %% "It fired on <condition>" line — with and without trace


class TestFiredOnLineWithTrace(unittest.TestCase):
    """
    The line naming the condition the standing conclusion came from.
    """

    def test_fired_on_line_absent_when_trace_is_none(self):
        """
        'It fired on' line is absent when trace is None (no trace supplied).
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _current_conclusion_context(
            case, rdr, current=Species.fish, trace=None
        )
        header = _render(ipython_interface(), context)
        self.assertNotIn("It fired on", header)

    def test_fired_on_line_present_when_trace_has_anchor(self):
        """
        'It fired on' line is present when trace.firing_anchor is set.
        """
        case = _make_animal()
        rdr = _zoo_rdr()

        # Seed a backbone→fish rule so we get a real trace with a firing anchor.
        def _answer_with_fish(context, requests):
            """
            :param context: The case being labelled.
            :param requests: The answers asked for.
            :return: A condition justifying the label, built over the case variable.
            """
            return {"conditions": context.case_variable.backbone == True}

        fish_expert = Expert(
            interface=FunctionInterface(answer_function=_answer_with_fish)
        )
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
        header = _render(ipython_interface(), context)
        self.assertIn("It fired on", header)

    def test_fired_on_line_absent_when_firing_anchor_is_none(self):
        """
        'It fired on' line is absent when trace is present but firing_anchor is None.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        # Build a synthetic trace with firing_anchor=None.
        trace = ClassificationTrace(
            rule_tree_root=None,
            satisfied_condition_ids=None,
            evaluated_expression_ids=None,
            firing_anchor=None,
            conclusion=...,
        )
        context = _current_conclusion_context(
            case, rdr, current=Species.fish, trace=trace
        )
        header = _render(ipython_interface(), context)
        self.assertNotIn("It fired on", header)


# %% enumerable vs. open-type domain display


class TestAllowedValuesLines(unittest.TestCase):
    """
    What the header says the conclusion may be, per kind of domain.
    """

    def test_enumerable_domain_shows_choose_one_of(self):
        """
        Enumerable domain (Species) → header contains 'Choose one of:'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(ipython_interface(), _no_rule_context(case, rdr))
        self.assertIn("Choose one of:", header)

    def test_enumerable_domain_lists_all_members(self):
        """
        Enumerable domain → header lists every Species member.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(ipython_interface(), _no_rule_context(case, rdr))
        for member in Species:
            self.assertIn(repr(member), header)

    def test_open_domain_shows_conclusion_type(self):
        """
        Open-type domain (Tag.name: str) → header contains 'Conclusion type: str'.
        """

        @dataclass
        class StrCase:
            """
            A case whose conclusion attribute is an open string, not an enum.
            """

            label: str = ""
            """
            The case's only field, unrelated to the conclusion under test.
            """

        rdr_str = EQLSingleClassRDR(Tag, "name")
        domain = rdr_str.conclusion_domain
        context = CaseContext(
            case_instance=Tag(name="hello"),
            case_variable=rdr_str.case_variable,
            current_conclusion=...,
            conclusion_domain=domain,
        )
        request = _conclusion_request(domain)
        interface = ipython_interface()
        interface._build_namespace(context, [request])
        header = interface._render_header(context, [request], {})
        self.assertIn("Conclusion type:", header)
        self.assertIn("str", header)

    def test_open_domain_does_not_show_choose_one_of(self):
        """
        Open-type domain (str) → header does NOT contain 'Choose one of:'.
        """
        rdr_str = EQLSingleClassRDR(Tag, "name")
        domain = rdr_str.conclusion_domain
        context = CaseContext(
            case_instance=Tag(name="hello"),
            case_variable=rdr_str.case_variable,
            current_conclusion=...,
            conclusion_domain=domain,
        )
        request = _conclusion_request(domain)
        interface = ipython_interface()
        interface._build_namespace(context, [request])
        header = interface._render_header(context, [request], {})
        self.assertNotIn("Choose one of:", header)


# %% hint line always contains %help


class TestHintLineAlwaysContainsHelp(unittest.TestCase):
    """
    The help magic is offered on every prompt.
    """

    def test_hint_contains_percent_help(self):
        """
        Hint line always contains '%help'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        header = _render(ipython_interface(), _no_rule_context(case, rdr))
        self.assertIn(f"%{MagicName.HELP}", header)


# %% %helper appears in hint only when helpers are present


class TestHintLineNamesTheHelperMagicOnlyWithAHelper(unittest.TestCase):
    """
    The helper magic is offered only when a helper has material to show.
    """

    def test_hint_contains_percent_aid_when_aids_present(self):
        """
        Hint line contains '%helper' when context.helpers is non-empty.
        """

        class PresentingHelper(ConclusionSupportPresenter):
            """
            A helper with something to show.
            """

            def present(self, context):
                """:return: Fixed supporting material."""
                return "SUPPORTING-MATERIAL"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[PresentingHelper()])
        header = _render(ipython_interface(), context)
        self.assertIn(f"%{MagicName.HELPER}", header)

    def test_hint_does_not_contain_percent_aid_when_no_aids(self):
        """
        Hint line does NOT contain '%helper' when context.helpers is empty.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[])
        header = _render(ipython_interface(), context)
        self.assertNotIn(f"%{MagicName.HELPER}", header)


# %% helper present() output folded into header, called exactly once


class TestSupportingMaterialFoldedIntoTheHeader(unittest.TestCase):
    """
    A helper's material appears in the header, and is produced once per question.
    """

    def test_aid_present_output_appears_in_header(self):
        """
        Aid present() text is included in the rendered header.
        """

        class PresentingHelper(ConclusionSupportPresenter):
            """
            A helper whose material is a recognisable literal.
            """

            def present(self, context):
                """:return: Fixed supporting material."""
                return "PIXELS-HERE"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[PresentingHelper()])
        header = _render(ipython_interface(), context)
        self.assertIn("PIXELS-HERE", header)

    def test_aid_present_called_once_regardless_of_render_calls(self):
        """
        helper.present() is called exactly once per _build_namespace, not per
        _render_header.
        """
        call_count = {"n": 0}

        class CountingHelper(ConclusionSupportPresenter):
            """
            A helper that counts how often it was asked to present.
            """

            def present(self, context):
                """:return: Fixed material, having recorded the call."""
                call_count["n"] += 1
                return "COUNTED"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[CountingHelper()])
        requests = [_conclusion_request(context.conclusion_domain)]
        interface = ipython_interface()
        # _build_namespace triggers present(); subsequent _render_header calls reuse cache.
        interface._build_namespace(context, requests)
        interface._render_header(context, requests, {})
        interface._render_header(context, requests, {})
        interface._render_header(context, requests, {})
        self.assertEqual(call_count["n"], 1)


# %% namespace injection of Enum type for enumerable domain


class TestNamespaceInjection(unittest.TestCase):
    """
    The conclusion domain's own names are in scope, so the expert can type them.
    """

    def test_species_injected_for_enumerable_domain(self):
        """
        _build_namespace injects 'Species' key bound to the Species enum for zoo domain.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(context.conclusion_domain)]
        interface = ipython_interface()
        namespace = interface._build_namespace(context, requests)
        self.assertIn("Species", namespace)
        self.assertIs(namespace["Species"], Species)

    def test_enum_type_not_injected_for_open_domain(self):
        """
        An open-type (str) domain contributes no tab-completion bindings of its own.

        (We assert on ``namespace_bindings()`` rather than scanning the built namespace,
        because the captured caller scope legitimately contains any enums the test
        module imported — e.g. ``Species`` — independent of the domain injection under
        test.)
        """
        rdr_str = EQLSingleClassRDR(Tag, "name")
        domain = rdr_str.conclusion_domain
        self.assertFalse(domain.is_enumerable)
        self.assertEqual(domain.namespace_bindings(), {})


# %% NamespaceKey.HELPER_TEXT in namespace iff helpers non-empty


class TestHelperRendererInTheNamespace(unittest.TestCase):
    """
    The helper magic's renderer is bound only when a helper has material.
    """

    def test_aid_text_key_present_when_aids_non_empty(self):
        """
        NamespaceKey.HELPER_TEXT is in the namespace when context.helpers is non-empty.
        """

        class PresentingHelper(ConclusionSupportPresenter):
            """
            A helper with something to show.
            """

            def present(self, context):
                """:return: Fixed supporting material."""
                return "MATERIAL"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[PresentingHelper()])
        requests = [_conclusion_request(context.conclusion_domain)]
        interface = ipython_interface()
        namespace = interface._build_namespace(context, requests)
        self.assertIn(NamespaceKey.HELPER_TEXT, namespace)

    def test_aid_text_key_absent_when_no_aids(self):
        """
        NamespaceKey.HELPER_TEXT is NOT in the namespace when context.helpers is empty.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[])
        requests = [_conclusion_request(context.conclusion_domain)]
        interface = ipython_interface()
        namespace = interface._build_namespace(context, requests)
        self.assertNotIn(NamespaceKey.HELPER_TEXT, namespace)


# %% ground-truth (has_target) path is unchanged


class TestGroundTruthPathUnchanged(unittest.TestCase):
    """
    The known-target path renders as it did before labelling was added.
    """

    def test_ground_truth_header_contains_ground_truth_conclusion_label(self):
        """
        has_target=True → header contains 'Ground-truth conclusion:'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=...,
            target_conclusion=Species.bird,
            conclusion_domain=rdr.conclusion_domain,
        )
        request = AnswerRequest(
            name=AnswerName.CONDITIONS,
            validate=ConditionsValidator(),
            example=f"{AnswerName.CONDITIONS} = case_variable.some_attr == True",
        )
        interface = ipython_interface()
        interface._build_namespace(context, [request])
        header = interface._render_header(context, [request], {})
        self.assertIn("Ground-truth conclusion:", header)

    def test_ground_truth_header_contains_target_value(self):
        """
        has_target=True → header contains repr of the target conclusion value.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=...,
            target_conclusion=Species.bird,
            conclusion_domain=rdr.conclusion_domain,
        )
        request = AnswerRequest(
            name=AnswerName.CONDITIONS,
            validate=ConditionsValidator(),
            example="conditions = case_variable.some_attr == True",
        )
        interface = ipython_interface()
        interface._build_namespace(context, [request])
        header = interface._render_header(context, [request], {})
        self.assertIn("bird", header)

    def test_ground_truth_header_does_not_contain_no_rule_fired(self):
        """
        has_target=True → header does NOT contain the labelling 'No rule fired' message.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = CaseContext(
            case_instance=case,
            case_variable=rdr.case_variable,
            current_conclusion=...,
            target_conclusion=Species.bird,
            conclusion_domain=rdr.conclusion_domain,
        )
        request = AnswerRequest(
            name=AnswerName.CONDITIONS,
            validate=ConditionsValidator(),
            example="conditions = case_variable.some_attr == True",
        )
        interface = ipython_interface()
        interface._build_namespace(context, [request])
        header = interface._render_header(context, [request], {})
        self.assertNotIn("No rule fired — what should this case conclude?", header)


# %% _help_text includes domain example and %helper iff helpers configured


class TestHelpText(unittest.TestCase):
    """
    What the help magic prints for the question currently being asked.
    """

    def test_help_text_includes_domain_example(self):
        """
        _help_text includes a domain-sourced example for the conclusion assignment.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        domain = rdr.conclusion_domain
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(domain)]
        interface = ipython_interface()
        text = interface._help_text(context, requests)
        # The example is derived from the domain (e.g. "conclusion = Species.<member>")
        self.assertIn("conclusion = Species.", text)

    def test_help_text_includes_percent_aid_when_aids_present(self):
        """
        _help_text includes a '%helper' line when helpers are configured.
        """

        class PresentingHelper(ConclusionSupportPresenter):
            """
            A helper with something to show.
            """

            def present(self, context):
                """:return: Fixed supporting material."""
                return "MATERIAL"

        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[PresentingHelper()])
        requests = [_conclusion_request(rdr.conclusion_domain)]
        interface = ipython_interface()
        text = interface._help_text(context, requests)
        self.assertIn(f"%{MagicName.HELPER}", text)

    def test_help_text_excludes_percent_aid_when_no_aids(self):
        """
        _help_text does NOT include '%helper' when no helpers are configured.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr, helpers=[])
        requests = [_conclusion_request(rdr.conclusion_domain)]
        interface = ipython_interface()
        text = interface._help_text(context, requests)
        self.assertNotIn(f"%{MagicName.HELPER}", text)

    def test_help_text_always_includes_percent_show_tree(self):
        """
        _help_text always includes '%show_tree'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(rdr.conclusion_domain)]
        interface = ipython_interface()
        text = interface._help_text(context, requests)
        self.assertIn("%show_tree", text)

    def test_help_text_always_includes_percent_help(self):
        """
        _help_text always includes '%help'.
        """
        case = _make_animal()
        rdr = _zoo_rdr()
        context = _no_rule_context(case, rdr)
        requests = [_conclusion_request(rdr.conclusion_domain)]
        interface = ipython_interface()
        text = interface._help_text(context, requests)
        self.assertIn(f"%{MagicName.HELP}", text)


if __name__ == "__main__":
    unittest.main()
