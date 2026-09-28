"""
Tests for the convergent fitting loop of
:meth:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR.fit`: re-fitting
cases a later rule retroactively broke, refusing to loop forever, and the progress
lifecycle the loop drives.
"""

from __future__ import annotations

import dataclasses
import enum
from pathlib import Path

import pytest

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.exceptions import (
    ExpertRequired,
    RDRDidNotConvergeError,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.progress import (
    ProgressDescription,
    RecordedCall,
    SpyProgressReporter,
)
from krrood.entity_query_language.rdr.rule_tree_view import walk_rules
from krrood.entity_query_language.rdr.serialization import (
    ModelSaver,
    TemporaryModelSaver,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from typing_extensions import Any, Dict, List, Optional

from .animal import Animal, Species, make_animal
from .expert_doubles import recording_expert

# %% a two-attribute domain in which one attribute cannot discriminate


class Colour(enum.Enum):
    """
    Two mutually-exclusive labels.
    """

    red = 1
    """
    The label of the case whose ``distinguishing`` trait is true.
    """

    blue = 2
    """
    The label of the case whose ``distinguishing`` trait is false.
    """


@dataclasses.dataclass
class TwoTraitCase:
    """
    A case with one trait both instances share and one that separates them.
    """

    shared: bool
    """
    A trait every case carries, so a rule conditioned on it cannot discriminate.
    """

    distinguishing: bool
    """
    The trait that differs between the two cases.
    """

    colour: Optional[Colour] = None
    """
    The predicted attribute; ``None`` until a rule concludes it.
    """


RED_CASE = TwoTraitCase(shared=True, distinguishing=True)
"""
The case labelled :attr:`Colour.red`.
"""

BLUE_CASE = TwoTraitCase(shared=True, distinguishing=False)
"""
The case labelled :attr:`Colour.blue`.
"""

BOTH_CASES = [RED_CASE, BLUE_CASE]
"""
The two cases, in the order the fitting tests supply them.
"""

BOTH_TARGETS = [Colour.red, Colour.blue]
"""
The ground-truth labels paired with :data:`BOTH_CASES`.
"""


def _shared_trait_answer(
    context: CaseContext, requests: List[AnswerRequest]
) -> Dict[AnswerName, Any]:
    """
    Always condition on the trait both cases carry, so every new rule intercepts the
    previously fitted case and the pending set oscillates.

    :param context: The case being fitted.
    :param requests: The answers asked for; ignored, conditions are always supplied.
    :return: The conditions answer.
    """
    return {AnswerName.CONDITIONS: context.case_variable.shared == True}


def _distinguishing_trait_answer(
    context: CaseContext, requests: List[AnswerRequest]
) -> Dict[AnswerName, Any]:
    """
    Condition on the trait that differs, so each rule is satisfied by exactly one case.

    :param context: The case being fitted.
    :param requests: The answers asked for; ignored, conditions are always supplied.
    :return: The conditions answer.
    """
    variable = context.case_variable
    if context.target_conclusion is Colour.red:
        return {AnswerName.CONDITIONS: variable.distinguishing == True}
    return {AnswerName.CONDITIONS: variable.distinguishing == False}


def _colour_labelling_answer(
    context: CaseContext, requests: List[AnswerRequest]
) -> Dict[AnswerName, Any]:
    """
    Label each case from its own distinguishing trait, for the no-target path.

    :param context: The case being labelled.
    :param requests: The answers asked for; the conclusion is supplied only when asked.
    :return: The conditions answer, plus the conclusion when it was requested.
    """
    variable, case = context.case_variable, context.case_instance
    answers: Dict[AnswerName, Any] = {
        AnswerName.CONDITIONS: variable.distinguishing == case.distinguishing
    }
    if any(request.name is AnswerName.CONCLUSION for request in requests):
        answers[AnswerName.CONCLUSION] = (
            Colour.red if case.distinguishing else Colour.blue
        )
    return answers


@pytest.fixture()
def colour_rdr() -> EQLSingleClassRDR:
    """
    :return: An unfitted RDR over the two-trait domain.
    """
    return EQLSingleClassRDR(TwoTraitCase, "colour")


@pytest.fixture()
def non_discriminating_expert() -> Expert:
    """
    :return: An expert whose conditions can never separate the two cases.
    """
    return Expert(interface=FunctionInterface(answer_function=_shared_trait_answer))


@pytest.fixture()
def discriminating_expert() -> Expert:
    """
    :return: An expert whose conditions separate the two cases.
    """
    return Expert(
        interface=FunctionInterface(answer_function=_distinguishing_trait_answer)
    )


# %% refusing to loop forever


def test_oscillating_fit_raises_rather_than_looping(
    colour_rdr: EQLSingleClassRDR, non_discriminating_expert: Expert
):
    with pytest.raises(RDRDidNotConvergeError):
        colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, non_discriminating_expert)


def test_oscillation_error_names_the_cases_still_misclassified(
    colour_rdr: EQLSingleClassRDR, non_discriminating_expert: Expert
):
    with pytest.raises(RDRDidNotConvergeError) as raised:
        colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, non_discriminating_expert)

    assert raised.value.clashing_cases
    for case in raised.value.clashing_cases:
        assert case in BOTH_CASES


