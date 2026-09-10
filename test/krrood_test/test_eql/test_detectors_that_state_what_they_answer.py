"""
Tests for a detector stating which looks it can answer, and for rules choosing among
detectors by those statements.
"""

from __future__ import annotations

from krrood.entity_query_language.backends import (
    Look,
    PerceptionDetector,
    state_the_detectors_own_condition,
)
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.serialization import NullModelSaver
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.query.query import Query

from ..dataset.detectors_that_state_what_they_answer import (
    MeasureTheDepth,
    PlaceToLookAt,
    ReadTheColors,
)

# %% what a detector says about itself


def test_a_detector_states_the_kind_of_look_it_answers():
    assert MeasureTheDepth.look_type() is PlaceToLookAt


def test_the_kind_a_detector_binds_is_a_look():
    """
    The type parameter is bound, so a detector cannot state its capability over
    something that is not a question put to perception.
    """
    assert issubclass(MeasureTheDepth.look_type(), Look)


def test_a_detector_asked_about_a_look_answers_with_its_own_statement():
    """
    What comes back is the query rather than a verdict, so whoever asked can evaluate
    it, inspect it or narrow it further.
    """
    detector = MeasureTheDepth()
    look = PlaceToLookAt(place="the table", depth_is_returned=True)

    asked = detector.asked_about(look)

    assert isinstance(asked, Query)
    assert asked.tolist() == [look]
    assert asked is detector.answerable_looks


def test_a_detector_answers_the_looks_its_condition_holds_for():
    detector = MeasureTheDepth()

    assert detector.asked_about(
        PlaceToLookAt(place="the table", depth_is_returned=True)
    ).tolist()
    assert not detector.asked_about(
        PlaceToLookAt(place="the table", depth_is_returned=False)
    ).tolist()


def test_two_detectors_of_one_family_answer_disjoint_looks():
    with_depth = PlaceToLookAt(place="the table", depth_is_returned=True)

    assert MeasureTheDepth().asked_about(with_depth).tolist()
    assert not ReadTheColors().asked_about(with_depth).tolist()


# %% rules choosing among them


def _rules_over(*detectors: PerceptionDetector) -> EQLSingleClassRDR:
    """
    Rules built from the underspecified statement *a place whose detector is to be
    worked out*, fitted with one look each detector answers.

    :param detectors: The detectors to state a rule for, in order.
    :return: The rules, ready to be asked about a look.
    """
    rules = EQLSingleClassRDR.from_underspecified(
        a(PlaceToLookAt)(detector=...), model_saver=NullModelSaver()
    )
    rules.fit(
        cases=[
            PlaceToLookAt(
                place="the table",
                depth_is_returned=isinstance(detector, MeasureTheDepth),
            )
            for detector in detectors
        ],
        targets=list(detectors),
        expert=Expert(
            interface=FunctionInterface(
                answer_function=state_the_detectors_own_condition
            )
        ),
    )
    return rules


def test_the_statement_says_what_is_described_and_what_is_left_open():
    rules = EQLSingleClassRDR.from_underspecified(a(PlaceToLookAt)(detector=...))

    assert rules.case_type is PlaceToLookAt
    assert rules.conclusion_attribute_name == "detector"


def test_the_rules_conclude_the_detector_whose_condition_holds():
    depth, colors = MeasureTheDepth(), ReadTheColors()
    rules = _rules_over(depth, colors)

    assert (
        rules.classify(PlaceToLookAt(place="the table", depth_is_returned=True))
        is depth
    )
    assert (
        rules.classify(PlaceToLookAt(place="the table", depth_is_returned=False))
        is colors
    )


def test_rules_concluding_a_detector_are_kept_wherever_the_saver_says():
    """
    A rule concludes the detector itself rather than a name for one, and the engine
    writes a model file as source that can spell a number or an enum member but not a
    collaborator, so where the rules are kept is the caller's to say.
    """
    saver = NullModelSaver()

    rules = EQLSingleClassRDR.from_underspecified(
        a(PlaceToLookAt)(detector=...), model_saver=saver
    )

    assert rules.model_saver is saver
