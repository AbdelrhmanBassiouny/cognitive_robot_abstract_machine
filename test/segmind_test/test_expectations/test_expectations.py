"""
Tests for what is expected of a thing after something has acted on it, stated in the
digital twin's own relation vocabulary, and for what is reported when a look finds
something else.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import a, an
from krrood.entity_query_language.query.match import Match
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
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from ..dataset.plate_with_a_hole import (
    CUBE_COLOR,
    HoleScene,
    cube_in_the_hole,
    cube_lifted_clear_of_the_hole,
    cube_on_the_plate_over_the_hole,
    named,
)
from ..dataset.stated_relations import says

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

    assert says(
        expected.holds,
        an(InsideRegion)(region=scene.hole),
        a(Near)(place=scene.hole, radius=RELEASE_SPREAD),
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

    assert SupportedBy not in [stated.type for stated in expected.holds]
    assert not SupportedBy(scene.cube, scene.plate)()


def test_a_thing_nothing_has_acted_on_is_expected_nowhere(expectations: Expectations):
    assert expectations.of(cube_in_the_hole().cube) is None


def test_an_expectation_is_read_back_by_the_annotation_about_the_thing(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    expected = release_the_cube(expectations, scene, declared)

    assert expectations.of_annotation(SomethingAbout(root=scene.cube)) is expected


# %% an expectation is a statement about the thing it is expected of


def test_an_expectation_is_a_statement_over_the_subjects_own_kind(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    """
    An expectation is an ordinary statement: a match over the kind of thing the subject
    is, ranging over that one thing, with what is expected of it as its conditions.
    """
    scene = cube_in_the_hole()

    expected = release_the_cube(expectations, scene, declared)

    assert isinstance(expected, Match)
    assert expected.type is type(scene.cube)
    assert expected.domain == [scene.cube]
    assert len(expected._where_conditions_) == len(expected.holds)


def test_an_expectation_is_answered_by_the_world_where_it_holds_of_it(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    """
    The same statement a look is asked can be asked of the world the robot already has,
    which is what says whether what was expected is true of the thing as it now stands.
    """
    expected = release_the_cube(expectations, cube_in_the_hole(), declared)

    assert expected.holds_now()


def test_an_expectation_the_world_contradicts_does_not_hold_of_it(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    """
    A cube lying on the plate over the hole is not in it, and the statement says so
    without a look being taken at all.
    """
    scene = cube_on_the_plate_over_the_hole()

    expected = release_the_cube(expectations, scene, declared)

    assert not expected.holds_now()


# %% what the events do to a belief


def test_an_event_moves_the_belief_by_what_it_says_holds(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    scene = cube_in_the_hole()
    release_the_cube(expectations, scene, declared)
    table = Body(name=named("table"))

    expectations.record(SupportEvent(tracked_object=scene.cube, with_object=table))

    assert expectations.of(scene.cube).expects(an(SupportedBy)(supporting=table))
    assert expectations.of(scene.cube).expects(an(InsideRegion)(region=scene.hole))


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

    assert [stated.type for stated in expectations.of(scene.cube).holds] == [Near]


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
    assert says(
        request.stated_relations,
        *expected.holds,
        a(Colored)(color=CUBE_COLOR),
    )


def test_a_thing_drawn_in_several_colours_is_not_looked_for_by_colour(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    """
    Which of its colours to search for is not a choice this can take: a look narrowed to
    one of them would pass over the thing wearing the other, so it says all of them and
    narrows by none.
    """
    other = Color(R=0.9, G=0.6, B=0.0)
    two_toned = Body.from_shape_collection(
        named("two_toned"),
        ShapeCollection(
            [
                Box(scale=Scale(0.05, 0.05, 0.05), color=CUBE_COLOR),
                Box(scale=Scale(0.05, 0.05, 0.05), color=other),
            ]
        ),
    )

    expected = expectations.expect(two_toned, (), declared)

    assert expected.colors == (CUBE_COLOR, other)
    assert expected.look_request(Body).stated_relations == []


def test_a_thing_drawn_in_no_colour_is_looked_for_by_its_relations_alone(
    expectations: Expectations, declared: SomethingThatDeclaredAnEffect
):
    bare = Body(name=named("bare"))
    expected = expectations.expect(bare, (), declared)

    assert expected.colors == ()
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
