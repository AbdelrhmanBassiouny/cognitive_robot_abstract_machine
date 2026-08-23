"""
Tests for the no-target fitting path, where the expert labels the case as well as
justifying the label.

``fit_case`` without a ``target`` routes to
:meth:`~krrood.entity_query_language.rdr.expert.Expert.ask_for_rule`, which asks two
sequential questions: a focused conclusion-only one, and — only when the chosen conclusion
differs from the current one — a conditions-only one.
"""

from __future__ import annotations

import unittest

from krrood.entity_query_language.rdr.conclusion_helper import ConclusionSuggester
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.exceptions import (
    ExpertAbort,
    NoConclusionProvided,
    NoConditionsProvided,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.rule_tree_view import walk_rules
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species
from .expert_doubles import (
    full_feature_conditions,
    labelling_answer,
    labelling_expert,
    recording_expert,
)
from .zoo_loader import load_zoo_animals

animals, targets = load_zoo_animals()


def first(species: Species) -> Animal:
    """
    :param species: The ground-truth label to look for.
    :return: The first animal in the dataset carrying that label.
    """
    return next(animal for animal, target in zip(animals, targets) if target is species)


def rule_count(rdr: EQLSingleClassRDR) -> int:
    """
    :param rdr: The RDR to measure.
    :return: How many rules its tree currently holds.
    """
    if rdr.conditions_root is None:
        return 0
    return len(walk_rules(rdr.conditions_root))


# %% the two-question protocol


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestQuestionsAsked(unittest.TestCase):
    def setUp(self):
        target_by_name = {
            animal.name: target for animal, target in zip(animals, targets)
        }
        self.expert = recording_expert(labelling_answer(target_by_name))
        EQLSingleClassRDR(Animal, "species").fit_case(
            first(Species.mammal), expert=self.expert
        )

    def test_the_expert_is_asked_twice(self):
        self.assertEqual(len(self.expert.interface.calls), 2)

    def test_the_first_question_asks_only_for_the_conclusion(self):
        self.assertEqual(
            self.expert.interface.calls[0].requested, [AnswerName.CONCLUSION]
        )

    def test_the_second_question_asks_only_for_the_conditions(self):
        self.assertEqual(
            self.expert.interface.calls[1].requested, [AnswerName.CONDITIONS]
        )


# %% labelling


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestLabelling(unittest.TestCase):
    def test_the_expert_label_becomes_the_classification(self):
        target_by_name = {
            animal.name: target for animal, target in zip(animals, targets)
        }
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = first(Species.mammal)

        rdr.fit_case(mammal, expert=labelling_expert(target_by_name))

        self.assertEqual(rdr.classify(mammal), Species.mammal)

    def test_bulk_labelling_reproduces_every_ground_truth_label(self):
        subset, subset_targets = animals[:12], targets[:12]
        target_by_name = {
            animal.name: target for animal, target in zip(subset, subset_targets)
        }
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.fit(subset, [...] * len(subset), labelling_expert(target_by_name))

        for animal, expected in zip(subset, subset_targets):
            with self.subTest(animal=animal.name):
                self.assertEqual(rdr.classify(animal), expected)

    def test_a_label_that_contradicts_a_firing_rule_refines_it(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        fish, mammal = first(Species.fish), first(Species.mammal)
        # Seed an over-general rule: backbone -> fish, which the mammal also satisfies.
        rdr.fit_case(
            fish,
            Species.fish,
            Expert(
                interface=FunctionInterface(
                    answer_function=lambda context, requests: {
                        AnswerName.CONDITIONS: context.case_variable.backbone == True
                    }
                )
            ),
        )
        self.assertEqual(rdr.classify(mammal), Species.fish)

        rdr.fit_case(mammal, expert=labelling_expert({mammal.name: Species.mammal}))

        self.assertEqual(rdr.classify(mammal), Species.mammal)
        self.assertEqual(rdr.classify(fish), Species.fish)


# %% keeping the conclusion that already stands


def _reaffirming_answer(context, requests):
    """
    Answer the conclusion question with the conclusion that already stands, and supply
    nothing else.

    :param context: The case being labelled.
    :param requests: The answers asked for.
    :return: The current conclusion, when it was asked for.
    """
    if any(request.name is AnswerName.CONCLUSION for request in requests):
        return {AnswerName.CONCLUSION: context.current_conclusion}
    return {}


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestKeepingTheCurrentConclusion(unittest.TestCase):
    def setUp(self):
        self.rdr = EQLSingleClassRDR(Animal, "species")
        self.mammal = first(Species.mammal)
        self.rdr.fit_case(
            self.mammal,
            Species.mammal,
            Expert(
                interface=FunctionInterface(
                    answer_function=lambda context, requests: {
                        AnswerName.CONDITIONS: context.case_variable.milk == True
                    }
                )
            ),
        )
        self.rules_before = rule_count(self.rdr)
        self.expert = recording_expert(_reaffirming_answer)

    def test_the_current_conclusion_is_returned(self):
        self.assertEqual(
            self.rdr.fit_case(self.mammal, expert=self.expert), Species.mammal
        )

    def test_no_rule_is_inserted(self):
        self.rdr.fit_case(self.mammal, expert=self.expert)

        self.assertEqual(rule_count(self.rdr), self.rules_before)

    def test_the_conditions_question_is_skipped(self):
        self.rdr.fit_case(self.mammal, expert=self.expert)

        self.assertEqual(
            [call.requested for call in self.expert.interface.calls],
            [[AnswerName.CONCLUSION]],
        )


# %% abandoning the session


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestAbort(unittest.TestCase):
    def test_aborting_the_conclusion_question_reports_the_missing_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        def abort(context, requests):
            raise ExpertAbort([AnswerName.CONCLUSION])

        with self.assertRaises(NoConclusionProvided):
            rdr.fit_case(
                first(Species.mammal),
                expert=Expert(interface=FunctionInterface(answer_function=abort)),
            )

    def test_aborting_the_conditions_question_reports_the_missing_conditions(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        def answer_then_abort(context, requests):
            if any(request.name is AnswerName.CONCLUSION for request in requests):
                return {AnswerName.CONCLUSION: Species.mammal}
            raise ExpertAbort([AnswerName.CONDITIONS])

        with self.assertRaises(NoConditionsProvided):
            rdr.fit_case(
                first(Species.mammal),
                expert=Expert(
                    interface=FunctionInterface(answer_function=answer_then_abort)
                ),
            )


# %% helpers pre-seeding the conclusion


class MammalSuggester(ConclusionSuggester):
    """
    A helper that always suggests :attr:`Species.mammal`.
    """

    def suggest(self, context):
        return Species.mammal


class BirdSuggester(ConclusionSuggester):
    """
    A helper that always suggests :attr:`Species.bird`.
    """

    def suggest(self, context):
        return Species.bird


class OutOfDomainSuggester(ConclusionSuggester):
    """
    A helper whose suggestion is not a :class:`Species`, so it fails domain validation.
    """

    def suggest(self, context):
        return "not a species"


def _conditions_only_answer(context, requests):
    """
    Supply the conditions and leave the conclusion at whatever it was pre-seeded with.

    :param context: The case being labelled.
    :param requests: The answers asked for.
    :return: The conditions answer, when it was asked for.
    """
    if any(request.name is AnswerName.CONDITIONS for request in requests):
        return {
            AnswerName.CONDITIONS: full_feature_conditions(
                context.case_variable, context.case_instance
            )
        }
    return {}


@unittest.skipIf(len(animals) == 0, "Failed to load zoo dataset")
class TestHelperSuggestions(unittest.TestCase):
    def test_a_valid_suggestion_stands_when_the_expert_supplies_no_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = first(Species.mammal)
        expert = Expert(
            interface=FunctionInterface(answer_function=_conditions_only_answer),
            helpers=[MammalSuggester()],
        )

        rdr.fit_case(mammal, expert=expert)

        self.assertEqual(rdr.classify(mammal), Species.mammal)

    def test_the_expert_can_answer_over_a_suggestion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = first(Species.mammal)

        def override(context, requests):
            answers = _conditions_only_answer(context, requests)
            if any(request.name is AnswerName.CONCLUSION for request in requests):
                answers[AnswerName.CONCLUSION] = Species.mammal
            return answers

        # The helper suggests bird; the expert answers mammal.
        expert = Expert(
            interface=FunctionInterface(answer_function=override),
            helpers=[BirdSuggester()],
        )

        rdr.fit_case(mammal, expert=expert)

        self.assertEqual(rdr.classify(mammal), Species.mammal)

    def test_a_suggestion_outside_the_domain_does_not_pre_seed_the_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        seen_defaults = []

        def record_default(context, requests):
            for request in requests:
                if request.name is AnswerName.CONCLUSION:
                    seen_defaults.append(request.default)
            answers = _conditions_only_answer(context, requests)
            if any(request.name is AnswerName.CONCLUSION for request in requests):
                answers[AnswerName.CONCLUSION] = Species.mammal
            return answers

        rdr.fit_case(
            first(Species.mammal),
            expert=Expert(
                interface=FunctionInterface(answer_function=record_default),
                helpers=[OutOfDomainSuggester()],
            ),
        )

        self.assertEqual(seen_defaults, [...])
