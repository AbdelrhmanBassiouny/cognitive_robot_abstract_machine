"""
Tests for what a look expects to find, where it believes it to be, and what suggested
it.
"""

from __future__ import annotations

import math

import pytest
from typing_extensions import List

from experiments.montessori.perception.hypotheses import (
    BeliefSource,
    BelievedPlace,
    PieceHypothesis,
    YawInterval,
)
from experiments.montessori.pieces import (
    CYAN_HUE,
    HUE_RANGE,
    HUE_TOLERANCE,
    KNOWN_PIECES,
    KNOWN_PIECE_BY_CATEGORY,
    YELLOW_HUE,
    hue_distance,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName

# %% the surface these tests believe things to be resting on

A_SURFACE = PrefixedName("table", "hypotheses_test")
"""
What the world is taken to call the surface these tests place their beliefs on.
"""


def place_at(x: float, y: float, **believed) -> BelievedPlace:
    """
    A place on this test module's own surface.

    :param x: Where along the world frame's x-axis it is, in metres.
    :param y: Where along the world frame's y-axis it is, in metres.
    :param believed: Whatever else is believed about it.
    """
    return BelievedPlace(surface=A_SURFACE, center=(x, y), **believed)


def gaps_between(turns: List[float]) -> List[float]:
    """
    How far apart consecutive turns stand.

    :param turns: The turns, in the order they are tried.
    """
    return [later - earlier for earlier, later in zip(turns, turns[1:])]


# %% which way a thing is believed to be turned


def test_an_interval_of_yaw_holds_the_turns_it_spans_and_no_others():
    believed = YawInterval(center=math.radians(30), spread=math.radians(10))

    assert believed.holds(math.radians(30))
    assert believed.holds(math.radians(21))
    assert not believed.holds(math.radians(19))
    assert not believed.holds(math.radians(41))


def test_the_turns_worth_trying_reach_both_ends_of_the_interval():
    believed = YawInterval(center=math.radians(30), spread=math.radians(10))
    step = math.radians(5)

    turns = believed.turns(step)

    assert min(turns) == pytest.approx(believed.center - believed.spread)
    assert max(turns) == pytest.approx(believed.center + believed.spread)
    assert gaps_between(turns) == pytest.approx([step] * (len(turns) - 1))


def test_an_interval_narrower_than_one_step_is_tried_at_its_own_centre():
    believed = YawInterval(center=math.radians(30), spread=math.radians(1))

    assert believed.turns(math.radians(5)) == [believed.center]


# %% how widely a place is searched


def test_a_place_believed_without_a_measure_of_its_own_reaches_the_seeding_distance():
    close = place_at(0.6, 0.2, radius=0.002)

    assert place_at(0.6, 0.2).radius > close.radius


# %% the turns a piece believed at a place is tried at


@pytest.mark.parametrize(
    "piece",
    [piece for piece in KNOWN_PIECES if piece.rotation_period is not None],
    ids=lambda piece: str(piece.category),
)
def test_a_piece_believed_turned_no_particular_way_is_tried_through_its_own_period(
    piece,
):
    step = math.radians(6)

    turns = PieceHypothesis(
        place=place_at(0.6, 0.2), source=BeliefSource.ASKED_FOR
    ).turns_of(piece, step)

    assert min(turns) == pytest.approx(-piece.rotation_period / 2, abs=step)
    assert max(turns) == pytest.approx(piece.rotation_period / 2, abs=step)


def test_a_piece_no_turn_changes_is_tried_at_one_turn_only():
    cylinder = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CYLINDER]
    hypothesis = PieceHypothesis(
        place=place_at(0.6, 0.2), source=BeliefSource.ASKED_FOR
    )

    assert cylinder.rotation_period is None
    assert hypothesis.turns_of(cylinder, math.radians(6)) == [0.0]


def test_a_piece_believed_turned_one_way_is_tried_only_around_that_turn():
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    believed = YawInterval(center=math.radians(30), spread=math.radians(4))

    turns = PieceHypothesis(
        place=place_at(0.6, 0.2, yaw=believed),
        source=BeliefSource.BODY_IN_THE_WORLD,
    ).turns_of(cube, math.radians(2))

    assert all(believed.holds(turn) for turn in turns)
    assert turns == believed.turns(math.radians(2))


# %% what a colour seen at a place suggests is there


def test_a_colour_suggests_the_pieces_that_wear_it():
    hypothesis = PieceHypothesis.of_color(place_at(0.6, 0.2), CYAN_HUE)

    assert set(hypothesis.candidates) == {
        piece
        for piece in KNOWN_PIECES
        if hue_distance(CYAN_HUE, piece.hue) <= HUE_TOLERANCE
    }


def test_a_colour_suggests_nothing_where_no_piece_wears_it():
    unworn = (CYAN_HUE + YELLOW_HUE) // 2

    assert PieceHypothesis.of_color(place_at(0.6, 0.2), unworn).candidates == ()


def test_a_place_whose_colour_could_not_be_read_expects_every_piece():
    hypothesis = PieceHypothesis.of_color(place_at(0.6, 0.2), None)

    assert hypothesis.candidates == KNOWN_PIECES
    assert hypothesis.hue is None


def test_a_hypothesis_records_the_colour_that_suggested_it():
    hypothesis = PieceHypothesis.of_color(place_at(0.6, 0.2), YELLOW_HUE)

    assert hypothesis.hue == YELLOW_HUE
    assert hypothesis.source is BeliefSource.COLOR_IN_THE_PICTURE


def test_a_colour_is_read_the_short_way_round_the_circle_when_it_suggests_pieces():
    just_below_zero = (CYAN_HUE - HUE_TOLERANCE) % HUE_RANGE
    wrapping = (just_below_zero - CYAN_HUE) % HUE_RANGE

    assert (
        PieceHypothesis.of_color(
            place_at(0.6, 0.2), (CYAN_HUE + wrapping) % HUE_RANGE
        ).candidates
        == PieceHypothesis.of_color(place_at(0.6, 0.2), CYAN_HUE).candidates
    )


# %% what is believed without a colour to suggest it


def test_a_belief_with_no_colour_behind_it_expects_every_known_piece():
    hypothesis = PieceHypothesis(
        place=place_at(0.6, 0.2), source=BeliefSource.ASKED_FOR
    )

    assert hypothesis.candidates == KNOWN_PIECES
    assert hypothesis.hue is None


def test_a_belief_may_name_the_one_piece_it_expects():
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]

    hypothesis = PieceHypothesis(
        place=place_at(0.6, 0.2),
        source=BeliefSource.BODY_IN_THE_WORLD,
        candidates=(cube,),
    )

    assert hypothesis.candidates == (cube,)
