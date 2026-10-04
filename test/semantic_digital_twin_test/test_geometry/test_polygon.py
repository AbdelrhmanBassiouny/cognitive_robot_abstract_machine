import math

import numpy as np
import pytest

from semantic_digital_twin.world_description.geometry import Polygon2D

# %% measuring a polygon


def test_a_rectangles_area_and_centroid():
    rectangle = Polygon2D(np.array([(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]))

    assert rectangle.area == pytest.approx(2.0)
    assert rectangle.centroid.to_np() == pytest.approx([1.0, 0.5])


def test_a_triangle_balances_at_a_third_of_its_height():
    triangle = Polygon2D(np.array([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]))

    assert triangle.area == pytest.approx(0.5)
    assert triangle.centroid.to_np() == pytest.approx([1 / 3, 1 / 3])


def test_the_area_does_not_depend_on_the_winding():
    corners = np.array([(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)])

    assert Polygon2D(corners[::-1]).area == Polygon2D(corners).area


def test_a_closing_corner_that_repeats_the_first_is_dropped():
    corners = np.array([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)])

    closed = Polygon2D(np.vstack([corners, corners[:1]]))

    assert closed.vertices == pytest.approx(corners)


def test_the_bounding_box_holds_every_corner():
    triangle = Polygon2D(np.array([(-1.0, 0.0), (3.0, 0.5), (0.0, 2.0)]))

    box = triangle.bounding_box

    assert (box.min_x, box.min_y, box.max_x, box.max_y) == (-1.0, 0.0, 3.0, 2.0)


def test_centering_moves_the_centroid_onto_the_origin():
    triangle = Polygon2D(np.array([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]))

    assert triangle.centered().centroid.to_np() == pytest.approx([0.0, 0.0])


# %% building a polygon


def test_a_rectangle_is_as_wide_and_long_as_asked():
    box = Polygon2D.rectangle(0.02, 0.04).bounding_box

    assert (box.depth, box.width) == pytest.approx((0.02, 0.04))


def test_a_circle_has_the_asked_diameter_and_its_corner_count():
    circle = Polygon2D.circle(0.028)

    assert len(circle.vertices) == Polygon2D.CIRCLE_CORNER_COUNT
    assert np.linalg.norm(circle.vertices, axis=1) == pytest.approx(0.014)


def test_an_equilateral_triangle_has_three_equal_sides_about_its_centroid():
    triangle = Polygon2D.equilateral_triangle(0.037)

    sides = np.linalg.norm(triangle.vertices - np.roll(triangle.vertices, 1, 0), axis=1)
    assert sides == pytest.approx(0.037)
    assert triangle.centroid.to_np() == pytest.approx([0.0, 0.0], abs=1e-12)


# %% using a polygon


def test_turning_a_quarter_turn_moves_x_onto_y():
    point = Polygon2D(np.array([(1.0, 0.0), (0.0, 0.0), (0.0, -1.0)]))

    turned = point.turned(math.pi / 2)

    assert turned.vertices[0] == pytest.approx([0.0, 1.0])


def test_points_along_include_every_corner_at_the_asked_spacing():
    square = Polygon2D.rectangle(1.0, 1.0)

    points = square.points_along(0.25)

    assert len(points) == 16
    for corner in square.vertices:
        assert np.isclose(points, corner).all(axis=1).any()


def test_extruding_gives_a_watertight_solid_of_the_enclosed_area_times_thickness():
    triangle = Polygon2D.equilateral_triangle(0.037)

    solid = triangle.extrude(0.01)

    assert solid.is_watertight
    assert solid.volume == pytest.approx(triangle.area * 0.01)
    assert solid.bounds[:, 2] == pytest.approx([-0.005, 0.005])
