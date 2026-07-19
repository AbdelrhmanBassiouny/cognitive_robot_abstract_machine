"""
Tests for causal-explanation verbalization:
:mod:`krrood.entity_query_language.verbalization.grammar.causal`.

A why-answer verbalizes as *"<conclusion> because <conditions>, by the <kind> rule"*: the
conclusion the fired rule reached, the satisfied conditions that justify it (read with the
concrete case, *"the Animal"*), and the identity of the rule that fired.

The rule trees here are grown with programmatic experts (the same contract the interactive
shell honours), so each test controls exactly which rule fires — mirroring
:mod:`test_why`.
"""

import unittest

import dataclasses

from krrood.entity_query_language.explanation.explanation import ConditionAndBindings
from krrood.entity_query_language.factories import and_
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.verbalization.exceptions import (
    UnverbalizableExpressionError,
)
from krrood.entity_query_language.verbalization.grammar.causal.rules import (
    CausalExplanationRule,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    RuleContext,
    select,
)
from krrood.entity_query_language.verbalization.grammar.framework.registry import RULES
from krrood.entity_query_language.verbalization.context import MicroplanningServices
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

from .animal import Animal, Species
from .zoo_loader import load_zoo_animals
from ..dataset.minimal_symbolic_expression import MinimalSymbolicExpression

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
class TestCausalTopLevelRule(unittest.TestCase):
    """
    The causal surface of a case classified by a single top-level rule.
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

    def test_golden_text(self):
        self.assertEqual(
            verbalize_expression(self.answer),
            "the species of the Animal is mammal, "
            "because the Animal is milk, by the base rule R0",
        )

    def test_because_fronts_the_condition(self):
        self.assertIn("because the Animal is milk", verbalize_expression(self.answer))

    def test_conclusion_precedes_because(self):
        surface = verbalize_expression(self.answer)
        self.assertLess(surface.index("is mammal"), surface.index("because"))


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestCausalConcreteInstance(unittest.TestCase):
    """
    The case is read as the concrete instance (*"the Animal"*), not the bare variable.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        self.mammal = first(Species.mammal)
        self.rdr.fit_case(
            self.mammal,
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )
        self.surface = verbalize_expression(self.rdr.why(self.mammal))

    def test_reads_with_the_definite_instance(self):
        self.assertIn("the Animal", self.surface)

    def test_does_not_read_the_bare_variable(self):
        self.assertNotIn("an Animal", self.surface)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestCausalCoordinatedConditions(unittest.TestCase):
    """
    Several satisfied conditions are coordinated under one *"because"*.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        self.bird = first(Species.bird)
        self.rdr.fit_case(
            self.bird,
            Species.bird,
            scripted_expert(
                {Species.bird: lambda v: and_(v.feathers == True, v.eggs == True)}
            ),
        )
        self.surface = verbalize_expression(self.rdr.why(self.bird))

    def test_conditions_are_coordinated_with_and(self):
        self.assertIn(
            "because the Animal is feathers, and the Animal is eggs", self.surface
        )


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestCausalRefinementRule(unittest.TestCase):
    """
    A refinement (except-if) rule names its kind in the rule-identity clause.
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
        self.surface = verbalize_expression(self.rdr.why(self.mammal))

    def test_rule_identity_names_the_refinement_with_its_code(self):
        self.assertIn("by the refinement rule R1", self.surface)

    def test_conclusion_is_the_refined_value(self):
        self.assertIn("the species of the Animal is mammal", self.surface)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestCausalAlternativeRule(unittest.TestCase):
    """
    An alternative (else-if) rule names its kind and code in the rule-identity clause.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )
        self.mammal = first(Species.mammal)
        self.bird = first(Species.bird)
        # The bird fires no existing rule, so its rule is added as an else-if alternative.
        self.rdr.fit_case(self.mammal, Species.mammal, expert)
        self.rdr.fit_case(self.bird, Species.bird, expert)
        self.surface = verbalize_expression(self.rdr.why(self.bird))

    def test_rule_identity_names_the_alternative_with_its_code(self):
        self.assertIn("by the alternative rule A1", self.surface)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestCausalRuleRegistration(unittest.TestCase):
    """
    The causal rule is auto-registered and dispatched without ambiguity.
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

    def test_rule_is_in_the_auto_discovered_registry(self):
        self.assertIn(CausalExplanationRule, {type(rule) for rule in RULES})

    def test_select_dispatches_a_why_answer_without_ambiguity(self):
        context = RuleContext(
            recurse=lambda node, options: node, services=MicroplanningServices()
        )
        # ``select`` raises AmbiguousRuleError on a tie; a clean dispatch proves none exists.
        self.assertIsInstance(
            select(self.answer, RULES, context), CausalExplanationRule
        )


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestCausalUnverbalizableCondition(unittest.TestCase):
    """
    An unverbalizable condition inside an explanation fails loudly, never silently.
    """

    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        self.mammal = first(Species.mammal)
        self.rdr.fit_case(
            self.mammal,
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )

    def test_unverbalizable_reason_raises(self):
        answer = self.rdr.why(self.mammal)
        # A node no grammar rule covers, standing in for an unsupported condition.
        unverbalizable = ConditionAndBindings(MinimalSymbolicExpression(), {})
        answer = dataclasses.replace(answer, satisfied_conditions=(unverbalizable,))
        with self.assertRaises(UnverbalizableExpressionError):
            verbalize_expression(answer)


if __name__ == "__main__":
    unittest.main()
