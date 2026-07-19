"""
Tests for the formal *why* ask surface:
:func:`krrood.entity_query_language.factories.why` and
:class:`krrood.entity_query_language.rdr.why.WhyQuery`.

``why(source)`` returns a query construct that composes over the explanation a result (or
case) already carries — never over the shared concluded value. Its primary input is a
yielded RDR result handle whose conclusion explanation rides on it
(:class:`~krrood.entity_query_language.rdr.why.ExplanationCarrier`); a case reaches the same
surface through ``rdr.explain(case)``. Reading is deferred, and the query verbalizes through
the W2 causal grammar as *"<conclusion> because <conditions>, by the <kind> rule"*.

The rule trees here are grown with programmatic experts (the same contract the interactive
shell honours), so each test controls exactly which rule fires — mirroring :mod:`test_why`
and :mod:`test_causal_verbalization`. A yielded result handle is mimicked by
:class:`ExplanationCarryingResult`, which carries a real ``RDRConclusionExplanation`` the way
the RDR backend will once explanations ride on results.
"""

import unittest

from dataclasses import dataclass, field

from typing_extensions import Optional

from krrood.entity_query_language.factories import why
from krrood.entity_query_language.rdr.exceptions import NoConclusionToExplainError
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.why import (
    ExplanationCarrier,
    RDRConclusionExplanation,
    WhyAnswer,
    WhyQuery,
)
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.grammar.causal.rules import WhyQueryRule
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    RuleContext,
    select,
)
from krrood.entity_query_language.verbalization.grammar.framework.registry import RULES
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

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


@dataclass
class ExplanationCarryingResult:
    """
    A yielded result handle mimic that carries its conclusion's explanation.

    Stands in for the fresh handle the RDR backend yields once explanations ride on
    results; the ask surface reads it through the :class:`ExplanationCarrier` seam.
    Access to the carried explanation is counted so a test can observe that the query
    reads it once.
    """

    explanation: Optional[RDRConclusionExplanation]
    """
    The explanation this result carries, or ``None`` when it carries none.
    """

    reads: int = 0
    """
    How many times :attr:`conclusion_explanation` was read.
    """

    @property
    def conclusion_explanation(self) -> Optional[RDRConclusionExplanation]:
        self.reads += 1
        return self.explanation


