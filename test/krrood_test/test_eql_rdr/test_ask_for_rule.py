"""
Tests for the no-target fitting path, where the expert labels the case as well as
justifying the label.

``fit_case`` without a ``target`` routes to
:meth:`~krrood.entity_query_language.rdr.expert.Expert.ask_for_rule`, which asks two
sequential questions: a focused conclusion-only one, and — only when the chosen conclusion
differs from the current one — a conditions-only one.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.rdr.conclusion_helper import ConclusionSuggester
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.exceptions import (
    ConclusionNotInDomain,
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
from .zoo_loader import ZooDataset

zoo = ZooDataset.load()


def rule_count(rdr: EQLSingleClassRDR) -> int:
    """
    :param rdr: The RDR to measure.
    :return: How many rules its tree currently holds.
    """
    if rdr.conditions_root is None:
        return 0
    return len(walk_rules(rdr.conditions_root))


# %% the two-question protocol


@pytest.fixture
def expert_asked_to_label_one_case() -> Expert:
    """
    :return: A recording expert, after one target-less ``fit_case`` has driven it.
    """
    target_by_name = {
        animal.name: target for animal, target in zip(zoo.animals, zoo.targets)
    }
    expert = recording_expert(labelling_answer(target_by_name))
    EQLSingleClassRDR(Animal, "species").fit_case(
        zoo.first(Species.mammal), expert=expert
    )
    return expert


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestQuestionsAsked:
    def test_the_expert_is_asked_twice(self, expert_asked_to_label_one_case):
        assert len(expert_asked_to_label_one_case.interface.calls) == 2

    def test_the_first_question_asks_only_for_the_conclusion(
        self, expert_asked_to_label_one_case
    ):
        calls = expert_asked_to_label_one_case.interface.calls
        assert calls[0].answer_names == [AnswerName.CONCLUSION]

    def test_the_second_question_asks_only_for_the_conditions(
        self, expert_asked_to_label_one_case
    ):
        calls = expert_asked_to_label_one_case.interface.calls
        assert calls[1].answer_names == [AnswerName.CONDITIONS]


# %% labelling


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestLabelling:
    def test_the_expert_label_becomes_the_classification(self):
        target_by_name = {
            animal.name: target for animal, target in zip(zoo.animals, zoo.targets)
        }
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = zoo.first(Species.mammal)

        rdr.fit_case(mammal, expert=labelling_expert(target_by_name))

        assert rdr.classify(mammal) == Species.mammal

    def test_bulk_labelling_reproduces_every_ground_truth_label(self):
        subset, subset_targets = zoo.animals[:12], zoo.targets[:12]
        target_by_name = {
            animal.name: target for animal, target in zip(subset, subset_targets)
        }
        rdr = EQLSingleClassRDR(Animal, "species")

        rdr.fit(subset, [...] * len(subset), labelling_expert(target_by_name))

        assert {animal.name: rdr.classify(animal) for animal in subset} == {
            animal.name: expected for animal, expected in zip(subset, subset_targets)
        }

    def test_a_label_that_contradicts_a_firing_rule_refines_it(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        fish, mammal = zoo.first(Species.fish), zoo.first(Species.mammal)
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
        assert rdr.classify(mammal) == Species.fish

        rdr.fit_case(mammal, expert=labelling_expert({mammal.name: Species.mammal}))

        assert rdr.classify(mammal) == Species.mammal
        assert rdr.classify(fish) == Species.fish


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


@dataclass
class StandingConclusion:
    """
    A fitted RDR whose rule already concludes correctly, and an expert that will be
    asked to label the same case again and will re-affirm that conclusion.
    """

    rdr: EQLSingleClassRDR
    """
    The RDR holding the single mammal rule.
    """

    mammal: Animal
    """
    The case the rule was written for, and the one to be labelled again.
    """

    rules_before: int
    """
    How many rules the tree held before the second, target-less fit.
    """

    expert: Expert
    """
    The recording expert that answers with the conclusion already standing.
    """


@pytest.fixture
def standing_conclusion() -> StandingConclusion:
    """
    :return: An RDR that already classifies its mammal correctly, ready to be asked
        about that same case with no target.
    """
    rdr = EQLSingleClassRDR(Animal, "species")
    mammal = zoo.first(Species.mammal)
    rdr.fit_case(
        mammal,
        Species.mammal,
        Expert(
            interface=FunctionInterface(
                answer_function=lambda context, requests: {
                    AnswerName.CONDITIONS: context.case_variable.milk == True
                }
            )
        ),
    )
    return StandingConclusion(
        rdr=rdr,
        mammal=mammal,
        rules_before=rule_count(rdr),
        expert=recording_expert(_reaffirming_answer),
    )


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestKeepingTheCurrentConclusion:
    def test_the_current_conclusion_is_returned(self, standing_conclusion):
        assert (
            standing_conclusion.rdr.fit_case(
                standing_conclusion.mammal, expert=standing_conclusion.expert
            )
            == Species.mammal
        )

    def test_no_rule_is_inserted(self, standing_conclusion):
        standing_conclusion.rdr.fit_case(
            standing_conclusion.mammal, expert=standing_conclusion.expert
        )

        assert rule_count(standing_conclusion.rdr) == standing_conclusion.rules_before

    def test_the_conditions_question_is_skipped(self, standing_conclusion):
        standing_conclusion.rdr.fit_case(
            standing_conclusion.mammal, expert=standing_conclusion.expert
        )

        assert [
            call.answer_names for call in standing_conclusion.expert.interface.calls
        ] == [[AnswerName.CONCLUSION]]


# %% abandoning the session


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestAbort:
    def test_aborting_the_conclusion_question_reports_the_missing_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        def abort(context, requests):
            raise ExpertAbort([AnswerName.CONCLUSION])

        with pytest.raises(NoConclusionProvided):
            rdr.fit_case(
                zoo.first(Species.mammal),
                expert=Expert(interface=FunctionInterface(answer_function=abort)),
            )

    def test_aborting_the_conditions_question_reports_the_missing_conditions(self):
        rdr = EQLSingleClassRDR(Animal, "species")

        def answer_then_abort(context, requests):
            if any(request.name is AnswerName.CONCLUSION for request in requests):
                return {AnswerName.CONCLUSION: Species.mammal}
            raise ExpertAbort([AnswerName.CONDITIONS])

        with pytest.raises(NoConditionsProvided):
            rdr.fit_case(
                zoo.first(Species.mammal),
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


@pytest.mark.skipif(len(zoo) == 0, reason="Failed to load zoo dataset")
class TestHelperSuggestions:
    def test_a_valid_suggestion_stands_when_the_expert_supplies_no_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = zoo.first(Species.mammal)
        expert = Expert(
            interface=FunctionInterface(answer_function=_conditions_only_answer),
            helpers=[MammalSuggester()],
        )

        rdr.fit_case(mammal, expert=expert)

        assert rdr.classify(mammal) == Species.mammal

    def test_the_expert_can_answer_over_a_suggestion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        mammal = zoo.first(Species.mammal)

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

        assert rdr.classify(mammal) == Species.mammal

    def test_a_suggestion_outside_the_domain_does_not_pre_seed_the_conclusion(self):
        rdr = EQLSingleClassRDR(Animal, "species")
        suggester = OutOfDomainSuggester()
        seen_defaults = []
        rejections = []

        def record_default(context, requests):
            for request in requests:
                if request.name is AnswerName.CONCLUSION:
                    seen_defaults.append(request.default)
                    rejections.append(
                        context.conclusion_domain.validate(
                            suggester.suggest(context), allow_unset=False
                        )
                    )
            answers = _conditions_only_answer(context, requests)
            if any(request.name is AnswerName.CONCLUSION for request in requests):
                answers[AnswerName.CONCLUSION] = Species.mammal
            return answers

        rdr.fit_case(
            zoo.first(Species.mammal),
            expert=Expert(
                interface=FunctionInterface(answer_function=record_default),
                helpers=[suggester],
            ),
        )

        # The suggestion is dropped because the domain rejects it, not because the
        # helper was never consulted.
        assert isinstance(rejections[0], ConclusionNotInDomain)
        assert seen_defaults == [...]
