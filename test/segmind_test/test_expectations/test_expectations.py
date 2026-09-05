"""
Tests for what is expected of a thing after something has acted on it, stated in the
digital twin's own relation vocabulary, and for what is reported when a look finds
something else.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.backends import StatedRelation
from krrood.patterns.belief_source import BeliefSource
from segmind.datastructures.events import (
    PickUpEvent,
    SupportEvent,
    TranslationEvent,
)
from segmind.expectations import Expectation, Expectations
from semantic_digital_twin.reasoning.predicates import (
    Colored,
    InsideRegion,
    Near,
    SupportedBy,
)
from semantic_digital_twin.semantic_annotations.mixins import HasRootBody
from semantic_digital_twin.world_description.world_entity import Body

from ..dataset.plate_with_a_hole import (
    CUBE_COLOR,
    HoleScene,
    cube_in_the_hole,
    cube_lifted_clear_of_the_hole,
    cube_on_the_plate_over_the_hole,
    named,
)

RELEASE_SPREAD = 0.03
"""
How far from a hole a released thing may come to rest, in metres, for these tests.
"""


class SomethingThatDeclaredAnEffect(BeliefSource):
    """
    Whatever declared the effect, standing in for the action that did.
    """


@dataclass(eq=False)
class SomethingAbout(HasRootBody):
    """
    Any annotation the world makes about a body, standing in for a piece's own.
    """


@pytest.fixture
def declared() -> SomethingThatDeclaredAnEffect:
    return SomethingThatDeclaredAnEffect()


@pytest.fixture
def expectations() -> Expectations:
    return Expectations(release_spread=RELEASE_SPREAD)


def release_the_cube(
    expectations: Expectations, scene: HoleScene, source: BeliefSource
) -> Expectation:
    """
    Arm the expectation an insertion declares.

    :param expectations: What is expected.
    :param scene: The world the cube was released in.
    :param source: What declared the effect.
    """
    return expectations.released_over(scene.cube, scene.hole, source)


# %% what an insertion's declared effect believes


def test_a_thing_released_over_a_hole_is_expected_in_it_within_the_spread(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    """
    The insertion's own promise, armed before any event confirms it: in the hole's
    region, no further from the hole than a release scatters.
    """
    scene = cube_in_the_hole()

    expected = release_the_cube(expectations, scene, declared)

    assert expected.holds == (
        StatedRelation.of(InsideRegion, scene.hole),
        StatedRelation.of(Near, scene.hole, radius=RELEASE_SPREAD),
    )
    assert expected.subject is scene.cube
    assert expected.source is declared


def test_a_thing_that_went_into_a_hole_is_not_expected_to_rest_on_what_the_hole_is_cut_in(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    """
    A cube sunk in its hole rests on whatever lies under the hole, and the world's own
    reading of support says so: expecting the plate would contradict the insertion's
    success.
    """
    scene = cube_in_the_hole()

    expected = release_the_cube(expectations, scene, declared)

    assert SupportedBy not in [stated.relation_type for stated in expected.holds]
    assert not SupportedBy(scene.cube, scene.plate)()


def test_a_thing_nothing_has_acted_on_is_expected_nowhere(expectations: Expectations):
    assert expectations.of(cube_in_the_hole().cube) is None


def test_an_expectation_is_read_back_by_the_annotation_about_the_thing(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    expected = release_the_cube(expectations, scene, declared)

    assert expectations.of_annotation(SomethingAbout(root=scene.cube)) is expected


# %% what the events do to a belief


def test_an_event_moves_the_belief_by_what_it_says_holds(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    release_the_cube(expectations, scene, declared)
    table = Body(name=named("table"))

    expectations.record(SupportEvent(tracked_object=scene.cube, with_object=table))

    assert StatedRelation.of(SupportedBy, table) in expectations.of(scene.cube).holds
    assert StatedRelation.of(InsideRegion, scene.hole) in (
        expectations.of(scene.cube).holds
    )


def test_a_pick_up_that_lifts_the_thing_out_of_the_hole_ends_its_being_in_it(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    """
    The belief about the region is checked against where the thing now is rather than
    dropped on the event's say-so.
    """
    scene = cube_lifted_clear_of_the_hole()
    release_the_cube(expectations, scene, declared)

    expectations.record(PickUpEvent(tracked_object=scene.cube))

    assert [stated.relation_type for stated in expectations.of(scene.cube).holds] == [
        Near
    ]


def test_a_belief_only_decays_when_something_acts_on_that_thing(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    before = release_the_cube(expectations, scene, declared)

    expectations.record(PickUpEvent(tracked_object=Body(name=named("another"))))

    assert expectations.of(scene.cube) == before


def test_an_event_that_states_no_effect_leaves_the_belief_alone(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    before = release_the_cube(expectations, scene, declared)

    expectations.record(TranslationEvent(tracked_object=scene.cube))

    assert expectations.of(scene.cube) == before


def test_an_event_about_a_thing_nothing_is_expected_of_changes_nothing(
    expectations: Expectations,
):
    scene = cube_in_the_hole()

    expectations.record(
        SupportEvent(tracked_object=scene.cube, with_object=scene.plate)
    )

    assert expectations.of(scene.cube) is None


# %% how an expectation reaches a look


def test_a_look_is_asked_for_the_expected_relations_and_the_colour_the_thing_is_drawn_in(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    expected = release_the_cube(expectations, scene, declared)

    [request] = expectations.look_requests(Body)

    assert request.type_ is Body
    assert request.stated_relations == [
        *expected.holds,
        StatedRelation.of(Colored, CUBE_COLOR),
    ]


def test_a_thing_drawn_in_no_colour_is_looked_for_by_its_relations_alone(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    bare = Body(name=named("bare"))
    expected = expectations.expect(bare, (), declared)

    assert expected.color is None
    assert expected.look_request(Body).stated_relations == []


# %% what a look that differs from the expectation reports


def test_a_thing_found_where_it_was_promised_meets_the_expectation(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    expected = release_the_cube(expectations, scene, declared)

    report = expected.check(scene.cube)

    assert report.holds
    assert report.violated == ()


def test_a_thing_found_over_the_hole_rather_than_in_it_violates_being_in_it(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_on_the_plate_over_the_hole()
    expected = release_the_cube(expectations, scene, declared)

    report = expected.check(scene.cube)

    assert [type(violated) for violated in report.violated] == [InsideRegion]
    assert report.violated[0].body is scene.cube


def test_finding_nothing_where_the_action_promised_is_its_own_outcome(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    expected = release_the_cube(expectations, cube_in_the_hole(), declared)

    report = expected.check(None)

    assert not report.holds
    assert report.nothing_was_found
    assert report.violated == ()
