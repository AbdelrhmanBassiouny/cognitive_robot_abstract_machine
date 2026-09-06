"""
Tests for a detector stating which looks it can answer, and for rules choosing among
detectors by those statements.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.backends import Look
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.rdr.serialization import NullModelSaver
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.query.query import Query

from ..dataset.detectors_that_state_what_they_answer import (
    MeasureTheDepth,
    NoDetectorAnswersThePlace,
    PlaceToLookAt,
    ReadTheColors,
    WhereEachDetectorIsWorthItsCostRules,
    WhereToLookRules,
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


def test_the_statement_says_what_is_described_and_what_is_left_open():
    rules = EQLSingleClassRDR.from_underspecified(a(PlaceToLookAt)(detector=...))

    assert rules.case_type is PlaceToLookAt
    assert rules.conclusion_attribute_name == "detector"


def test_the_rules_conclude_the_detector_whose_condition_holds():
    rules = WhereToLookRules()

    assert (
        rules.detector_for(PlaceToLookAt(place="the table", depth_is_returned=True))
        is rules.depth
    )
    assert (
        rules.detector_for(PlaceToLookAt(place="the table", depth_is_returned=False))
        is rules.colors
    )


def test_the_rules_a_family_starts_with_need_no_case_to_be_derived_from():
    """
    Each is the detector's own capability, stated over the variable the rules range
    over, so nothing has to be invented for the engine to read a rule off.
    """
    rules = WhereToLookRules()

    assert [rule.conclusion for rule in rules.rules_stated_at_the_start()] == [
        rules.depth,
        rules.colors,
    ]


def test_a_look_no_rule_reaches_is_refused_in_the_familys_own_words():
    rules = WhereEachDetectorIsWorthItsCostRules()

    with pytest.raises(NoDetectorAnswersThePlace):
        rules.detector_for(PlaceToLookAt(place=""))


def test_the_rules_can_be_read_as_a_tree():
    rules = WhereToLookRules()

    rendered = rules.render_tree(
        PlaceToLookAt(place="the table", depth_is_returned=True)
    )

    assert type(rules.depth).__name__ in rendered


# %% rules that add their own knowledge to what a detector says


def test_a_detector_both_answer_is_chosen_by_where_the_rules_say_it_is_worth_running():
    """
    Both detectors declare they answer a look at a named place with depth, so a
    capability alone leaves the choice open and the rules' own knowledge settles it --
    for the place a rule was stated for, and nowhere else.
    """
    rules = WhereEachDetectorIsWorthItsCostRules()

    rules.add_rule(PlaceToLookAt(place="the shelf"), rules.depth)

    assert rules.detector_for(PlaceToLookAt(place="the shelf")) is rules.depth
    assert rules.detector_for(PlaceToLookAt(place="the sink")) is rules.edges


def test_the_situation_a_rule_is_stated_in_is_read_off_the_look_it_was_stated_from():
    """
    Which situation a detector is preferred in is a property of the look the rule is
    being stated from, so a place nobody foresaw gets a rule of its own rather than the
    condition of the place that happened to come first.
    """
    rules = WhereEachDetectorIsWorthItsCostRules()
    rules.add_rule(PlaceToLookAt(place="the shelf"), rules.depth)

    rules.add_rule(PlaceToLookAt(place="the windowsill"), rules.depth)

    assert rules.detector_for(PlaceToLookAt(place="the windowsill")) is rules.depth
    assert rules.detector_for(PlaceToLookAt(place="the shelf")) is rules.depth


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
