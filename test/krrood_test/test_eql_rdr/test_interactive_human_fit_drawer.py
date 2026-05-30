"""
Human-in-the-loop fitting of the *correct drawer* dataset (SKIPPED by default).

``TestCorrectFitDrawerAsHumanExpert`` opens a **real embedded IPython shell** and asks
the human expert to author each rule's conditions **and conclusion** (the no-target
``ask_for_rule`` path), then saves the learned rule tree so it can be reloaded.

``TestCorrectDrawerNoTargetFit`` runs automatically and tests the conclusion-asking
flow deterministically through both :class:`FunctionInterface` and stubbed
:class:`IPythonInterface` paths.

``TestCorrectLoadHumanFittedDrawerModel`` is NOT interactive: it runs automatically
once the human-authored model file exists, loading it and verifying full accuracy.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from krrood.entity_query_language.factories import and_
from krrood.entity_query_language.rdr.expert import (
    ANSWER_NAME,
    CONCLUSION_NAME,
    Expert,
)
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.interface import (
    CASE_INSTANCE_NAME,
    CASE_VARIABLE_NAME,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.serialization import load_rdr, save_rdr
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.utils import UNSET

from .test_correct_drawer import (
    RDRTestCorrectDrawer,
    generate_test_correct_drawer_cases,
)

drawers, targets = generate_test_correct_drawer_cases()

#: Where the human-authored rule tree is saved, alongside these tests.
FITTED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "fitted_models")
SAVED_MODEL_PATH = os.path.join(FITTED_MODELS_DIR, "test_correct_drawer_rdr.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _drawer_ground_truth(drawer):
    """Return the correct conclusion for *drawer*.

    Only ``(left_handle, bottom_drawer)`` is correct.
    """
    return (
        drawer.handle.name == "left_handle" and drawer.container.name == "bottom_drawer"
    )


def _test_correct_drawer_conditions(case_variable, case):
    """EQL expression matching a case's handle name AND container name."""
    return and_(
        case_variable.handle.name == case.handle.name,
        case_variable.container.name == case.container.name,
    )


def _labelling_expert(label_of):
    """A :class:`FunctionInterface` expert that supplies *both* conclusion and conditions.

    The ``answer_fn`` is invoked twice per :meth:`Expert.ask_for_rule`:
    - First with ``requests`` containing only the conclusion request.
    - Second (via ``ask_for_conditions``) with ``requests`` containing only the
      conditions request.
    """

    def answer(context, requests):
        result = {
            ANSWER_NAME: _test_correct_drawer_conditions(
                context.case_variable, context.case_instance
            )
        }
        if any(r.name == CONCLUSION_NAME for r in requests):
            result[CONCLUSION_NAME] = label_of(context.case_instance)
        return result

    return Expert(interface=FunctionInterface(answer_fn=answer))


def _ipython_available() -> bool:
    try:
        import IPython  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Deterministic tests (run automatically)
# ---------------------------------------------------------------------------