def test_oscillation_is_detected_when_any_earlier_passes_pending_set_recurs(
    colour_rdr: EQLSingleClassRDR, non_discriminating_expert: Expert
):
    """
    These two cases alternate: pass one leaves the red case wrong, pass two leaves the
    blue one wrong, and pass three is back to the red one. No two consecutive passes
    ever leave the same set, so detection has to compare against every earlier pass —
    a check against only the preceding pass would loop forever here. Pinning the exact
    pass count is what tells those two rules apart.
    """
    with pytest.raises(RDRDidNotConvergeError) as raised:
        colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, non_discriminating_expert)

    assert raised.value.passes == 3


@dataclasses.dataclass
class RecordingModelSaver(ModelSaver):
    """
    Records which RDR it was handed instead of writing a file.
    """

    saved: List[EQLSingleClassRDR] = dataclasses.field(default_factory=list)
    """
    The RDRs passed to :meth:`save`, oldest first.
    """

    def save(self, rdr: EQLSingleClassRDR) -> None:
        self.saved.append(rdr)


def test_oscillating_fit_saves_the_partial_model_before_raising(
    colour_rdr: EQLSingleClassRDR, non_discriminating_expert: Expert
):
    """
    A fit saves once on its way out, so a fit that gives up saves exactly once — the
    rules it did author are on disk, and the count does not grow with them.
    """
    saver = RecordingModelSaver()
    colour_rdr.model_saver = saver

    with pytest.raises(RDRDidNotConvergeError):
        colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, non_discriminating_expert)

    assert saver.saved == [colour_rdr]
    assert walk_rules(colour_rdr.conditions_root) != []


# %% what a fit persists


class _ExpertFailure(Exception):
    """
    Stands in for anything that can go wrong partway through a fit.
    """


def _expert_that_fails_after(successful_answers: int) -> Expert:
    """
    :param successful_answers: How many rules the expert authors before it breaks.
    :return: An expert that answers that many times, then raises.
    """
    answered = 0

    def answer(context: CaseContext, requests: List[AnswerRequest]):
        nonlocal answered
        if answered >= successful_answers:
            raise _ExpertFailure("the expert broke partway through")
        answered += 1
        return {AnswerName.CONDITIONS: context.case_variable.distinguishing == True}

    return Expert(interface=FunctionInterface(answer_function=answer))


def test_a_fit_that_crashes_still_saves_the_rules_it_had_authored(
    colour_rdr: EQLSingleClassRDR,
):
    saver = RecordingModelSaver()
    colour_rdr.model_saver = saver

    with pytest.raises(_ExpertFailure):
        colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, _expert_that_fails_after(1))

    assert saver.saved == [colour_rdr]
    assert len(walk_rules(colour_rdr.conditions_root)) == 1


