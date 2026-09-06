"""
Tests for :class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
orchestration: what ``classify`` returns, and which branch ``fit_case`` grows the tree
through.

Experts here are programmatic and return EQL condition expressions built over the RDR's
shared case variable — the same contract the interactive shell honours.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from typing_extensions import Any, Dict, Set, Tuple

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.condition_resolver import ChainConditionResolver
from krrood.entity_query_language.rdr.exceptions import ExpertRequired
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.factories import an
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.rule_tree import StatedRule
from krrood.entity_query_language.rdr.rule_tree_view import walk_rules
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rules.conclusion_selector import (
    Alternative,
    Refinement,
)

from .animal import Animal, Species, make_animal, make_bird, make_mammal
from .expert_doubles import (
    feature_vector,
    maximally_specific_expert,
    labelling_expert,
    recording_expert,
    scripted_expert,
)
from .zoo_loader import ZooDataset

zoo = ZooDataset.load()


def names_sharing_a_feature_vector_with_another_species() -> Set[str]:
    """
    A rule matching a complete feature vector cannot separate two rows carrying the same
    vector under different labels, so those rows are the only ones such a rule set can
    get wrong.

    :return: The names of the animals whose feature vector another species also carries.
    """
    species_by_vector: Dict[Tuple[Any, ...], Set[Species]] = defaultdict(set)
    for animal, target in zip(zoo.animals, zoo.targets):
        species_by_vector[feature_vector(animal)].add(target)
    return {
        animal.name
        for animal in zoo.animals
        if len(species_by_vector[feature_vector(animal)]) > 1
    }


# %% classification


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestClassify:
    def test_empty_rdr_leaves_the_conclusion_undetermined(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        assert rdr.classify(zoo.first(Species.mammal)) is ...

    def test_shared_case_variable_ranges_over_the_case_type(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        assert rdr.case_variable._type_ is Animal

    def test_conclusion_variable_is_the_predicted_attribute_of_the_case_variable(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        assert rdr.conclusion_variable._id_ == rdr.case_variable.species._id_


# %% which branch fit_case grows


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestFitCaseBranches:
    def test_first_case_seeds_the_tree(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert({Species.mammal: lambda v: v.milk == True})
        mammal = zoo.first(Species.mammal)

        rdr.fit_case(mammal, Species.mammal, expert)

        assert rdr.classify(mammal) == Species.mammal

    def test_first_case_is_asked_about_with_no_current_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert({Species.mammal: lambda v: v.milk == True})

        rdr.fit_case(zoo.first(Species.mammal), Species.mammal, expert)

        assert len(expert.interface.calls) == 1
        assert expert.interface.calls[0].context.current_conclusion is ...

    def test_case_no_rule_fires_for_becomes_an_alternative(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )
        mammal, bird = zoo.first(Species.mammal), zoo.first(Species.bird)
        rdr.fit_case(mammal, Species.mammal, expert)

        rdr.fit_case(bird, Species.bird, expert)

        assert isinstance(rdr.conditions_root, Alternative)
        assert rdr.classify(bird) == Species.bird
        assert rdr.classify(mammal) == Species.mammal

    def test_alternative_is_asked_about_with_no_current_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )
        rdr.fit_case(zoo.first(Species.mammal), Species.mammal, expert)

        rdr.fit_case(zoo.first(Species.bird), Species.bird, expert)

        assert isinstance(rdr.conditions_root, Alternative)
        assert expert.interface.calls[-1].context.current_conclusion is ...

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
        fish, mammal = zoo.first(Species.fish), zoo.first(Species.mammal)
        rdr.fit_case(fish, Species.fish, expert)
        assert rdr.classify(mammal) == Species.fish

        rdr.fit_case(mammal, Species.mammal, expert)

        assert isinstance(rdr.conditions_root, Refinement)
        assert rdr.classify(mammal) == Species.mammal
        assert rdr.classify(fish) == Species.fish

    def test_refinement_is_asked_about_with_the_wrong_conclusion_that_fired(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
            }
        )
        rdr.fit_case(zoo.first(Species.fish), Species.fish, expert)

        rdr.fit_case(zoo.first(Species.mammal), Species.mammal, expert)

        assert isinstance(rdr.conditions_root, Refinement)
        assert expert.interface.calls[-1].context.current_conclusion == Species.fish

    def test_already_correct_case_does_not_reach_the_expert(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert({Species.mammal: lambda v: v.milk == True})
        mammal = zoo.first(Species.mammal)
        rdr.fit_case(mammal, Species.mammal, expert)
        calls_after_first_fit = len(expert.interface.calls)

        rdr.fit_case(mammal, Species.mammal, expert)

        assert len(expert.interface.calls) == calls_after_first_fit

    def test_case_needing_a_rule_without_an_expert_is_rejected(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        with pytest.raises(ExpertRequired):
            rdr.fit_case(zoo.first(Species.mammal), Species.mammal)

    def test_already_correct_case_needs_no_expert(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = zoo.first(Species.mammal)
        rdr.fit_case(
            mammal,
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )

        assert rdr.fit_case(mammal, Species.mammal) == Species.mammal


# %% the root the rule tree hangs from


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestConditionsRoot:
    def test_an_empty_rdr_has_no_conditions_root(self):
        assert EQLSingleClassRDR(Animal, "species").conditions_root is None

    def test_every_rule_stays_reachable_from_the_conditions_root(self):
        """
        The root is reported from the query the RDR built, while both insertion helpers
        splice new rules above or below existing nodes.

        A root left behind by one of those splices would hide the rules on the other
        side of it, so the property to hold is that the reported root still reaches
        every rule inserted.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
                Species.insect: lambda v: v.legs == 6,
            }
        )
        # One case per branch: the seed, a refinement of it, an alternative, and a
        # second refinement below the first.
        rdr.fit_case(zoo.first(Species.fish), Species.fish, expert)
        rdr.fit_case(zoo.first(Species.mammal), Species.mammal, expert)
        rdr.fit_case(zoo.first(Species.insect), Species.insect, expert)
        rdr.fit_case(zoo.first(Species.bird), Species.bird, expert)

        assert len(walk_rules(rdr.conditions_root)) == 4

    def test_a_conclusion_reached_through_every_branch_is_still_inferable(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        expert = scripted_expert(
            {
                Species.fish: lambda v: v.backbone == True,
                Species.mammal: lambda v: v.milk == True,
                Species.bird: lambda v: v.feathers == True,
            }
        )
        for species in (Species.fish, Species.mammal, Species.bird):
            rdr.fit_case(zoo.first(species), species, expert)

        assert {
            species: rdr.sufficient_conditions_for(species).is_satisfiable()
            for species in (Species.fish, Species.mammal, Species.bird)
        } == {Species.fish: True, Species.mammal: True, Species.bird: True}


# %% building from an underspecified query


def test_from_underspecified_predicts_the_underspecified_attribute():
    rdr = EQLSingleClassRDR.from_underspecified(an(Animal)(species=...))

    assert rdr.case_type is Animal
    assert rdr.conclusion_attribute_name == "species"


# %% fitting a whole dataset


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestFit:
    def test_maximally_specific_rules_memorise_the_training_set(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.fit(zoo.animals, zoo.targets, maximally_specific_expert())

        misclassified = {
            animal.name
            for animal, target in zip(zoo.animals, zoo.targets)
            if rdr.classify(animal) != target
        }

        # No zoo row shares its feature vector with a different species, so there is
        # nothing a feature-vector rule set could fail to separate.
        assert names_sharing_a_feature_vector_with_another_species() == set()
        assert misclassified == set()

    def test_fit_without_targets_labels_each_case_through_the_expert(self):
        subset, subset_targets = zoo.animals[:12], zoo.targets[:12]
        target_by_name = {
            animal.name: target for animal, target in zip(subset, subset_targets)
        }
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.fit(subset, expert=labelling_expert(target_by_name))

        assert {animal.name: rdr.classify(animal) for animal in subset} == {
            animal.name: expected for animal, expected in zip(subset, subset_targets)
        }

    def test_fit_returns_the_rdr_for_chaining(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        assert (
            rdr.fit(zoo.animals[:3], zoo.targets[:3], maximally_specific_expert())
            is rdr
        )


# %% structural memoization


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestSubtreeWalksStayBounded:
    """
    Structural facts about an expression's subtree are constant for the duration of an
    evaluation, so they must be memoized rather than recomputed by a full descendant
    walk on every comparator evaluation.

    Without memoization a tiny 8-case fit performs tens of thousands of walks, which
    grows into a multi-second stall on the full dataset.
    """

    def test_a_small_fit_does_not_rewalk_subtrees_every_evaluation(self, monkeypatch):
        walks = 0
        original_iter = SymbolicExpression._iter_descendants_

        def counting_iter(expression, visited_ids):
            nonlocal walks
            walks += 1
            yield from original_iter(expression, visited_ids)

        monkeypatch.setattr(SymbolicExpression, "_iter_descendants_", counting_iter)
        rdr = EQLSingleClassRDR(Animal, "species")
        rdr.fit(zoo.animals[:8], zoo.targets[:8], maximally_specific_expert())

        # The pre-memoization implementation performs ~59k walks for these 8 cases.
        assert walks < 15000


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


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestAutomaticConditionResolution:
    """
    When a ``condition_resolver`` is set, ``fit_case`` derives the differentiating
    condition from the rule tree's backward-inference condition sets before asking the
    expert.

    Only the refinement branch resolves; the alternative and no-target branches always
    ask.
    """

    def test_expert_is_silent_when_resolution_succeeds(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=True)
        bird = _venomous_bird()
        assert rdr.classify(bird) == Species.reptile
        calls_before = len(expert.interface.calls)

        rdr.fit_case(bird, Species.bird, expert)

        assert len(expert.interface.calls) == calls_before

    def test_resolved_condition_corrects_the_classification(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=True)
        bird = _venomous_bird()

        rdr.fit_case(bird, Species.bird, expert)

        assert rdr.classify(bird) == Species.bird

    def test_expert_is_asked_once_when_the_target_has_no_known_conditions(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=True)
        # Nothing in the tree concludes fish yet, so backward inference has nothing to
        # discriminate with.
        fish = make_animal(
            "venomous_fish", fins=True, venomous=True, aquatic=True, toothed=True
        )
        assert rdr.classify(fish) == Species.reptile
        calls_before = len(expert.interface.calls)

        rdr.fit_case(fish, Species.fish, expert)

        assert len(expert.interface.calls) == calls_before + 1
        assert rdr.classify(fish) == Species.fish

    def test_expert_is_asked_when_no_resolver_is_set(self):
        rdr, expert = _three_species_rdr(_discriminating_answer, with_resolver=False)
        bird = _venomous_bird()
        assert rdr.classify(bird) == Species.reptile
        calls_before = len(expert.interface.calls)

        rdr.fit_case(bird, Species.bird, expert)

        assert len(expert.interface.calls) == calls_before + 1
        assert rdr.classify(bird) == Species.bird

    def test_no_target_path_asks_the_expert_even_with_a_resolver(self):
        rdr, expert = _three_species_rdr(_bird_labelling_answer, with_resolver=True)
        unknown = make_animal("unlabelled", feathers=True, venomous=True, legs=2)
        calls_before = len(expert.interface.calls)

        rdr.fit_case(unknown, expert=expert)

        assert len(expert.interface.calls) > calls_before
        assert rdr.classify(unknown) == Species.bird


# %% rules stated outright


class TestStateRules:
    """
    Rules an author already has need no case to be derived from: they are written down
    and taken as they are.
    """

    def test_a_stated_rule_answers_the_cases_its_condition_holds_for(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.state_rules([StatedRule(rdr.case_variable.milk == True, Species.mammal)])

        assert rdr.classify(make_mammal()) == Species.mammal

    def test_a_case_no_stated_rule_reaches_stays_undetermined(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.state_rules([StatedRule(rdr.case_variable.milk == True, Species.mammal)])

        assert rdr.classify(make_bird()) is ...

    def test_the_first_rule_whose_condition_holds_is_the_one_that_answers(self):
        """
        Stated order is the order they are tried in, which is how an author says that a
        narrow rule is to be preferred to the general one it overlaps.
        """
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.state_rules(
            [
                StatedRule(rdr.case_variable.feathers == True, Species.bird),
                StatedRule(rdr.case_variable.backbone == True, Species.fish),
            ]
        )

        assert rdr.classify(make_bird()) == Species.bird
        assert rdr.classify(make_mammal()) == Species.fish

    def test_every_stated_rule_is_one_rule_of_the_tree(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.state_rules(
            [
                StatedRule(rdr.case_variable.feathers == True, Species.bird),
                StatedRule(rdr.case_variable.milk == True, Species.mammal),
                StatedRule(rdr.case_variable.backbone == True, Species.fish),
            ]
        )

        assert len(walk_rules(rdr.conditions_root)) == 3

    def test_stating_rules_answers_with_the_rules_themselves(self):
        rdr = EQLSingleClassRDR.from_underspecified(an(Animal)(species=...))

        assert (
            rdr.state_rules(
                [StatedRule(rdr.case_variable.milk == True, Species.mammal)]
            )
            is rdr
        )

    def test_a_case_a_stated_rule_gets_wrong_is_corrected_by_fitting_it(self):
        """
        A stated tree is a starting point rather than the last word: the rules an author
        wrote and the rules an expert adds afterwards are one tree.
        """
        rdr = EQLSingleClassRDR(Animal, "species")
        rdr.state_rules([StatedRule(rdr.case_variable.backbone == True, Species.fish)])
        mammal = make_mammal()

        rdr.fit_case(
            mammal,
            Species.mammal,
            scripted_expert({Species.mammal: lambda v: v.milk == True}),
        )

        assert rdr.classify(mammal) == Species.mammal
        assert rdr.classify(make_animal("a_fish", backbone=True)) == Species.fish

    def test_rules_reading_one_trait_are_stated_together_without_clashing(self):
        """
        Rules are written down before any of them is in the tree, so two that read the
        same trait share the expression that reads it -- which the tree has to take as
        one trait read twice rather than as two rules fighting over one node.
        """
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.state_rules(
            [
                StatedRule(rdr.case_variable.milk == True, Species.mammal),
                StatedRule(rdr.case_variable.milk == False, Species.bird),
            ]
        )

        assert rdr.classify(make_mammal()) == Species.mammal
        assert rdr.classify(make_bird()) == Species.bird

    def test_a_conclusion_a_stated_rule_reaches_is_inferable_backwards(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.state_rules(
            [
                StatedRule(rdr.case_variable.feathers == True, Species.bird),
                StatedRule(rdr.case_variable.milk == True, Species.mammal),
            ]
        )

        assert rdr.sufficient_conditions_for(Species.mammal).is_satisfiable()
