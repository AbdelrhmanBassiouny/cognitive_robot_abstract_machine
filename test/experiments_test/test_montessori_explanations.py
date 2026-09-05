"""
Tests for deciding what is there by comparing the accounts of a place, rather than by
measuring one of them against a level.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest
from typing_extensions import Tuple

from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.explanations import (
    NOTHING_EXPLAINED,
    BoardOutlines,
    CompetingExplanations,
    Explanation,
    PlaceInThePicture,
)
from experiments.montessori.perception.orthophoto import Orthophoto, WorkspaceRegion

DRAWN_SURFACE_COLOR = (60, 60, 60)
"""
Blue, green and red of the bare surface these tests draw an outline onto.
"""

DRAWN_FACE_COLOR = (200, 220, 230)
"""
Blue, green and red of the face they draw.
"""

REACH = 0.003
"""
How far, in metres, an outline and an edge may lie apart and still count as one here.

The reach the fit itself reads at
(:attr:`~experiments.montessori.perception.outline_fit.OutlineFitter.reach`).
"""

OUTLINE_SPACING = 0.002
"""
How far apart, in metres, the points an outline is read at stand here.
"""

SQUARE_WIDTH = 0.04
"""
Edge length, in metres, of the square face these tests draw.
"""


def square(width: float = SQUARE_WIDTH) -> np.ndarray:
    """
    A square outline about its own centre.

    :param width: Its edge length, in metres.
    """
    half = width / 2
    return np.array([[-half, -half], [half, -half], [half, half], [-half, half]])


def drawn(
    outline: np.ndarray, center: Tuple[float, float] = (0.0, 0.0)
) -> EdgeDistances:
    """
    The edges of a rectified view holding one filled outline on a bare surface.

    :param outline: The outline to draw, as ``(n, 2)`` ``(x, y)`` points in metres about
        its own centre.
    :param center: Where in the world frame to draw it, in metres.
    """
    reach = 0.1
    region = WorkspaceRegion(
        minimum_x=center[0] - reach,
        maximum_x=center[0] + reach,
        minimum_y=center[1] - reach,
        maximum_y=center[1] + reach,
    )
    image = np.zeros((region.height_in_pixels, region.width_in_pixels, 3), np.uint8)
    image[:, :] = DRAWN_SURFACE_COLOR
    corners = np.stack(
        [
            (outline[:, 0] + center[0] - region.minimum_x) / region.resolution,
            (outline[:, 1] + center[1] - region.minimum_y) / region.resolution,
        ],
        axis=1,
    )
    cv2.fillPoly(image, [np.round(corners).astype(np.int32)], DRAWN_FACE_COLOR)
    return EdgeDistances.of(Orthophoto(image=image, region=region, plane_height=0.0))


def place_around(outline: np.ndarray, edges: EdgeDistances) -> PlaceInThePicture:
    """
    The place one outline stands in, in a view whose edges are known.

    :param outline: The outline that raises the place, as ``(n, 2)`` world-frame points.
    :param edges: The edges seen in that view.
    """
    return PlaceInThePicture.around(
        outline, edges, edges.positions, REACH, OUTLINE_SPACING
    )


# %% an account read from both sides


def test_an_account_is_held_to_whichever_side_it_is_weaker_on():
    """
    Their harmonic mean, so following the edges perfectly buys nothing while most of
    what is there is left unaccounted for.
    """
    lopsided = Explanation(outline_followed=1.0, edges_accounted_for=0.2)

    assert lopsided.strength == pytest.approx(2 * 1.0 * 0.2 / 1.2)
    assert lopsided.strength < min(
        Explanation(outline_followed=0.6, edges_accounted_for=0.6).strength,
        lopsided.outline_followed,
    )


def test_an_account_equally_good_on_both_sides_is_exactly_that_strong():
    assert Explanation(
        outline_followed=0.44, edges_accounted_for=0.44
    ).strength == pytest.approx(0.44)


def test_the_account_that_says_nothing_is_there_explains_nothing():
    assert NOTHING_EXPLAINED.strength == 0.0


def test_an_outline_claimed_where_the_picture_holds_no_edge_is_not_rewarded_for_it():
    edges = drawn(square())
    over_the_edges = place_around(square(), edges)

    laid_where_nothing_is = over_the_edges.explained_by(
        square() + np.array([0.05, 0.05])
    )

    assert laid_where_nothing_is.outline_followed == pytest.approx(0.0)
    assert laid_where_nothing_is.strength == pytest.approx(0.0)


def test_an_account_that_leaves_seen_edges_over_is_weaker_than_one_that_covers_them():
    """
    The half a fit's own agreement never asks, and what tells a template laid across
    part of an outline from one that follows the whole of it.
    """
    edges = drawn(square())
    place = place_around(square(), edges)

    whole = place.explained_by(square())
    one_side = place.explained_by(square()[:2])

    assert one_side.edges_accounted_for < whole.edges_accounted_for / 2
    assert one_side.strength < whole.strength


# %% the outlines the board itself produces


def test_an_outline_below_a_plane_is_cast_onto_it_away_from_the_camera():
    """
    A rectification onto a plane above the board puts the board's own edges where the
    camera sees them against it, which is further from the point under the camera the
    lower they lie.
    """
    camera = np.array([0.0, 0.0, 2.0])
    lying_at, plane_height = 1.0, 1.2
    outline = np.array([[0.5, 0.0], [0.5, 0.4]])

    cast = BoardOutlines.cast_onto([outline], lying_at, plane_height, camera)

    [where] = cast.corners
    assert where == pytest.approx(
        outline * (plane_height - camera[2]) / (lying_at - camera[2])
    )
    assert np.linalg.norm(where, axis=1).max() < np.linalg.norm(outline, axis=1).max()


def test_an_outline_in_the_plane_it_is_read_in_is_cast_onto_itself():
    outline = square()

    cast = BoardOutlines.cast_onto([outline], 1.0, 1.0, np.array([0.0, 0.0, 2.0]))

    [where] = cast.corners
    assert where == pytest.approx(outline)


def test_the_board_accounts_for_an_edge_its_own_geometry_produces():
    edges = drawn(square())
    place = place_around(square(), edges)
    board = BoardOutlines(corners=[square()])

    assert board.account_of(place).strength == pytest.approx(
        place.explained_by(square()).strength
    )


def test_a_board_with_nothing_at_a_place_accounts_for_nothing_there():
    edges = drawn(square())
    place = place_around(square(), edges)
    elsewhere = BoardOutlines(corners=[square() + np.array([0.08, 0.08])])

    assert elsewhere.account_of(place) == NOTHING_EXPLAINED
    assert BoardOutlines().account_of(place) == NOTHING_EXPLAINED


# %% deciding by comparison


def test_an_account_that_explains_next_to_nothing_is_not_reported():
    """
    The account that says nothing is there is always among the rivals, so an account is
    refused for explaining too little without a level being set on it separately.
    """
    rule = CompetingExplanations(required_lead=0.1)
    barely = Explanation(outline_followed=0.05, edges_accounted_for=0.05)

    assert not rule.is_reported(barely)
    assert rule.is_reported(Explanation(outline_followed=0.5, edges_accounted_for=0.5))


def test_an_account_that_does_not_lead_a_rival_is_not_reported():
    rule = CompetingExplanations(required_lead=0.1)
    candidate = Explanation(outline_followed=0.5, edges_accounted_for=0.5)
    within_the_lead = Explanation(outline_followed=0.45, edges_accounted_for=0.45)
    behind_it = Explanation(outline_followed=0.3, edges_accounted_for=0.3)

    assert not rule.is_reported(candidate, within_the_lead)
    assert rule.is_reported(candidate, behind_it)


def test_a_candidate_chosen_from_several_has_more_to_lead_than_one_a_belief_names():
    """
    The plan's own claim as a rule rather than as a description: what a look must show
    to report something rises with the number of accounts of that place it was the best
    of, so a belief naming one piece makes the same evidence go further than an unguided
    look over the whole set.
    """
    rule = CompetingExplanations(required_lead=0.1)
    seen = Explanation(outline_followed=0.5, edges_accounted_for=0.5)
    next_best = Explanation(outline_followed=0.45, edges_accounted_for=0.45)

    assert rule.is_reported(seen)
    assert not rule.is_reported(seen, next_best)


def test_one_account_leads_another_only_by_more_than_the_stated_lead():
    rule = CompetingExplanations(required_lead=0.25)
    ahead = Explanation(outline_followed=0.8, edges_accounted_for=0.8)
    behind = Explanation(outline_followed=0.5, edges_accounted_for=0.5)

    assert rule.leads(ahead, behind)
    assert not rule.leads(behind, ahead)
    assert not rule.leads(
        Explanation(outline_followed=0.7, edges_accounted_for=0.7), behind
    )


def test_a_template_over_part_of_an_outline_loses_to_the_thing_that_made_it():
    """
    The comparison the item exists for, on a drawn scene rather than on a capture: an
    account that sits on real edges the whole of its own length still loses to one that
    covers what is actually there, which is what no level on the following side could
    have said.
    """
    rim = square()
    place = place_around(rim, drawn(rim))
    rule = CompetingExplanations(required_lead=0.1)

    fills_it = place.explained_by(rim)
    lies_along_one_side = place.explained_by(rim[:2])

    assert lies_along_one_side.outline_followed > rule.required_lead
    assert rule.leads(fills_it, lies_along_one_side)
    assert not rule.leads(lies_along_one_side, fills_it)


def test_a_place_is_read_over_the_same_edges_whichever_account_is_asked():
    """
    What makes two accounts comparable: an account read over a wider stretch of picture
    than its rival would be answering a different question.
    """
    edges = drawn(square())
    place = place_around(square(), edges)

    turned = place.explained_by(
        square()
        @ np.array([[math.cos(0.3), math.sin(0.3)], [-math.sin(0.3), math.cos(0.3)]])
    )

    assert place.holds(place.seen_here).shape == place.seen_here.shape
    assert turned.edges_accounted_for < place.explained_by(square()).edges_accounted_for