def _mammal_rdr():
    rdr = EQLSingleClassRDR(Animal, "species")
    mammal = first(Species.mammal)
    rdr.fit_case(
        mammal,
        Species.mammal,
        scripted_expert({Species.mammal: lambda v: v.milk == True}),
    )
    return rdr, mammal


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyFactoryReturnsQueryConstruct(unittest.TestCase):
    """
    ``why(...)`` returns a query construct over an explanation source.
    """

    def setUp(self):
        self.rdr, self.mammal = _mammal_rdr()

    def test_returns_a_why_query(self):
        self.assertIsInstance(why(self.rdr.explain(self.mammal)), WhyQuery)

    def test_source_is_carried(self):
        explanation = self.rdr.explain(self.mammal)
        self.assertIs(why(explanation).source, explanation)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyComposesOverYieldedResultHandle(unittest.TestCase):
    """
    The primary surface: a yielded result handle carrying its conclusion explanation.
    """

    def setUp(self):
        self.rdr, self.mammal = _mammal_rdr()
        self.result = ExplanationCarryingResult(self.rdr.explain(self.mammal))

    def test_handle_is_an_explanation_carrier(self):
        self.assertIsInstance(self.result, ExplanationCarrier)

    def test_answer_reads_the_carried_explanation(self):
        self.assertEqual(why(self.result).answer.conclusion, Species.mammal)

    def test_verbalizes_over_the_handle(self):
        self.assertEqual(
            why(self.result).verbalize(),
            "the species of the Animal is mammal, "
            "because the Animal is milk, by the base rule R0",
        )


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyComposesOverCaseStoreRead(unittest.TestCase):
    """
    A case reaches the same surface through its ``RDRConclusionExplanation``.
    """

    def setUp(self):
        self.rdr, self.mammal = _mammal_rdr()

    def test_over_an_rdr_conclusion_explanation(self):
        self.assertEqual(
            why(self.rdr.explain(self.mammal)).answer.conclusion, Species.mammal
        )

    def test_over_a_bare_why_answer(self):
        answer = self.rdr.why(self.mammal)
        self.assertIs(why(answer).answer, answer)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyReadingIsDeferredAndMemoized(unittest.TestCase):
    """
    Reading the source is deferred to first access and happens once.
    """

    def setUp(self):
        self.rdr, self.mammal = _mammal_rdr()

    def test_construction_does_not_read_the_source(self):
        result = ExplanationCarryingResult(self.rdr.explain(self.mammal))
        why(result)
        self.assertEqual(result.reads, 0)

    def test_answer_is_read_once_and_memoized(self):
        result = ExplanationCarryingResult(self.rdr.explain(self.mammal))
        query = why(result)
        self.assertIs(query.answer, query.answer)
        self.assertEqual(result.reads, 1)

    def test_missing_explanation_raises_only_when_answered(self):
        query = why(ExplanationCarryingResult(None))  # cheap ask, no raise
        with self.assertRaises(NoConclusionToExplainError):
            query.answer


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyQueryVerbalizesViaCausalGrammar(unittest.TestCase):
    """
    A top-level why-query verbalizes through the W2 causal grammar.
    """

    def setUp(self):
        self.rdr, self.mammal = _mammal_rdr()
        self.query = why(self.rdr.explain(self.mammal))

    def test_golden_text(self):
        self.assertEqual(
            self.query.verbalize(),
            "the species of the Animal is mammal, "
            "because the Animal is milk, by the base rule R0",
        )

    def test_verbalizes_identically_to_the_answer(self):
        self.assertEqual(
            self.query.verbalize(), verbalize_expression(self.rdr.why(self.mammal))
        )

    def test_verbalize_method_matches_pipeline(self):
        self.assertEqual(self.query.verbalize(), verbalize_expression(self.query))

    def test_conclusion_reads_over_the_entity_query(self):
        # The conclusion subject is an attribute of the case variable — the entity query the
        # rule tree ranges over — so it reads "the species of the Animal", composing the
        # why-query with the underlying EQL entity query.
        self.assertIn("the species of the Animal", self.query.verbalize())


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyQueryDispatch(unittest.TestCase):
    """
    The why-query is dispatchable through the rule registry without ambiguity.
    """

    def setUp(self):
        self.rdr, self.mammal = _mammal_rdr()
        self.query = why(self.rdr.explain(self.mammal))

    def test_rule_is_in_the_auto_discovered_registry(self):
        self.assertIn(WhyQueryRule, {type(rule) for rule in RULES})

    def test_select_dispatches_a_why_query_without_ambiguity(self):
        context = RuleContext(
            recurse=lambda node, options: node, services=MicroplanningServices()
        )
        # ``select`` raises AmbiguousRuleError on a tie; a clean dispatch proves none exists.
        self.assertIsInstance(select(self.query, RULES, context), WhyQueryRule)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyQueryRefinementRule(unittest.TestCase):
    """
    A refinement rule names its kind and code through the query surface too.
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
        # The over-general fish rule fires for the mammal; refining it adds an except-if.
        self.rdr.fit_case(self.fish, Species.fish, expert)
        self.rdr.fit_case(self.mammal, Species.mammal, expert)
        self.surface = why(self.rdr.explain(self.mammal)).verbalize()

    def test_rule_identity_names_the_refinement_with_its_code(self):
        self.assertIn("by the refinement rule R1", self.surface)

    def test_conclusion_is_the_refined_value(self):
        self.assertIn("the species of the Animal is mammal", self.surface)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestWhyContrastReserved(unittest.TestCase):
    """
    The contrast argument is reserved: it is accepted, but answering is not implemented.
    """

    def setUp(self):
        self.rdr, self.mammal = _mammal_rdr()

    def test_contrast_is_recorded_on_the_query(self):
        query = why(self.rdr.explain(self.mammal), contrast=Species.bird)
        self.assertTrue(query.is_contrastive)
        self.assertIs(query.contrast, Species.bird)

    def test_answering_a_contrastive_query_raises(self):
        query = why(self.rdr.explain(self.mammal), contrast=Species.bird)
        with self.assertRaises(NotImplementedError):
            query.answer

    def test_plain_query_is_not_contrastive(self):
        self.assertFalse(why(self.rdr.explain(self.mammal)).is_contrastive)


if __name__ == "__main__":
    unittest.main()
