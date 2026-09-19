"""
Tests for the interactive expert: ``Expert`` (policy) over ``IPythonInterface``
(mechanism).

The real interface opens an embedded IPython shell; here we inject a stub
``shell_runner`` that plays the expert's part — building a live EQL condition expression
from the namespace the expert is given. This exercises namespace construction, scope
capture, the live-object answer contract, the validate/re-prompt loop, abort handling,
and integration with fit_case.
"""

from krrood.entity_query_language.rdr.answer_vocabulary import (
    AnswerName,
    NamespaceName,
)
import contextlib
import dataclasses
import io
import unittest

from typing_extensions import Any, Dict, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.backward_inference import (
    ConclusionSufficientConditionSets,
)
from krrood.entity_query_language.rdr.expert import (
    Expert,
    NoConditionsProvided,
)
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.progress import (
    IPythonProgressBar,
    NullProgressReporter,
    SpyProgressReporter,
)
from krrood.entity_query_language.rdr.magics import (
    NamespaceKey,
    SufficientConditionsMagic,
)

from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.interface import CaseContext, FunctionInterface

from .animal import Animal, Species
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()

FEATURE_FIELDS = [
    field.name
    for field in dataclasses.fields(Animal)
    if field.name not in ("name", "species")
]

USER_SCOPE_SENTINEL = "interactive_sentinel"


def first(species: Species) -> Animal:
    """
    :param species: The species to find a case for.
    :return: The first zoo animal whose target species is ``species``.
    """
    return next(animal for animal, target in zip(animals, targets) if target is species)


def maximally_specific_runner(captured=None):
    """
    A stub shell runner that assigns a full-feature-vector condition.

    Builds the condition with the EQL ``and_`` taken *from the namespace* (proving the
    factories were injected) over the case variable, matching the case's features.
    """

    def run(namespace, header):
        """
        Answer with a condition matching every feature of the case.
        """
        if captured is not None:
            captured["namespace"] = namespace
            captured["header"] = header
        case = namespace[NamespaceName.CASE_INSTANCE]
        case_variable = namespace[NamespaceName.CASE_VARIABLE]
        and_ = namespace["and_"]
        namespace[AnswerName.CONDITIONS] = and_(
            *[
                getattr(case_variable, feature) == getattr(case, feature)
                for feature in FEATURE_FIELDS
            ]
        )

    return run


@dataclasses.dataclass
class RecordingShellRunner:
    """
    Stands in for the expert's shell: records what the interface showed it, then answers
    with one fixed condition so the interaction completes.

    A test asserts on what was recorded rather than on a shell it would otherwise have
    to drive.
    """

    header: Optional[str] = None
    """
    The header text the interface rendered on the most recent call.
    """

    namespace: Optional[Dict[str, Any]] = None
    """
    The namespace the interface built on the most recent call.
    """

    def __call__(self, namespace: Dict[str, Any], header: str) -> None:
        """
        :param namespace: The interaction namespace to answer in.
        :param header: The header text the expert would have been shown.
        """
        self.namespace = namespace
        self.header = header
        namespace[AnswerName.CONDITIONS] = (
            namespace[NamespaceName.CASE_VARIABLE].milk == True
        )


def conditions_context(
    case,
    case_variable,
    target_conclusion=...,
    current_conclusion=...,
    **overrides,
) -> CaseContext:
    """
    Build the :class:`CaseContext` an ``ask_for_conditions`` call is driven by.

    :param case: The concrete case being labelled.
    :param case_variable: The shared EQL variable conditions are built over.
    :param target_conclusion: The known correct conclusion, or ``...`` when unknown.
    :param current_conclusion: What the rule tree concludes today, or ``...`` when
        nothing fired.
    :param overrides: Any further :class:`CaseContext` field to set.
    :return: The assembled context.
    """
    return CaseContext(
        case_instance=case,
        case_variable=case_variable,
        target_conclusion=target_conclusion,
        current_conclusion=current_conclusion,
        **overrides,
    )