def test_a_fit_that_fails_before_any_rule_saves_nothing_and_reports_its_own_failure(
    colour_rdr: EQLSingleClassRDR,
):
    """
    The serializer refuses an empty tree, and raising that from the save would replace
    the failure the caller actually needs to see.
    """
    saver = RecordingModelSaver()
    colour_rdr.model_saver = saver

    with pytest.raises(ExpertRequired):
        colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, expert=None)

    assert saver.saved == []


def test_a_completed_fit_saves_once_however_many_rules_it_wrote(
    colour_rdr: EQLSingleClassRDR, discriminating_expert: Expert
):
    saver = RecordingModelSaver()
    colour_rdr.model_saver = saver

    colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, discriminating_expert)

    assert saver.saved == [colour_rdr]
    assert len(walk_rules(colour_rdr.conditions_root)) == 2


def test_fitting_one_case_directly_also_saves_once(colour_rdr: EQLSingleClassRDR):
    saver = RecordingModelSaver()
    colour_rdr.model_saver = saver

    colour_rdr.fit_case(RED_CASE, Colour.red, _expert_that_fails_after(1))

    assert saver.saved == [colour_rdr]


def test_an_unconfigured_rdr_saves_where_it_can_say(discriminating_expert: Expert):
    rdr = EQLSingleClassRDR(TwoTraitCase, "colour")

    assert isinstance(rdr.model_saver, TemporaryModelSaver)

    rdr.fit(BOTH_CASES, BOTH_TARGETS, discriminating_expert)

    assert Path(rdr.model_saver.path).exists()
    Path(rdr.model_saver.path).unlink()


# %% converging


def test_convergent_fit_completes_without_raising(
    colour_rdr: EQLSingleClassRDR, discriminating_expert: Expert
):
    colour_rdr.fit(BOTH_CASES, BOTH_TARGETS, discriminating_expert)

    assert colour_rdr.classify(RED_CASE) is Colour.red
    assert colour_rdr.classify(BLUE_CASE) is Colour.blue


def test_no_target_fit_never_runs_oscillation_detection(
    colour_rdr: EQLSingleClassRDR,
):
    """
    The no-target path has no ground truth to converge against, so it fits each case
    exactly once — even with conditions that would oscillate under a ground-truth fit.
    """
    expert = Expert(
        interface=FunctionInterface(answer_function=_colour_labelling_answer)
    )

    colour_rdr.fit(BOTH_CASES, None, expert)

    assert colour_rdr.classify(RED_CASE) is Colour.red
    assert colour_rdr.classify(BLUE_CASE) is Colour.blue


# %% re-fitting a case a later rule broke


def _retroactive_break_scenario():
    """
    Three animals in which the last one's rule retroactively breaks the second.

    Fitted in order, the reptile's ``venomous`` rule intercepts the molusc, which is also
    venomous — so the molusc has to be re-fitted on a second pass.

    :return: ``(cases, targets)``.
    """
    cases = [
        make_animal(
            "break_mammal", hair=True, milk=True, toothed=True, legs=4, tail=True
        ),
        make_animal("break_molusc", backbone=False, venomous=True),
        make_animal(
            "break_reptile",
            venomous=True,
            predator=True,
            toothed=True,
            legs=4,
            tail=True,
        ),
    ]
    return cases, [Species.mammal, Species.molusc, Species.reptile]


