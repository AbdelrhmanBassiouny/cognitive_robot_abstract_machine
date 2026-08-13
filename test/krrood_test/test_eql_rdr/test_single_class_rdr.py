"""
Tests for :class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
orchestration: what ``classify`` returns, and which branch ``fit_case`` grows the tree
through.

Experts here are programmatic and return live EQL condition expressions built over the
RDR's shared case variable — the same contract the interactive shell honours.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.condition_resolver import ChainConditionResolver
from krrood.entity_query_language.rdr.exceptions import ExpertRequired
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species, make_animal
from .expert_doubles import (
    maximally_specific_expert,
    labelling_expert,
    recording_expert,
    scripted_expert,
)
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()


def first(species: Species) -> Animal:
    """
    :param species: The ground-truth label to look for.
    :return: The first animal in the dataset carrying that label.
    """
    return next(animal for animal, target in zip(animals, targets) if target is species)


# %% classification


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestClassify(unittest.TestCase):
    def test_empty_rdr_leaves_the_conclusion_undetermined(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        self.assertIs(rdr.classify(first(Species.mammal)), ...)

    def test_shared_case_variable_ranges_over_the_case_type(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        self.assertIs(rdr.case_variable._type_, Animal)

    def test_conclusion_variable_is_the_predicted_attribute_of_the_case_variable(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        self.assertEqual(rdr.conclusion_variable._id_, rdr.case_variable.species._id_)


# %% which branch fit_case grows


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestFitCaseBranches(unittest.TestCase):
    def test_first_case_seeds_the_tree(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert({Species.mammal: lambda v: v.milk == True})
        mammal = first(Species.mammal)

        rdr.fit_case(mammal, Species.mammal, expert)

        self.assertEqual(rdr.classify(mammal), Species.mammal)

    def test_first_case_is_asked_about_with_no_current_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert({Species.mammal: lambda v: v.milk == True})

        rdr.fit_case(first(Species.mammal), Species.mammal, expert)

        self.assertEqual(len(expert.interface.calls), 1)
        self.assertIs(expert.interface.calls[0].current_conclusion, ...)

    def test_case_no_rule_fires_for_becomes_an_alternative(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )
        mammal, bird = first(Species.mammal), first(Species.bird)
        rdr.fit_case(mammal, Species.mammal, expert)

        rdr.fit_case(bird, Species.bird, expert)

        self.assertEqual(rdr.classify(bird), Species.bird)
        self.assertEqual(rdr.classify(mammal), Species.mammal)

    def test_alternative_is_asked_about_with_no_current_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )
        rdr.fit_case(first(Species.mammal), Species.mammal, expert)

        rdr.fit_case(first(Species.bird), Species.bird, expert)

        self.assertIs(expert.interface.calls[-1].current_conclusion, ...)

    def test_case_a_wrong_rule_fires_for_becomes_a_refinement(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        # Over-general first rule: backbone -> fish, which a milk-bearing mammal also
        # satisfies.
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
            }
        )
        fish, mammal = first(Species.fish), first(Species.mammal)
        rdr.fit_case(fish, Species.fish, expert)
        self.assertEqual(rdr.classify(mammal), Species.fish)

        rdr.fit_case(mammal, Species.mammal, expert)

        self.assertEqual(rdr.classify(mammal), Species.mammal)
        self.assertEqual(rdr.classify(fish), Species.fish)

    def test_refinement_is_asked_about_with_the_wrong_conclusion_that_fired(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
            }
        )
        rdr.fit_case(first(Species.fish), Species.fish, expert)

        rdr.fit_case(first(Species.mammal), Species.mammal, expert)

        self.assertEqual(expert.interface.calls[-1].current_conclusion, Species.fish)

    def test_already_correct_case_does_not_reach_the_expert(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert({Species.mammal: lambda v: v.milk == True})
        mammal = first(Species.mammal)
        rdr.fit_case(mammal, Species.mammal, expert)
        calls_after_first_fit = len(expert.interface.calls)

        rdr.fit_case(mammal, Species.mammal, expert)

        self.assertEqual(len(expert.interface.calls), calls_after_first_fit)

    def test_case_needing_a_rule_without_an_expert_is_rejected(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        with self.assertRaises(ExpertRequired):
            rdr.fit_case(first(Species.mammal), Species.mammal)

    def test_already_correct_case_needs_no_expert(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = first(Species.mammal)
        rdr.fit_case(
            mammal,
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )

        self.assertEqual(rdr.fit_case(mammal, Species.mammal), Species.mammal)


# %% fitting a whole dataset


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestFit(unittest.TestCase):
    def test_maximally_specific_rules_memorise_the_training_set(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.fit(animals, targets, maximally_specific_expert())

        correct = sum(
            rdr.classify(animal) == target for animal, target in zip(animals, targets)
        )
        # A handful of zoo rows share a feature vector but differ in species, so a
        # feature-vector rule cannot separate them.
        self.assertGreaterEqual(correct / len(animals), 0.95)

    def test_fit_without_targets_labels_each_case_through_the_expert(self):
        subset, subset_targets = animals[:12], targets[:12]
        target_by_name = {
            animal.name: target for animal, target in zip(subset, subset_targets)
        }
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.fit(subset, expert=labelling_expert(target_by_name))

        for animal, expected in zip(subset, subset_targets):
            with self.subTest(animal=animal.name):
                self.assertEqual(rdr.classify(animal), expected)

    def test_fit_returns_the_rdr_for_chaining(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        self.assertIs(
            rdr.fit(animals[:3], targets[:3], maximally_specific_expert()), rdr
        )


# %% structural memoization


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestSubtreeWalksStayBounded(unittest.TestCase):
    """
    Structural facts about an expression's subtree are constant for the duration of an
    evaluation, so they must be memoized rather than recomputed by a full descendant
    walk on every comparator evaluation.

    Without memoization a tiny 8-case fit performs tens of thousands of walks, which
    grows into a multi-second stall on the full dataset.
    """

    def test_a_small_fit_does_not_rewalk_subtrees_every_evaluation(self):
        walks = 0
        original_iter = SymbolicExpression._iter_descendants_

        def counting_iter(self, visited_ids):
            nonlocal walks
            walks += 1
            yield from original_iter(self, visited_ids)

        rdr = EQLSingleClassRDR(Animal, "species")
        with patch.object(SymbolicExpression, "_iter_descendants_", counting_iter):
            rdr.fit(animals[:8], targets[:8], maximally_specific_expert())

        # The pre-memoization implementation performs ~59k walks for these 8 cases.
        self.assertLess(walks, 15000)


# %% automatic condition resolution


def _three_species_rdr(answer_function, *, with_resolver: bool):
    """
    Build an RDR that already knows mammal (``milk``), reptile (``venomous``) and bird
    (``feathers``), fitted in that order.

    A second bird that is *also* venomous is then misclassified as reptile, which is the
    refinement branch auto-resolution acts on.

    :param answer_function: The answer function the expert answers through.
    :param with_resolver: Whether to give the RDR the default backward-inference chain.
    :return:``(rdr, expert)``, the expert recording every interaction.
    """
    expert = recording_expert(answer_function)
    rdr = EQLSingleClassRDR(
        Animal,
        "species",
        condition_resolver=(
            ChainConditionResolver.backward_inference_default()
            if with_resolver
            else None
        ),
    )
    rdr.fit_case(
        make_animal("auto_mammal", milk=True, hair=True, legs=4),
        Species.mammal,
        expert,
    )
    rdr.fit_case(
        make_animal("auto_reptile", venomous=True, eggs=True, toothed=True, legs=4),
        Species.reptile,
        expert,
    )
    rdr.fit_case(
        make_animal("auto_bird", feathers=True, eggs=True, airborne=True, legs=2),
        Species.bird,
        expert,
    )
    return rdr, expert


def _discriminating_answer(context, requests):
    """
    Answer each target conclusion with its single discriminating trait.

    :param context: The case being fitted.
    :param requests: The answers asked for; ignored, conditions are always supplied.
    :return: The conditions answer for ``context.target_conclusion``.
    """
    conditions_for = {
        Species.mammal: lambda v: v.milk == True,
        Species.bird: lambda v: v.feathers == True,
        Species.reptile: lambda v: v.venomous == True,
        Species.fish: lambda v: v.fins == True,
    }
    return {
        AnswerName.CONDITIONS: conditions_for[context.target_conclusion](
            context.case_variable
        )
    }


def _bird_labelling_answer(context, requests):
    """
    Label every case ``Species.bird`` on the no-target path, with feather conditions.

    :param context: The case being labelled.
    :param requests: The answers asked for; the conclusion is supplied only when asked.
    :return: The conditions answer, plus the conclusion when it was requested.
    """
    answers = {AnswerName.CONDITIONS: context.case_variable.feathers == True}
    if any(request.name is AnswerName.CONCLUSION for request in requests):
        answers[AnswerName.CONCLUSION] = Species.bird
    return answers


def _venomous_bird() -> Animal:
    """
    :return: A bird the reptile rule wrongly intercepts, because it is also venomous.
    """
    return make_animal("venomous_bird", feathers=True, venomous=True, eggs=True, legs=2)


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestAutomaticConditionResolution(unittest.TestCase):
    """
    When a ``condition_resolver`` is set, ``fit_case`` derives the differentiating
    condition from the rule tree's backward-inference knowledge before asking the
    expert.

    Only the refinement branch resolves; the alternative and no-target branches always
    ask.
    """

    def test_expert_is_silent_when_resolution_succeeds(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=True)
        bird = _venomous_bird()
        self.assertEqual(rdr.classify(bird), Species.reptile)
        calls_before = len(expert.interface.calls)

        rdr.fit_case(bird, Species.bird, expert)

        self.assertEqual(len(expert.interface.calls), calls_before)

    def test_resolved_condition_corrects_the_classification(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=True)
        bird = _venomous_bird()

        rdr.fit_case(bird, Species.bird, expert)

        self.assertEqual(rdr.classify(bird), Species.bird)

    def test_expert_is_asked_once_when_the_target_has_no_known_conditions(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=True)
        # Nothing in the tree concludes fish yet, so backward inference has nothing to
        # discriminate with.
        fish = make_animal(
            "venomous_fish", fins=True, venomous=True, aquatic=True, toothed=True
        )
        self.assertEqual(rdr.classify(fish), Species.reptile)
        calls_before = len(expert.interface.calls)

        rdr.fit_case(fish, Species.fish, expert)

        self.assertEqual(len(expert.interface.calls), calls_before + 1)
        self.assertEqual(rdr.classify(fish), Species.fish)

    def test_expert_is_asked_when_no_resolver_is_set(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=False)
        bird = _venomous_bird()
        self.assertEqual(rdr.classify(bird), Species.reptile)
        calls_before = len(expert.interface.calls)

        rdr.fit_case(bird, Species.bird, expert)

        self.assertEqual(len(expert.interface.calls), calls_before + 1)
        self.assertEqual(rdr.classify(bird), Species.bird)

    def test_no_target_path_asks_the_expert_even_with_a_resolver(self):
        rdr, expert = _three_species_rdr(_bird_labelling_answer, with_resolver=True)
        unknown = make_animal("unlabelled", feathers=True, venomous=True, legs=2)
        calls_before = len(expert.interface.calls)

        rdr.fit_case(unknown, expert=expert)

        self.assertGreater(len(expert.interface.calls), calls_before)
        self.assertEqual(rdr.classify(unknown), Species.bird)
