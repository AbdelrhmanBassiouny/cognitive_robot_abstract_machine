"""
Tests for the rule that nothing is reported in a place another thing already occupies.
"""

from __future__ import annotations

import numpy as np
import pytest
from typing_extensions import List

from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.perception.footprint import Footprint
from experiments.montessori.perception.hypotheses import (
    BelievedPlace,
    PieceHypothesis,
)
from experiments.montessori.perception.exceptions import NothingIsHiddenFromBelow
from experiments.montessori.perception.occupancy import Occupancy, OccupiedVolume
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Pose

from .dataset.montessori_belief_sources import SomethingThatAskedForALook

WHOEVER_ASKED = SomethingThatAskedForALook()
"""
The source these tests hand the beliefs behind the detections they build by hand.
"""

# %% building volumes and detections to test the rule against

PIECE_WIDTH = 0.04
"""
Edge length, in metres, of the square outlines these tests place against one another.
"""


def square_at(x: float, y: float, width: float = PIECE_WIDTH) -> np.ndarray:
    """
    A square outline centred on a position, in world-frame metres.

    :param x: Centre along the world frame's x-axis, in metres.
    :param y: Centre along the world frame's y-axis, in metres.
    :param width: Edge length of the square, in metres.
    """
    half = width / 2
    return np.array(
        [
            [x - half, y - half],
            [x + half, y - half],
            [x + half, y + half],
            [x - half, y + half],
        ]
    )


def volume_at(
    x: float, y: float, bottom: float, top: float, width: float = PIECE_WIDTH
) -> OccupiedVolume:
    """
    The space a square-based thing takes up.

    :param x: Centre along the world frame's x-axis, in metres.
    :param y: Centre along the world frame's y-axis, in metres.
    :param bottom: Height of the surface it rests on, in metres.
    :param top: Height of its own top, in metres.
    :param width: Edge length of its outline, in metres.
    """
    return OccupiedVolume(outline=square_at(x, y, width), bottom=bottom, top=top)


def piece_at(
    x: float, y: float, surface_height: float, outline_agreement: float
) -> DetectedMontessoriShape:
    """
    A cube detection standing at a position, fitted as well as the caller says.

    :param x: Centre along the world frame's x-axis, in metres.
    :param y: Centre along the world frame's y-axis, in metres.
    :param surface_height: Height of the surface it was found resting on, in metres.
    :param outline_agreement: How much of its outline lay along a seen edge.
    """
    height = 0.03
    resting_on = PrefixedName("table", "occupancy_test")
    return DetectedMontessoriShape(
        pose=Pose.from_xyz_rpy(x, y, surface_height + height / 2),
        footprint=Footprint(
            area=PIECE_WIDTH**2,
            width=PIECE_WIDTH,
            length=PIECE_WIDTH,
            fill_ratio=1.0,
            corner_count=4,
            yaw=0.0,
        ),
        outline=square_at(x, y),
        category=MontessoriShapeCategory.CUBE,
        supporting_surface=resting_on,
        height=height,
        outline_agreement=outline_agreement,
        hypothesis=PieceHypothesis(
            place=BelievedPlace(surface=resting_on, center=PlanarPoint(x, y)),
            source=WHOEVER_ASKED,
        ),
    )


# %% one volume against another


def test_a_volume_takes_up_the_place_it_stands_in():
    volume = volume_at(0.6, 0.2, bottom=0.88, top=0.91)

    assert volume.overlaps(volume)


def test_two_things_at_the_same_place_and_different_heights_do_not_share_it():
    below = volume_at(0.6, 0.2, bottom=0.88, top=0.96)
    above = volume_at(0.6, 0.2, bottom=0.96, top=0.99)

    assert not below.overlaps(above)
    assert not above.overlaps(below)


def test_a_thing_reaching_into_another_thing_shares_its_place():
    board = volume_at(0.8, 0.03, bottom=0.88, top=0.96, width=0.15)
    inside_it = volume_at(0.8, 0.03, bottom=0.88, top=0.91)

    assert board.overlaps(inside_it)
    assert inside_it.overlaps(board)


def test_two_things_side_by_side_each_have_their_own_place():
    left = volume_at(0.6, 0.20, bottom=0.88, top=0.91)
    right = volume_at(0.6, 0.20 + PIECE_WIDTH, bottom=0.88, top=0.91)

    assert not left.overlaps(right)


def test_two_things_standing_into_one_another_share_one_place():
    left = volume_at(0.6, 0.20, bottom=0.88, top=0.91)
    right = volume_at(0.6, 0.20 + PIECE_WIDTH / 2, bottom=0.88, top=0.91)

    assert left.overlaps(right)


def test_a_thing_lying_flat_in_a_surface_takes_up_no_place_in_it():
    hole = volume_at(0.8, 0.03, bottom=0.96, top=0.96)
    lid = volume_at(0.8, 0.03, bottom=0.88, top=0.96, width=0.15)

    assert not hole.overlaps(lid)


def test_a_detection_takes_up_the_space_between_its_surface_and_its_own_top():
    piece = piece_at(0.6, 0.2, surface_height=0.88, outline_agreement=0.9)

    volume = OccupiedVolume.of(piece)

    assert volume.bottom == pytest.approx(piece.surface_height)
    assert volume.top == pytest.approx(piece.top_height)


# %% giving a place to one thing at a time


def test_the_first_thing_to_ask_for_a_free_place_gets_it():
    occupancy = Occupancy()

    assert occupancy.claim(volume_at(0.6, 0.2, bottom=0.88, top=0.91))