def _retroactive_break_expert() -> Expert:
    """
    :return: A recording expert that answers ``backbone == False`` for a molusc a reptile
        rule has already intercepted, and the single discriminating trait otherwise.
    """

    def answer(
        context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        variable = context.case_variable
        target = context.target_conclusion
        if target is Species.mammal:
            return {AnswerName.CONDITIONS: variable.milk == True}
        if target is Species.reptile:
            return {AnswerName.CONDITIONS: variable.venomous == True}
        if context.current_conclusion is Species.reptile:
            return {AnswerName.CONDITIONS: variable.backbone == False}
        return {AnswerName.CONDITIONS: variable.milk == False}

    return recording_expert(answer)


def test_case_broken_by_a_later_rule_is_refitted():
    cases, case_targets = _retroactive_break_scenario()
    rdr = EQLSingleClassRDR(Animal, "species")

    rdr.fit(cases, case_targets, _retroactive_break_expert())

    for case, target in zip(cases, case_targets):
        assert rdr.classify(case) is target


def test_the_broken_case_is_asked_about_again_with_the_wrong_conclusion():
    cases, case_targets = _retroactive_break_scenario()
    expert = _retroactive_break_expert()
    rdr = EQLSingleClassRDR(Animal, "species")

    rdr.fit(cases, case_targets, expert)

    molusc_calls = [
        call
        for call in expert.interface.calls
        if call.context.case_instance.name == "break_molusc"
    ]
    assert len(molusc_calls) == 2
    assert molusc_calls[0].context.current_conclusion is ...
    assert molusc_calls[1].context.current_conclusion is Species.reptile


# %% the progress lifecycle the loop drives


def test_single_pass_fit_starts_updates_once_per_case_then_finishes():
    reporter = SpyProgressReporter()
    rdr = EQLSingleClassRDR(TwoTraitCase, "colour", progress_reporter=reporter)

    rdr.fit(
        BOTH_CASES,
        BOTH_TARGETS,
        Expert(
            interface=FunctionInterface(answer_function=_distinguishing_trait_answer)
        ),
    )

    assert reporter.events == [
        RecordedCall("start", (2,), {"description": ProgressDescription.FITTING}),
        RecordedCall("update", (1,), {}),
        RecordedCall("update", (1,), {}),
        RecordedCall("finish", (), {}),
    ]


def test_second_pass_resets_to_the_number_still_pending():
    cases, case_targets = _retroactive_break_scenario()
    reporter = SpyProgressReporter()
    rdr = EQLSingleClassRDR(Animal, "species", progress_reporter=reporter)

    rdr.fit(cases, case_targets, _retroactive_break_expert())

    assert reporter.events == [
        RecordedCall("start", (3,), {"description": ProgressDescription.FITTING}),
        RecordedCall("update", (1,), {}),
        RecordedCall("update", (1,), {}),
        RecordedCall("update", (1,), {}),
        RecordedCall("reset", (1,), {}),
        RecordedCall("update", (1,), {}),
        RecordedCall("finish", (), {}),
    ]


def test_no_target_fit_never_resets():
    reporter = SpyProgressReporter()
    rdr = EQLSingleClassRDR(TwoTraitCase, "colour", progress_reporter=reporter)

    rdr.fit(
        BOTH_CASES,
        None,
        Expert(interface=FunctionInterface(answer_function=_colour_labelling_answer)),
    )

    assert [event.method_name for event in reporter.events] == [
        "start",
        "update",
        "update",
        "finish",
    ]


def test_progress_is_finished_even_when_the_fit_does_not_converge():
    reporter = SpyProgressReporter()
    rdr = EQLSingleClassRDR(TwoTraitCase, "colour", progress_reporter=reporter)

    with pytest.raises(RDRDidNotConvergeError):
        rdr.fit(
            BOTH_CASES,
            BOTH_TARGETS,
            Expert(interface=FunctionInterface(answer_function=_shared_trait_answer)),
        )

    assert reporter.events[-1] == RecordedCall("finish", (), {})


def test_reporting_progress_does_not_change_what_is_fitted():
    cases, case_targets = _retroactive_break_scenario()
    without_reporter = EQLSingleClassRDR(Animal, "species")
    with_reporter = EQLSingleClassRDR(
        Animal, "species", progress_reporter=SpyProgressReporter()
    )

    without_reporter.fit(cases, case_targets, _retroactive_break_expert())
    with_reporter.fit(cases, case_targets, _retroactive_break_expert())

    for case in cases:
        assert without_reporter.classify(case) is with_reporter.classify(case)