def expert_with(runner) -> Expert:
    """
    :param runner: The stub shell runner that plays the expert's part.
    :return: An expert whose interface drives that runner instead of a real shell.
    """
    return Expert(interface=IPythonInterface(shell_runner=runner))


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestInteractiveExpert(unittest.TestCase):
    """
    The expert policy over the IPython interface, driven by a stub shell runner in place
    of a real terminal.
    """

    def test_namespace_has_factories_case_instance_and_variable(self):
        """
        The expert authors over the shared variable, with the EQL factories in scope.
        """
        captured = {}
        expert = expert_with(maximally_specific_runner(captured))
        rdr = EQLSingleClassRDR(Animal, "species")
        case = first(Species.mammal)
        expert.ask_for_conditions(
            conditions_context(case, rdr.case_variable, Species.mammal)
        )

        namespace = captured["namespace"]
        for verb in ("entity", "variable", "and_", "refinement", "alternative", "add"):
            self.assertIn(verb, namespace)
        self.assertIn(NamespaceName.CASE_VARIABLE, namespace)
        self.assertIs(namespace[NamespaceName.CASE_VARIABLE], rdr.case_variable)
        self.assertIs(namespace[NamespaceName.CASE_INSTANCE], case)

    def test_header_mentions_case_target(self):
        """
        The header names the conclusion the case is known to deserve.
        """
        captured = {}
        expert = expert_with(maximally_specific_runner(captured))
        rdr = EQLSingleClassRDR(Animal, "species")
        expert.ask_for_conditions(
            conditions_context(
                first(Species.bird), rdr.case_variable, Species.bird, Species.mammal
            )
        )
        header = captured["header"]
        self.assertIn("bird", header.lower())

    def test_returns_live_eql_expression(self):
        """
        The answer comes back as a live EQL expression, never as its text.
        """
        expert = expert_with(maximally_specific_runner())
        rdr = EQLSingleClassRDR(Animal, "species")
        condition = expert.ask_for_conditions(
            conditions_context(first(Species.mammal), rdr.case_variable, Species.mammal)
        )
        self.assertIsInstance(condition, SymbolicExpression)
        self.assertNotIsInstance(condition, str)

    def test_abort_raises_no_conditions(self):
        """
        Leaving the shell without answering is reported as a missing answer.
        """

        def run_and_abort(namespace, header):
            """
            Leave without answering.
            """
            namespace["exit"]()  # expert gives up without answering

        expert = expert_with(run_and_abort)
        rdr = EQLSingleClassRDR(Animal, "species")
        with self.assertRaises(NoConditionsProvided):
            expert.ask_for_conditions(
                conditions_context(
                    first(Species.mammal), rdr.case_variable, Species.mammal
                )
            )

    def test_invalid_answer_is_reprompted_then_accepted(self):
        """
        An invalid answer re-opens the shell with the error, and the retry is taken.
        """
        # The first attempt builds the condition over the *concrete* case, which is a
        # plain bool rather than an expression.
        calls = {"n": 0}

        def run(namespace, header):
            """
            Answer with a plain bool first, then with a real EQL expression.
            """
            calls["n"] += 1
            case = namespace[NamespaceName.CASE_INSTANCE]
            case_variable = namespace[NamespaceName.CASE_VARIABLE]
            if calls["n"] == 1:
                namespace[AnswerName.CONDITIONS] = (
                    case.milk == True
                )  # plain bool — rejected
            else:
                self.assertIn("[error]", header)  # error surfaced on re-prompt
                namespace[AnswerName.CONDITIONS] = case_variable.milk == True

        expert = expert_with(run)
        rdr = EQLSingleClassRDR(Animal, "species")
        condition = expert.ask_for_conditions(
            conditions_context(first(Species.mammal), rdr.case_variable, Species.mammal)
        )
        self.assertEqual(calls["n"], 2)
        self.assertIsInstance(condition, SymbolicExpression)

    def test_captures_user_definition_scope(self):
        """
        The caller's own names are in scope, so the expert can refer to them.
        """
        interactive_sentinel = USER_SCOPE_SENTINEL  # noqa: F841
        rdr = EQLSingleClassRDR(Animal, "species")
        captured = {}
        expert = expert_with(maximally_specific_runner(captured))
        expert.ask_for_conditions(
            conditions_context(first(Species.mammal), rdr.case_variable, Species.mammal)
        )
        self.assertEqual(
            captured["namespace"].get("interactive_sentinel"), USER_SCOPE_SENTINEL
        )

    def test_fit_through_interactive_expert(self):
        """
        A tree fitted through the shell classifies every case it was fitted on.
        """
        expert = expert_with(maximally_specific_runner())
        rdr = EQLSingleClassRDR(Animal, "species")
        subset = list(zip(animals, targets))[:15]
        for case, target in subset:
            rdr.fit_case(case, target, expert)
        for case, target in subset:
            self.assertEqual(rdr.classify(case), target, case.name)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestSufficientConditionsMagic(unittest.TestCase):
    """
    Tests for the ``%sufficient_conditions_for`` backward-inference magic.
    """

    def test_sufficient_conditions_key_in_namespace_when_rdr_set(self):
        """
        The RDR reference appears in the namespace under the sufficient-conditions key.
        """
        runner = RecordingShellRunner()
        rdr = EQLSingleClassRDR(Animal, "species")
        interface = IPythonInterface(shell_runner=runner, rdr=rdr)
        expert = Expert(interface=interface)
        expert.ask_for_conditions(
            conditions_context(first(Species.mammal), rdr.case_variable, Species.mammal)
        )
        self.assertIs(runner.namespace.get(NamespaceKey.SUFFICIENT_CONDITIONS), rdr)

    def test_sufficient_conditions_key_absent_when_no_rdr(self):
        """
        Without ``rdr`` set, the sufficient-conditions key is not in the namespace.
        """
        runner = RecordingShellRunner()
        rdr = EQLSingleClassRDR(Animal, "species")
        interface = IPythonInterface(shell_runner=runner)
        expert = Expert(interface=interface)
        expert.ask_for_conditions(
            conditions_context(first(Species.mammal), rdr.case_variable, Species.mammal)
        )
        self.assertIsNone(runner.namespace.get(NamespaceKey.SUFFICIENT_CONDITIONS))

    def test_sufficient_conditions_query_the_rdr_directly(self):
        """
        get_conclusion_sufficient_conditions_from_a_rule_tree returns correct results
        after fitting through interactive.
        """
        rdr = EQLSingleClassRDR(Animal, "species")

        def runner(namespace, header):
            """
            Answer every question with a milk condition.
            """
            case_variable = namespace[NamespaceName.CASE_VARIABLE]
            namespace[AnswerName.CONDITIONS] = case_variable.milk == True

        interface = IPythonInterface(shell_runner=runner, rdr=rdr)
        expert = Expert(interface=interface)
        rdr.fit_case(first(Species.mammal), Species.mammal, expert)

        sufficient_conditions = rdr.sufficient_conditions_for(Species.mammal)
        self.assertIsInstance(sufficient_conditions, ConclusionSufficientConditionSets)
        self.assertTrue(sufficient_conditions.is_satisfiable())
        self.assertEqual(len(sufficient_conditions.sufficient_condition_sets), 1)

    def test_empty_rdr_has_no_sufficient_conditions(self):
        """
        Empty RDR returns no paths for any value.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        sufficient_conditions = rdr.sufficient_conditions_for(Species.molusc)
        self.assertIsInstance(sufficient_conditions, ConclusionSufficientConditionSets)
        self.assertFalse(sufficient_conditions.is_satisfiable())

    def test_magic_evaluates_its_argument_in_the_namespace(self):
        """
        The magic evaluates its argument and queries the RDR.
        """
        rdr = EQLSingleClassRDR(Animal, "species")

        def runner(namespace, header):
            """
            Answer every question with a milk condition.
            """
            case_variable = namespace[NamespaceName.CASE_VARIABLE]
            namespace[AnswerName.CONDITIONS] = case_variable.milk == True

        interface = IPythonInterface(shell_runner=runner, rdr=rdr)
        expert = Expert(interface=interface)
        rdr.fit_case(first(Species.mammal), Species.mammal, expert)

        # Build a namespace as the shell would see it
        namespace = {NamespaceKey.SUFFICIENT_CONDITIONS: rdr, "Species": Species}
        magic = SufficientConditionsMagic(
            palette=IPythonInterface().palette, namespace=namespace
        )

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            magic.run("Species.mammal")

        output = printed.getvalue()
        self.assertIn("mammal", output.lower())
        self.assertIn("milk", output.lower())

    def test_magic_rejects_an_argument_it_cannot_evaluate(self):
        """
        Invalid magic argument prints an error.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        namespace = {NamespaceKey.SUFFICIENT_CONDITIONS: rdr}
        magic = SufficientConditionsMagic(
            palette=IPythonInterface().palette, namespace=namespace
        )

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            magic.run("Species.NonExistentValue")

        output = printed.getvalue()
        self.assertIn("error", output.lower())

    def test_magic_prints_usage_for_an_empty_line(self):
        """
        Empty magic line prints usage hint.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        namespace = {NamespaceKey.SUFFICIENT_CONDITIONS: rdr}
        magic = SufficientConditionsMagic(
            palette=IPythonInterface().palette, namespace=namespace
        )

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            magic.run("")

        output = printed.getvalue()
        self.assertIn("usage", output.lower())


def _make_animal(
    name: str,
    *,
    milk: bool = False,
    feathers: bool = False,
    fins: bool = False,
    backbone: bool = True,
    venomous: bool = False,
) -> Animal:
    """
    Return a minimal animal with one discriminating feature set.
    """
    return Animal(
        name=name,
        hair=milk,
        feathers=feathers,
        eggs=not milk,
        milk=milk,
        airborne=False,
        aquatic=fins,
        predator=False,
        toothed=backbone,
        backbone=backbone,
        breathes=not fins,
        venomous=venomous,
        fins=fins,
        legs=0 if fins else 4,
        tail=backbone,
        domestic=False,
        catsize=milk,
    )


def _scripted_function_expert(rules: dict) -> Expert:
    """
    A ``FunctionInterface``-backed expert that records every ``CaseContext`` it sees.
    """
    recorded: list = []

    def answer(context, requests):
        """
        Record the context, then answer from the scripted rule for its target.
        """
        recorded.append(context)
        return {"conditions": rules[context.target_conclusion](context.case_variable)}

    expert = Expert(interface=FunctionInterface(answer_function=answer))
    expert.recorded_contexts = recorded  # type: ignore[attr-defined]
    return expert


class TestCaseContextCornerCase(unittest.TestCase):
    """
    Tests for ``CaseContext.corner_case`` field and ``fit_case`` provenance wiring.
    """

    def test_case_context_has_corner_case_field(self):
        """
        ``CaseContext`` exposes a ``corner_case`` attribute that defaults to ``None``.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        case = _make_animal("mammal", milk=True)
        ctx = CaseContext(case_instance=case, case_variable=rdr.case_variable)
        self.assertIsNone(ctx.corner_case)

    def test_fit_case_first_rule_corner_case_is_none(self):
        """
        When the very first rule is fitted (empty RDR, no prior firing) the
        ``CaseContext`` passed to the expert has ``corner_case == None``.

        No firing anchor exists for the first case, so there is no corner case to show.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = _make_animal("mammal", milk=True)
        expert = _scripted_function_expert({Species.mammal: lambda v: v.milk == True})

        rdr.fit_case(mammal, Species.mammal, expert)

        self.assertEqual(len(expert.recorded_contexts), 1)
        ctx = expert.recorded_contexts[0]
        self.assertIsNone(ctx.corner_case)

    def test_fit_case_refinement_populates_corner_case_in_context(self):
        """
        When a second case triggers a refinement (wrong rule fired) the ``CaseContext``
        passed to the expert for that second case has ``corner_case`` equal to the first
        case's Animal instance — i.e., the corner case of the firing rule.

        This is the core Phase 4 contract: the expert can see *why the original rule
        exists* by inspecting the corner case shown alongside the new case.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = _make_animal("mammal", milk=True)
        # fish has backbone=False so the mammal rule (milk==True) does NOT fire for it;
        # use an over-general first rule that WILL misfire for the second case.
        # Strategy: first rule is "backbone == True" -> mammal; second case is also
        # backbone==True but should be classified as bird (feathers==True).
        backbone_animal = _make_animal("backbone_mammal", milk=True, backbone=True)
        feathered_backbone = Animal(
            name="owl",
            hair=False,
            feathers=True,
            eggs=True,
            milk=False,
            airborne=True,
            aquatic=False,
            predator=True,
            toothed=False,
            backbone=True,
            breathes=True,
            venomous=False,
            fins=False,
            legs=2,
            tail=False,
            domestic=False,
            catsize=False,
        )

        expert = _scripted_function_expert(
            {
                Species.mammal: lambda v: v.backbone == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )

        # First fit: backbone rule -> mammal (no prior firing; corner_case must be None).
        rdr.fit_case(backbone_animal, Species.mammal, expert)
        self.assertIsNone(expert.recorded_contexts[0].corner_case)

        # Second fit: feathered bird with backbone fires the mammal rule (wrong).
        # The refinement expert call must see corner_case == backbone_animal.
        rdr.fit_case(feathered_backbone, Species.bird, expert)

        self.assertEqual(len(expert.recorded_contexts), 2)
        ctx_refinement = expert.recorded_contexts[1]
        self.assertIs(ctx_refinement.corner_case, backbone_animal)

    def test_fit_case_alternative_corner_case_is_none(self):
        """
        When a second case does NOT fire any existing rule (alternative path) the
        ``CaseContext`` for that second case has ``corner_case == None``.

        No rule fired means no firing anchor, so no corner case to display.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = _make_animal("mammal", milk=True)
        # fish: no backbone, no milk, no feathers — will not fire the mammal rule.
        fish = _make_animal("fish", fins=True, backbone=False)

        expert = _scripted_function_expert(
            {
                Species.mammal: lambda v: v.milk == True,
                Species.fish: lambda v: v.fins == True,
            }
        )

        rdr.fit_case(mammal, Species.mammal, expert)
        rdr.fit_case(fish, Species.fish, expert)

        self.assertEqual(len(expert.recorded_contexts), 2)
        ctx_alternative = expert.recorded_contexts[1]
        self.assertIsNone(ctx_alternative.corner_case)


# %% the shell's progress bar as the interactive default


class TestProgressReporterInstalledOnAttachedRDR(unittest.TestCase):
    """
    The interactive layer supplies the progress reporter the engine cannot: the engine
    knows nothing about its caller and so keeps the null default, while this layer knows
    there is a shell to draw the bar into.
    """

    def test_attached_rdr_gets_the_shell_progress_bar(self):
        """
        An RDR handed to the interface trades the null default for a bar.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        self.assertIsInstance(rdr.progress_reporter, NullProgressReporter)

        IPythonInterface(rdr=rdr)

        self.assertIsInstance(rdr.progress_reporter, IPythonProgressBar)

    def test_the_bar_matches_the_shell_colour_setting(self):
        """
        The bar is built with the interface's own ``use_color``.
        """
        rdr = EQLSingleClassRDR(Animal, "species")

        IPythonInterface(rdr=rdr, use_color=False)

        self.assertFalse(rdr.progress_reporter.use_color)

    def test_a_reporter_the_caller_chose_is_left_alone(self):
        """
        A reporter set on the RDR outranks this layer's default.
        """
        chosen = SpyProgressReporter()
        rdr = EQLSingleClassRDR(Animal, "species", progress_reporter=chosen)

        IPythonInterface(rdr=rdr)

        self.assertIs(rdr.progress_reporter, chosen)

    def test_an_interface_without_an_rdr_installs_nothing(self):
        """
        An interface used standalone has no RDR to hand a reporter to.
        """
        interface = IPythonInterface()

        self.assertIsNone(interface.rdr)


if __name__ == "__main__":
    unittest.main()
