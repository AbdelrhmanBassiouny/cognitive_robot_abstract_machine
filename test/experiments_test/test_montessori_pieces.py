"""
Tests for the colour a known piece is drawn in, from the hue measured off the real one.
"""

from __future__ import annotations

import numpy as np

from experiments.montessori.pieces import (
    HUE_RANGE,
    KNOWN_PIECE_BY_CATEGORY,
    KnownPiece,
    hue_distance,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.world_description.geometry import Color

# %% reading a piece's colour


def test_a_piece_is_coloured_the_pure_form_of_the_hue_it_was_measured_at():
    scarlet = KnownPiece(
        category=MontessoriShapeCategory.CUBE,
        outline=np.zeros((0, 2)),
        height=0.03,
        hue=0,
        rotation_period=None,
    )

    assert scarlet.color == Color(1.0, 0.0, 0.0)


def test_two_pieces_measured_at_one_hue_are_coloured_alike():
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    cylinder = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CYLINDER]
    rectangular_prism = KNOWN_PIECE_BY_CATEGORY[
        MontessoriShapeCategory.RECTANGULAR_PRISM
    ]

    assert cube.color == cylinder.color
    assert cube.color != rectangular_prism.color


def test_hue_is_measured_the_short_way_round_the_colour_circle():
    assert hue_distance(2, HUE_RANGE - 3) == 5
    assert hue_distance(20, 25) == 5