class TestCorrectDrawerNoTargetFit(unittest.TestCase):
    """Deterministic tests for the no-target conclusion-asking flow on the correct-drawer dataset."""

    def test_conclusion_domain_resolves_as_enumerable_bool(self):
        """The ``Optional[bool]`` conclusion domain resolves to an enumerable bool."""
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        domain = rdr.conclusion_domain
        self.assertTrue(domain.is_enumerable)
        self.assertEqual(set(domain.members), {True, False})
        self.assertTrue(domain.allows_none)

    def test_first_no_target_fit_case_classifies_correctly_and_unseen_returns_none(
        self,
    ):
        """Fitting the first case via ``ask_for_rule`` classifies it correctly;
        an unseen case returns ``None`` (no rule fires)."""
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        rdr.fit_case(
            drawers[0], target=UNSET, expert=_labelling_expert(_drawer_ground_truth)
        )
        # The fitted case must classify to the expert-assigned conclusion.
        self.assertIs(rdr.classify(drawers[0]), True)
        # An unseen drawer has no matching rule → UNSET (the no-fire sentinel).
        self.assertIs(rdr.classify(drawers[1]), UNSET)

    def test_bulk_no_target_fit_all_four_cases_classifies_with_full_accuracy(self):
        """Fitting all four drawer cases (without targets) achieves 100 % accuracy."""
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        expert = _labelling_expert(_drawer_ground_truth)
        for case in drawers:
            rdr.fit_case(case, expert=expert)
        for case, target in zip(drawers, targets):
            self.assertEqual(rdr.classify(case), target)

    def test_answer_fn_is_called_first_for_conclusion_then_for_conditions(self):
        """The ``answer_fn`` receives the conclusion request first, then the conditions request."""
        call_log = []

        def tracking_answer(context, requests):
            call_log.append([r.name for r in requests])
            result = {
                ANSWER_NAME: _test_correct_drawer_conditions(
                    context.case_variable, context.case_instance
                )
            }
            if any(r.name == CONCLUSION_NAME for r in requests):
                result[CONCLUSION_NAME] = _drawer_ground_truth(context.case_instance)
            return result

        expert = Expert(interface=FunctionInterface(answer_fn=tracking_answer))
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        rdr.fit_case(drawers[0], target=UNSET, expert=expert)

        # First call: conclusion only.  Second call: conditions only.
        self.assertEqual(len(call_log), 2)
        self.assertEqual(call_log[0], [CONCLUSION_NAME])
        self.assertEqual(call_log[1], [ANSWER_NAME])

    def test_serialization_round_trip_preserves_classification(self):
        """Save → load → every classification matches the original model."""
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        expert = _labelling_expert(_drawer_ground_truth)
        for case in drawers:
            rdr.fit_case(case, expert=expert)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test_correct_drawer_model.py")
            save_rdr(rdr, path)
            loaded = load_rdr(path)

        for case, target in zip(drawers, targets):
            self.assertEqual(rdr.classify(case), loaded.classify(case))
            self.assertEqual(loaded.classify(case), target)

    def test_stubbed_ipython_shell_drives_no_target_fit_through_ask_for_rule(self):
        """A stubbed :class:`IPythonInterface` shell drives the two-question
        ``ask_for_rule`` flow (conclusion then conditions) end-to-end."""

        def runner(namespace, header):
            # The namespace contains the answer key for exactly one question:
            # ``CONCLUSION_NAME`` for the first, ``ANSWER_NAME`` for the second.
            if CONCLUSION_NAME in namespace:
                case = namespace[CASE_INSTANCE_NAME]
                namespace[CONCLUSION_NAME] = _drawer_ground_truth(case)
            if ANSWER_NAME in namespace:
                case = namespace[CASE_INSTANCE_NAME]
                case_variable = namespace[CASE_VARIABLE_NAME]
                build_and = namespace[and_.__name__]
                namespace[ANSWER_NAME] = build_and(
                    case_variable.handle.name == case.handle.name,
                    case_variable.container.name == case.container.name,
                )

        expert = Expert(interface=IPythonInterface(shell_runner=runner))
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        for case in drawers:
            rdr.fit_case(case, expert=expert)
        for case, target in zip(drawers, targets):
            self.assertEqual(rdr.classify(case), target, f"mismatch for {case}")


# ---------------------------------------------------------------------------
# Human-interactive tests (skipped by default)
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    False,
    "human-interactive: set to True and run with `pytest -s`",
)
@unittest.skipUnless(_ipython_available(), "IPython not installed")
class TestCorrectFitDrawerAsHumanExpert(unittest.TestCase):
    """Real interactive fitting of the correct-drawer dataset.

    Opens an embedded IPython shell for each misclassified drawer so a human
    expert can supply **both** the conclusion (True/False) and the distinguishing
    conditions.  The learned rule tree is saved so the automatic load-and-verify
    test can exercise it on subsequent runs.

    To opt in, change ``False`` to ``True`` in the ``skipUnless`` decorator above
    the class, then run::

        pytest -s \\
            test/krrood_test/test_eql_rdr/test_interactive_human_fit_drawer.py::TestCorrectFitDrawerAsHumanExpert

    ``-s`` is required so pytest does not capture stdin/stdout (the shell needs
    the terminal).
    """

    def test_fit_and_save(self):
        rdr = EQLSingleClassRDR(RDRTestCorrectDrawer, "correct")
        # targets=None triggers the no-target conclusion-asking path.
        rdr.fit(drawers, expert=Expert(interface=IPythonInterface()))

        os.makedirs(FITTED_MODELS_DIR, exist_ok=True)
        save_rdr(rdr, SAVED_MODEL_PATH)

        correct = sum(rdr.classify(d) == t for d, t in zip(drawers, targets))
        print(f"\n[interactive] accuracy on fitted set: {correct}/{len(drawers)}")
        print(f"[interactive] saved learned rule tree to: {SAVED_MODEL_PATH}")
        print(
            "[interactive] commit it to enable TestCorrectLoadHumanFittedDrawerModel.\n"
        )

        self.assertTrue(os.path.exists(SAVED_MODEL_PATH))


@unittest.skipUnless(
    os.path.exists(SAVED_MODEL_PATH),
    "no human-fitted model saved yet (run TestCorrectFitDrawerAsHumanExpert first)",
)
class TestCorrectLoadHumanFittedDrawerModel(unittest.TestCase):
    """Automatic verification that the human-authored model loads and classifies correctly."""

    def test_loaded_model_classifies_correctly(self):
        rdr = load_rdr(SAVED_MODEL_PATH)
        self.assertIs(rdr.case_type, RDRTestCorrectDrawer)
        self.assertEqual(rdr.conclusion_attribute_name, "correct")

        correct = sum(1 for d, t in zip(drawers, targets) if rdr.classify(d) == t)
        print(f"\n[loaded model] accuracy on drawer set: {correct}/{len(drawers)}")
        self.assertEqual(correct, len(drawers))


if __name__ == "__main__":
    unittest.main()
