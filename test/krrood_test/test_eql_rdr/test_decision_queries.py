"""
Tests for the decision-query pattern and its explanation semantics.

A decision is an underspecified query over a partially-specified object; choosing is filling
its ``...`` by evaluating with an RDR backend, and asking why is
:func:`~krrood.entity_query_language.rdr.decision.explain` over the yielded result. These
tests exercise the end-to-end three-liner and the model-side explanation store that backs
it (weak, identity-keyed, last-classification-wins), against the pattern-named
:class:`~krrood_test.dataset.decision_object.SlotAssignment` mimic.
"""

import gc
import unittest
import weakref
from dataclasses import dataclass

from krrood.entity_query_language.explanation.explanation import (
    Explanation,
    explain_inference,
)
from krrood.entity_query_language.factories import an, entity, inference
from krrood.entity_query_language.rdr.backend import RDRBackend
from krrood.entity_query_language.rdr.decision import (
    ExplainedUnificationDict,
    explain,
)
from krrood.entity_query_language.rdr.exceptions import (
    NoRecordedExplanation,
    UnexplainedResult,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.why import RDRConclusionExplanation
from krrood.symbol_graph.symbol_graph import Symbol

from ..dataset.decision_object import Slot, SlotAssignment


@dataclass(unsafe_hash=True)
class InferredChoice(Symbol):
    """
    A Symbol-valued choice produced by inference, used to exercise the shared surface.
    """

    slot: str


def scripted_expert(condition_of):
    """
    An expert returning conditions from a per-target callable over the case variable.
    """

    def answer(context, requests):
        return {
            "conditions": condition_of[context.target_conclusion](context.case_variable)
        }

    return Expert(interface=FunctionInterface(answer_fn=answer))


def circle_to_left_rdr() -> EQLSingleClassRDR:
    """
    A fitted RDR that assigns a circle to the left slot.
    """
    rdr = EQLSingleClassRDR(SlotAssignment, "chosen")
    rdr.fit_case(
        SlotAssignment(shape="circle"),
        Slot.left,
        scripted_expert({Slot.left: lambda v: v.shape == "circle"}),
    )
    return rdr


def backend_over(rdr: EQLSingleClassRDR) -> RDRBackend:
    """
    A backend whose only model is ``rdr``.
    """
    backend = RDRBackend()
    backend.models[(SlotAssignment, "chosen")] = rdr
    return backend


class TestDecisionQueryThreeLiner(unittest.TestCase):
    """
    The canonical three-liner: evaluate a decision, explain it, verbalize it.
    """

    def setUp(self):
        self.backend = backend_over(circle_to_left_rdr())
        self.assignment = SlotAssignment(shape="circle")

    def _query(self):
        return an(SlotAssignment)(chosen=...).from_([self.assignment])

    def test_evaluate_yields_the_chosen_slot(self):
        query = self._query()
        result = next(query.evaluate(backend=self.backend))
        self.assertEqual(result[query.variable.chosen], Slot.left)

    def test_explain_names_the_fired_rule_conclusion(self):
        explanation = explain(next(self._query().evaluate(backend=self.backend)))
        self.assertIsInstance(explanation, RDRConclusionExplanation)
        self.assertEqual(explanation.why_answer.conclusion, Slot.left)

    def test_three_liner_verbalizes(self):
        explanation = explain(next(self._query().evaluate(backend=self.backend)))
        self.assertEqual(
            explanation.why_answer.verbalize(),
            "the chosen of the SlotAssignment is left, "
            "because the shape of the SlotAssignment is 'circle', by the base rule R0",
        )


class TestExplanationBearingHandle(unittest.TestCase):
    """
    The yielded handle carries the explanation and matches the model store.
    """

    def setUp(self):
        self.rdr = circle_to_left_rdr()
        self.backend = backend_over(self.rdr)
        self.assignment = SlotAssignment(shape="circle")

    def test_evaluate_yields_an_explanation_bearing_handle(self):
        result = next(
            an(SlotAssignment)(chosen=...)
            .from_([self.assignment])
            .evaluate(backend=self.backend)
        )
        self.assertIsInstance(result, ExplainedUnificationDict)

    def test_handle_exposes_conclusion_explanation_attribute(self):
        # The ``conclusion_explanation`` attribute is the seam the why(...) surface reads
        # a result handle through; renaming it would silently break that composition.
        result = next(
            an(SlotAssignment)(chosen=...)
            .from_([self.assignment])
            .evaluate(backend=self.backend)
        )
        self.assertIsInstance(result.conclusion_explanation, RDRConclusionExplanation)

    def test_handle_explanation_is_the_stored_one(self):
        result = next(
            an(SlotAssignment)(chosen=...)
            .from_([self.assignment])
            .evaluate(backend=self.backend)
        )
        self.assertIs(explain(result), self.rdr.explanation_store.get(self.assignment))

    def test_why_answer_matches_the_store(self):
        result = next(
            an(SlotAssignment)(chosen=...)
            .from_([self.assignment])
            .evaluate(backend=self.backend)
        )
        self.assertEqual(self.rdr.why(self.assignment), explain(result).why_answer)


class TestFastPathHasNoExplanation(unittest.TestCase):
    """
    The bulk fast path stays unchanged: no explanation attached, none recorded.
    """

    def setUp(self):
        self.rdr = circle_to_left_rdr()
        self.backend = backend_over(self.rdr)
        self.assignment = SlotAssignment(shape="circle")

    def test_infer_default_yields_plain_handle(self):
        result = next(
            self.backend.infer(an(SlotAssignment)(chosen=...).from_([self.assignment]))
        )
        self.assertNotIsInstance(result, ExplainedUnificationDict)

    def test_explain_on_fast_result_raises(self):
        result = next(
            self.backend.infer(an(SlotAssignment)(chosen=...).from_([self.assignment]))
        )
        with self.assertRaises(UnexplainedResult):
            explain(result)


class TestEnumAliasingRegression(unittest.TestCase):
    """
    Two cases concluding the SAME enum value get distinct explanations.
    """

    def setUp(self):
        self.rdr = circle_to_left_rdr()
        self.circle_one = SlotAssignment(shape="circle")
        self.circle_two = SlotAssignment(shape="circle")
        self.first = self.rdr.classify_and_explain(self.circle_one)
        self.second = self.rdr.classify_and_explain(self.circle_two)

    def test_same_concluded_value(self):
        self.assertEqual(self.first.value, self.second.value)
        self.assertEqual(self.first.value, Slot.left)

    def test_distinct_explanations(self):
        self.assertIsNot(self.first.explanation, self.second.explanation)
        self.assertIsNot(
            self.rdr.explanation_store.get(self.circle_one),
            self.rdr.explanation_store.get(self.circle_two),
        )

    def test_shared_enum_value_carries_no_explanation(self):
        self.assertFalse(hasattr(Slot.left, "conclusion_explanation"))
        self.assertFalse(hasattr(Slot.left, "_inference_explanation_"))


class TestReclassificationOverwrites(unittest.TestCase):
    """
    The store answers for the latest classification of a case.
    """

    def test_store_returns_the_latest_explanation(self):
        rdr = circle_to_left_rdr()
        case = SlotAssignment(shape="circle")
        first = rdr.classify_and_explain(case).explanation
        second = rdr.classify_and_explain(case).explanation
        self.assertIsNot(first, second)
        self.assertIs(rdr.explanation_store.get(case), second)


class TestWeakKeyLifetime(unittest.TestCase):
    """
    Deleting a case (with nothing else holding it) drops its stored explanation.
    """

    def test_deleting_the_case_drops_the_entry(self):
        rdr = circle_to_left_rdr()
        case = SlotAssignment(shape="circle")
        concluded = rdr.classify_and_explain(case)
        self.assertIn(case, rdr.explanation_store)
        key = id(case)

        # Re-target the shared case variable off ``case`` so the rule tree does not pin it.
        rdr.classify_and_explain(SlotAssignment(shape="square"))
        reference = weakref.ref(case)
        del case, concluded
        gc.collect()

        self.assertIsNone(reference())
        self.assertNotIn(key, rdr.explanation_store._entries)


class TestFirstAccessRaisesTypedException(unittest.TestCase):
    """
    First-access failure raises a typed exception, never a silent ``None``.
    """

    def test_store_require_raises(self):
        rdr = circle_to_left_rdr()
        with self.assertRaises(NoRecordedExplanation):
            rdr.explanation_store.require(SlotAssignment(shape="triangle"))

    def test_explain_on_unconcluded_result_raises(self):
        backend = backend_over(circle_to_left_rdr())
        # A triangle fires no rule, so the yielded handle carries no explanation.
        result = next(
            an(SlotAssignment)(chosen=...)
            .from_([SlotAssignment(shape="triangle")])
            .evaluate(backend=backend)
        )
        with self.assertRaises(UnexplainedResult):
            explain(result)


class TestExplainRoutesInferenceToo(unittest.TestCase):
    """
    ``explain`` routes an inference-created instance through the same surface.
    """

    def test_explain_returns_the_inference_explanation(self):
        instance = next(entity(inference(InferredChoice)(slot="left")).evaluate())
        self.assertIsInstance(explain(instance), Explanation)
        self.assertIs(explain(instance), explain_inference(instance))

    def test_explain_on_unexplained_object_raises(self):
        with self.assertRaises(UnexplainedResult):
            explain(InferredChoice(slot="left"))


if __name__ == "__main__":
    unittest.main()
