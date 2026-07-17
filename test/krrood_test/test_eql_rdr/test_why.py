"""
Tests for the why-question core: :mod:`krrood.entity_query_language.rdr.why`.

A *why* question asks why a case was given its conclusion; the answer names the rule
that fired, its condition expression, its place in the rule tree, the conditions that
were satisfied (with their bindings), and the corner case the rule was created for.

The rule trees here are grown with programmatic experts (the same contract the
interactive shell honours), so each test controls exactly which rule fires.
"""

import unittest

from krrood.entity_query_language.explanation.explanation import (
    ConditionAndBindings,
    Explanation,
    InferenceExplanation,
)
from krrood.entity_query_language.factories import an
from krrood.entity_query_language.rdr.backend import (
    ExplainingInference,
    RDRBackend,
)
from krrood.entity_query_language.rdr.exceptions import NoConclusionToExplainError
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.why import (
    RDRConclusionExplanation,
    WhyAnswer,
    WhyQuestion,
)

from .animal import Animal, Species
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()


def first(species: Species) -> Animal:
    return next(a for a, t in zip(animals, targets) if t is species)


def scripted_expert(rules):
    """
    An expert returning conditions from a per-target callable over the case variable.
    """

    def answer(context, requests):
        return {"conditions": rules[context.target_conclusion](context.case_variable)}

    return Expert(interface=FunctionInterface(answer_fn=answer))


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyTopLevelRule(unittest.TestCase):
    """
    A why-answer for a case classified by a single top-level rule.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        self.mammal = first(Species.mammal)
        self.rdr.fit_case(
            self.mammal,
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )
        self.answer = self.rdr.why(self.mammal)

    def test_answer_is_a_why_answer(self):
        self.assertIsInstance(self.answer, WhyAnswer)

    def test_conclusion_is_the_inferred_value(self):
        self.assertEqual(self.answer.conclusion, Species.mammal)

    def test_condition_is_the_firing_anchor(self):
        trace = self.rdr._trace(self.mammal)
        self.assertEqual(self.answer.condition._id_, trace.firing_anchor_id)

    def test_add_node_carries_the_conclusion(self):
        self.assertEqual(self.answer.add_node.unwrapped_value, Species.mammal)

    def test_rule_kind_and_depth_for_top_level_rule(self):
        self.assertEqual(self.answer.rule_kind, "if")
        self.assertEqual(self.answer.rule_depth, 0)

    def test_satisfied_conditions_carry_bindings(self):
        self.assertTrue(self.answer.satisfied_conditions)
        for condition in self.answer.satisfied_conditions:
            self.assertIsInstance(condition, ConditionAndBindings)

    def test_satisfied_conditions_match_the_trace(self):
        trace = self.rdr._trace(self.mammal)
        answered_ids = {c.condition._id_ for c in self.answer.satisfied_conditions}
        self.assertTrue(answered_ids)
        self.assertTrue(answered_ids <= set(trace.satisfied_condition_ids))

    def test_corner_case_is_the_case_that_created_the_rule(self):
        self.assertIs(self.answer.corner_case, self.mammal)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyRefinementRule(unittest.TestCase):
    """
    A why-answer for a case classified by a refinement (except-if) rule.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
            }
        )
        self.fish = first(Species.fish)
        self.mammal = first(Species.mammal)
        # Over-general fish rule fires for the mammal; refining it adds an except-if.
        self.rdr.fit_case(self.fish, Species.fish, expert)
        self.rdr.fit_case(self.mammal, Species.mammal, expert)
        self.answer = self.rdr.why(self.mammal)

    def test_conclusion_is_refined_value(self):
        self.assertEqual(self.answer.conclusion, Species.mammal)

    def test_rule_kind_and_depth_for_refinement(self):
        self.assertEqual(self.answer.rule_kind, "except if")
        self.assertEqual(self.answer.rule_depth, 1)

    def test_corner_case_is_the_refinement_case(self):
        self.assertIs(self.answer.corner_case, self.mammal)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyWithoutConclusion(unittest.TestCase):
    """
    Asking why when no rule fired is an illegal state, not a null answer.
    """

    def test_empty_rdr_raises(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        with self.assertRaises(NoConclusionToExplainError):
            rdr.why(first(Species.mammal))

    def test_case_that_fires_nothing_raises(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        rdr.fit_case(
            first(Species.mammal),
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )
        # An insect has no milk, so no rule fires.
        with self.assertRaises(NoConclusionToExplainError):
            rdr.why(first(Species.insect))


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestContrastReserved(unittest.TestCase):
    """
    The contrast field is reserved: answering a contrastive question is not implemented.
    """

    def test_contrastive_question_raises_not_implemented(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        rdr.fit_case(
            first(Species.mammal),
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )
        question = WhyQuestion(case=first(Species.mammal), contrast=Species.bird)
        with self.assertRaises(NotImplementedError):
            rdr.answer_why(question)

    def test_plain_question_is_not_contrastive(self):
        self.assertFalse(WhyQuestion(case=first(Species.mammal)).is_contrastive)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestExplanationUnification(unittest.TestCase):
    """
    RDR conclusions are explained through the same abstraction as EQL inferences.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        self.mammal = first(Species.mammal)
        self.rdr.fit_case(
            self.mammal,
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )

    def test_rdr_conclusion_explanation_is_an_explanation(self):
        explanation = self.rdr.explain(self.mammal)
        self.assertIsInstance(explanation, RDRConclusionExplanation)
        self.assertIsInstance(explanation, Explanation)

    def test_inference_explanation_shares_the_abstraction(self):
        self.assertTrue(issubclass(InferenceExplanation, Explanation))

    def test_explanation_exposes_satisfied_conditions(self):
        explanation = self.rdr.explain(self.mammal)
        answer = self.rdr.why(self.mammal)
        explained_ids = {
            c.condition._id_
            for c in explanation.get_satisfied_conditions_and_their_bindings()
        }
        answered_ids = {c.condition._id_ for c in answer.satisfied_conditions}
        self.assertEqual(explained_ids, answered_ids)

    def test_explanation_renders_a_string(self):
        explanation = self.rdr.explain(self.mammal)
        self.assertIn("milk", explanation.get_satisfied_conditions_as_string())


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestBackendExplainPath(unittest.TestCase):
    """
    The backend's explain path retains a trace per result; the fast path is unchanged.
    """

    def _backend(self):
        backend = RDRBackend(
            expert=scripted_expert(
                {
                    Species.mammal: lambda v: v.milk == True,
                    Species.bird: lambda v: v.feathers == True,
                }
            )
        )
        return backend

    def _query(self):
        mammal, bird = first(Species.mammal), first(Species.bird)
        return an(Animal)(species=...).from_([mammal, bird]), [mammal, bird]

    def test_explain_path_yields_one_trace_per_result(self):
        backend = self._backend()
        query, cases = self._query()
        ground_truth = {a.name: t for a, t in zip(animals, targets)}
        strategy = ExplainingInference()
        results = list(
            backend.infer(
                query, ground_truth=lambda c: ground_truth[c.name], strategy=strategy
            )
        )
        self.assertEqual(len(strategy.traces), len(results))

    def test_fast_path_matches_explain_path_values(self):
        ground_truth = {a.name: t for a, t in zip(animals, targets)}

        backend_fast = self._backend()
        query_fast, _ = self._query()
        fast = [
            d for d in backend_fast.infer(query_fast, lambda c: ground_truth[c.name])
        ]

        backend_explain = self._backend()
        query_explain, _ = self._query()
        strategy = ExplainingInference()
        explained = list(
            backend_explain.infer(
                query_explain,
                ground_truth=lambda c: ground_truth[c.name],
                strategy=strategy,
            )
        )
        self.assertEqual(len(fast), len(explained))

    def test_explaining_strategy_builds_conclusion_explanations(self):
        backend = self._backend()
        query, _ = self._query()
        ground_truth = {a.name: t for a, t in zip(animals, targets)}
        strategy = ExplainingInference()
        list(
            backend.infer(
                query, ground_truth=lambda c: ground_truth[c.name], strategy=strategy
            )
        )
        explanations = strategy.explanations()
        self.assertTrue(explanations)
        for explanation in explanations:
            self.assertIsInstance(explanation, Explanation)


if __name__ == "__main__":
    unittest.main()