def test_a_place_already_held_is_refused_to_whatever_asks_next():
    occupancy = Occupancy()
    occupancy.claim(volume_at(0.6, 0.2, bottom=0.88, top=0.91))

    assert not occupancy.claim(volume_at(0.6, 0.2, bottom=0.88, top=0.91))


def test_a_refused_thing_does_not_take_the_place_it_was_refused():
    occupancy = Occupancy()
    held = volume_at(0.6, 0.2, bottom=0.88, top=0.91)
    occupancy.claim(held)
    occupancy.claim(volume_at(0.6, 0.2, bottom=0.88, top=0.91))

    assert occupancy.taken == [held]


# %% one detection per place


def test_the_better_fitted_of_two_detections_in_one_place_is_the_one_kept():
    poorly_fitted = piece_at(0.60, 0.20, surface_height=0.88, outline_agreement=0.66)
    well_fitted = piece_at(0.61, 0.20, surface_height=0.88, outline_agreement=0.94)

    kept = Occupancy().keep_one_detection_per_place([poorly_fitted, well_fitted])

    assert kept == [well_fitted]


def test_detections_in_places_of_their_own_are_all_kept():
    pieces = [
        piece_at(0.60, 0.20, surface_height=0.88, outline_agreement=0.9),
        piece_at(0.70, 0.20, surface_height=0.88, outline_agreement=0.8),
        piece_at(0.60, 0.30, surface_height=0.88, outline_agreement=0.7),
    ]

    assert Occupancy().keep_one_detection_per_place(pieces) == pieces


def test_a_detection_standing_in_a_place_already_taken_is_dropped():
    board = volume_at(0.80, 0.03, bottom=0.88, top=0.96, width=0.15)
    occupancy = Occupancy()
    occupancy.claim(board)
    on_the_lid = piece_at(0.80, 0.03, surface_height=0.96, outline_agreement=0.66)
    inside_the_board = piece_at(0.80, 0.03, surface_height=0.88, outline_agreement=0.94)

    kept = occupancy.keep_one_detection_per_place([on_the_lid, inside_the_board])

    assert kept == [on_the_lid]


def test_the_kept_detections_keep_the_order_they_were_offered_in():
    first = piece_at(0.60, 0.20, surface_height=0.88, outline_agreement=0.7)
    second = piece_at(0.70, 0.20, surface_height=0.88, outline_agreement=0.9)

    kept: List[DetectedMontessoriShape] = Occupancy().keep_one_detection_per_place(
        [first, second]
    )

    assert kept == [first, second]


# %% what a raised thing keeps the camera from seeing


CAMERA_ABOVE_THE_TABLE = np.array([0.41, -0.05, 1.82])
"""
Where the camera stood over the shipped captures, as world-frame ``(x, y, z)`` in
metres.
"""


def test_what_a_raised_thing_hides_reaches_from_the_lower_surface_up_to_its_own_base():
    lid = volume_at(0.8, 0.03, bottom=0.96, top=0.99, width=0.11)

    hidden = lid.hides(0.88, CAMERA_ABOVE_THE_TABLE)

    assert hidden.bottom == pytest.approx(0.88)
    assert hidden.top == pytest.approx(0.96)


def test_what_a_raised_thing_hides_covers_the_ground_it_stands_on():
    lid = volume_at(0.8, 0.03, bottom=0.96, top=0.99, width=0.11)

    hidden = lid.hides(0.88, CAMERA_ABOVE_THE_TABLE)

    assert hidden.shared_area(lid) == pytest.approx(lid.area, rel=1e-3)


def test_what_a_raised_thing_hides_reaches_away_from_the_camera():
    lid = volume_at(0.8, 0.03, bottom=0.96, top=0.99, width=0.11)

    hidden = lid.hides(0.88, CAMERA_ABOVE_THE_TABLE)

    away_from_the_camera = np.asarray(hidden.outline) - CAMERA_ABOVE_THE_TABLE[:2]
    reach = np.linalg.norm(away_from_the_camera, axis=1).max()
    to_the_lid = np.linalg.norm(
        np.asarray(lid.outline) - CAMERA_ABOVE_THE_TABLE[:2], axis=1
    ).max()
    assert reach > to_the_lid


def test_a_piece_seen_against_the_ground_a_raised_thing_hides_loses_its_place():
    lid = volume_at(0.8, 0.03, bottom=0.96, top=0.99, width=0.11)
    hidden = lid.hides(0.88, CAMERA_ABOVE_THE_TABLE)
    behind_it = OccupiedVolume(
        outline=np.asarray(hidden.outline).mean(axis=0) + square_at(0.0, 0.0),
        bottom=0.88,
        top=0.91,
    )

    assert hidden.overlaps(behind_it)


def test_a_piece_standing_on_the_raised_thing_keeps_its_place():
    lid = volume_at(0.8, 0.03, bottom=0.96, top=0.99, width=0.11)
    hidden = lid.hides(0.88, CAMERA_ABOVE_THE_TABLE)
    on_the_lid = volume_at(0.8, 0.03, bottom=0.96, top=0.99)

    assert not hidden.overlaps(on_the_lid)


def test_a_camera_that_does_not_look_down_on_a_thing_is_refused():
    lid = volume_at(0.8, 0.03, bottom=0.96, top=0.99, width=0.11)

    with pytest.raises(NothingIsHiddenFromBelow):
        lid.hides(0.88, np.array([0.41, -0.05, 0.5]))
