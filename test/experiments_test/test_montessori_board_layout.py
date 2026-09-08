"""
The board's holes as one rigid layout, and the fit that lays it over what was seen.

A hole given three degrees of freedom of its own lands wherever the picture happens to
agree with it, which is how the per-contour classifier put five holes inside ninety
millimetres of a board whose own mesh spreads them over a hundred and eighty. These
tests hold the two halves of the answer: the layout is exactly what the mesh was cut
with, and fitting it moves all six holes together.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from experiments.montessori.hole_geometry import BoardHoleLayout, detect_hole_footprints
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import BoardDetector
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.world import BOARD_SCALE

# %% the layout the mesh gives


def test_the_layout_holds_every_hole_the_mesh_was_cut_with():
    """
    The layout is the mesh's own footprints, not a reading of its own.
    """
    layout = BoardHoleLayout.of_board_mesh()

    assert list(layout.holes) == detect_hole_footprints()


def test_the_layout_reaches_as_far_as_the_world_says_the_board_does():
    """
    The lid's extent read off the mesh agrees with the scale the world builds its board
    at, which is what lets the detector stop importing that constant.
    """
    layout = BoardHoleLayout.of_board_mesh()

    assert layout.size.x == pytest.approx(float(BOARD_SCALE.x), abs=1e-6)
    assert layout.size.y == pytest.approx(float(BOARD_SCALE.y), abs=1e-6)


def test_reading_the_layout_twice_answers_the_same_object():
    """
    The mesh is sliced once rather than once per frame.
    """
    assert BoardHoleLayout.of_board_mesh() is BoardHoleLayout.of_board_mesh()


# %% placing it


def test_every_hole_is_placed_where_the_layout_puts_it():
    """
    A placed hole stands at its own offset from the board's centre, turned with the
    board.
    """
    layout = BoardHoleLayout.of_board_mesh()
    center, yaw = PlanarPoint(0.8, 0.13), math.radians(30.0)

    placed = layout.placed(center, yaw)

    assert [hole.footprint for hole in placed] == list(layout.holes)
    cosine, sine = math.cos(yaw), math.sin(yaw)
    for hole in placed:
        offset = hole.footprint.center
        assert hole.center.x == pytest.approx(
            center.x + offset.x * cosine - offset.y * sine
        )
        assert hole.center.y == pytest.approx(
            center.y + offset.x * sine + offset.y * cosine
        )


def test_a_placed_hole_carries_its_own_outline_about_its_own_centre():
    """
    A hole's reported outline is the mesh's boundary for that hole, put where the hole
    now stands.
    """
    layout = BoardHoleLayout.of_board_mesh()

    [placed] = [
        hole
        for hole in layout.placed(PlanarPoint(0.0, 0.0), 0.0)
        if hole.footprint is layout.holes[0]
    ]

    boundary = np.array(
        [(point.x, point.y) for point in placed.footprint.boundary]
    ) + np.array([placed.center.x, placed.center.y])
    assert placed.outline == pytest.approx(boundary)


def test_no_two_turns_of_the_layout_look_alike():
    """
    Six holes of five shapes have no symmetry, so a turn is only ever equivalent to
    itself brought within half a circle.
    """
    layout = BoardHoleLayout.of_board_mesh()

    assert layout.smallest_equivalent_turn(math.radians(30.0)) == pytest.approx(
        math.radians(30.0)
    )
    assert layout.smallest_equivalent_turn(
        math.radians(30.0) + 2 * math.pi
    ) == pytest.approx(math.radians(30.0))
    assert layout.smallest_equivalent_turn(math.radians(200.0)) == pytest.approx(
        math.radians(200.0) - 2 * math.pi
    )


# %% fitting it to what was seen


def edges_showing(outline_points: np.ndarray, region: WorkspaceRegion) -> EdgeDistances:
    """
    A view in which the only edges seen are the given outlines.

    :param outline_points: World-frame ``(n, 2)`` points the edges lie on.
    :param region: The patch of the plane the view covers.
    """
    drawn = np.ones((region.height_in_pixels, region.width_in_pixels), dtype=np.uint8)
    pixels = region.to_pixels(outline_points).round().astype(int)
    drawn[pixels[:, 1], pixels[:, 0]] = 0
    return EdgeDistances(
        distances=cv2.distanceTransform(drawn * 255, cv2.DIST_L2, 3)
        * region.resolution,
        region=region,
    )


@pytest.fixture
def lid_region() -> WorkspaceRegion:
    """
    A patch of table wide enough to hold the board at any turn.
    """
    return WorkspaceRegion(
        minimum_x=0.6, maximum_x=1.0, minimum_y=-0.05, maximum_y=0.35
    )


@pytest.mark.parametrize("drawn_yaw_in_degrees", [0.0, -7.6, -29.7, 95.0])
def test_the_layout_is_found_where_it_was_drawn(
    lid_region: WorkspaceRegion, drawn_yaw_in_degrees: float
) -> None:
    """
    Fitting the layout over its own outlines recovers the placement they were drawn at,
    from a seed that is neither the right place nor the right turn.

    Driven through the detector's own fitter, so what is measured is the configuration
    that ships.
    """
    layout = BoardHoleLayout.of_board_mesh()
    drawn_center = PlanarPoint(0.79, 0.135)
    drawn_yaw = math.radians(drawn_yaw_in_degrees)
    edges = edges_showing(
        layout.outline_points(drawn_yaw, 0.001)
        + np.array([drawn_center.x, drawn_center.y]),
        lid_region,
    )
    fitter = BoardDetector().fitter

    placement = fitter.fit(
        layout,
        edges,
        center=PlanarPoint(drawn_center.x + 0.012, drawn_center.y - 0.010),
        radius=0.03,
        angles=list(np.arange(-math.pi, math.pi, fitter.coarse_angle_step)),
    )

    assert placement.center.x == pytest.approx(drawn_center.x, abs=0.003)
    assert placement.center.y == pytest.approx(drawn_center.y, abs=0.003)
    assert placement.yaw == pytest.approx(
        layout.smallest_equivalent_turn(drawn_yaw), abs=math.radians(3.0)
    )
    assert placement.outline_agreement > 0.9


def test_a_layout_fitted_where_nothing_was_drawn_agrees_with_nothing(
    lid_region: WorkspaceRegion,
) -> None:
    """
    Agreement measures the picture, so a view holding no board's edges scores far below
    one holding them.
    """
    layout = BoardHoleLayout.of_board_mesh()
    edges = edges_showing(
        np.array([[lid_region.minimum_x, lid_region.minimum_y]]), lid_region
    )
    fitter = BoardDetector().fitter

    placement = fitter.fit(
        layout,
        edges,
        center=PlanarPoint(0.79, 0.135),
        radius=0.03,
        angles=[0.0],
    )

    assert placement.outline_agreement < 0.1
