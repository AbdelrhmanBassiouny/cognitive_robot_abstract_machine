"""
Tests for the pieces the physical set contains: the colour a piece is drawn in, from the
hue measured off the real one, and telling a measured colour apart from theirs.
"""

from __future__ import annotations

import numpy as np

from experiments.montessori.pieces import HueCircle, KnownPiece, PieceHue, PieceSet
from experiments.montessori.semantics import (
    CubeShape,
    CylinderShape,
    DiskShape,
    RectangularPrismShape,
)
from semantic_digital_twin.world_description.geometry import Color, Polygon2D

# %% reading a piece's colour


def test_a_piece_is_coloured_the_pure_form_of_the_hue_it_was_measured_at():
    scarlet = KnownPiece(
        category=CubeShape,
        outline=Polygon2D(np.zeros((0, 2))),
        height=0.03,
        hue=0,
        rotation_period=None,
    )

    assert scarlet.color == Color(1.0, 0.0, 0.0)


def test_two_pieces_measured_at_one_hue_are_coloured_alike():
    pieces = PieceSet.this_lab()
    cube = pieces.piece_for(CubeShape)
    cylinder = pieces.piece_for(CylinderShape)
    rectangular_prism = pieces.piece_for(RectangularPrismShape)

    assert cube.color == cylinder.color
    assert cube.color != rectangular_prism.color


def test_hue_is_measured_the_short_way_round_the_colour_circle():
    circle = HueCircle()

    assert circle.distance(2, circle.size - 3) == 5
    assert circle.distance(20, 25) == 5


# %% the set the pieces make up


def test_a_kind_of_piece_the_set_has_none_of_is_not_found():
    assert PieceSet.this_lab().piece_for(DiskShape) is None


def test_the_set_wears_each_of_its_measured_hues_once():
    assert PieceSet.this_lab().hues == tuple(sorted(PieceHue))


def test_a_colour_is_taken_for_a_piece_only_within_the_tolerance():
    pieces = PieceSet.this_lab()
    cube = pieces.piece_for(CubeShape)

    assert pieces.could_be(cube, cube.hue + pieces.hue_tolerance)
    assert not pieces.could_be(cube, cube.hue + pieces.hue_tolerance + 1)
    assert pieces.could_be(cube, None)


def test_a_pixel_wears_a_piece_colour_only_near_one_of_the_sets_hues():
    pieces = PieceSet.this_lab()
    hues = np.array(
        [[PieceHue.CYAN, PieceHue.YELLOW + pieces.hue_tolerance, PieceHue.CYAN + 30]]
    )

    assert pieces.wears_a_piece_colour(hues).tolist() == [[True, True, False]]
