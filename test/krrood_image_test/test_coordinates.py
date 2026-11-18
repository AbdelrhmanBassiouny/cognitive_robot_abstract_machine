"""
Tests for the plane images lie on, and for positions, displacements and boxes on an
image.
"""

from __future__ import annotations

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_image.coordinates import (
    ImageBox,
    ImageCoordinateSystem,
    ImagePlane,
    ImagePoint,
    ImageVector,
    Pixel,
    PixelBox,
    Resolution,
)
from krrood_spatial_math.coordinate_system import (
    AffineFrame,
    AffineFrameT,
    CartesianFrame,
    CoordinateT,
    SpaceT,
)
from krrood_spatial_math.space import EuclideanSpace2Dimensional
from krrood_spatial_math.vector import VectorT

# %% the plane images lie on, and the coordinate systems on it


@pytest.mark.parametrize("interface", [ImagePlane, ImageCoordinateSystem])
def test_an_image_interface_cannot_be_instantiated(interface: type) -> None:
    """
    The plane and its coordinate systems are interfaces that a camera or an image
    implements, so they cannot be created on their own.
    """
    with pytest.raises(InterfaceInstantiationError):
        interface()


def test_an_image_plane_is_a_two_dimensional_euclidean_space() -> None:
    """
    An image plane has distances and angles and two directions, like any flat surface.
    """
    assert issubclass(ImagePlane, EuclideanSpace2Dimensional)


def test_an_image_coordinate_system_charts_an_image_plane() -> None:
    """
    The space an image coordinate system is bound to is the image plane.
    """
    assert (
        ImageCoordinateSystem.get_type_of_generic_parameter(parameter=SpaceT)
        is ImagePlane
    )


def test_an_image_coordinate_system_is_an_affine_frame() -> None:
    """
    Pixel coordinates are amounts along straight axes from an origin.
    """
    assert issubclass(ImageCoordinateSystem, AffineFrame)


def test_an_image_coordinate_system_is_not_a_cartesian_frame() -> None:
    """
    A pixel is not a unit of the plane's length, so pixel axes do not measure distances.
    """
    assert not issubclass(ImageCoordinateSystem, CartesianFrame)


# %% positions and displacements anywhere on an image


@pytest.mark.parametrize("value_type", [ImagePoint, ImageVector])
def test_an_image_value_is_given_in_an_image_coordinate_system(
    value_type: type,
) -> None:
    """
    Image points and vectors are bound to image coordinate systems, so a type checker
    tells them apart from metric points and vectors.
    """
    assert (
        value_type.get_type_of_generic_parameter(parameter=AffineFrameT)
        is ImageCoordinateSystem
    )


@pytest.mark.parametrize("value_type", [ImagePoint, ImageVector])
def test_an_image_values_coordinates_are_floats(value_type: type) -> None:
    """
    Positions and displacements lie anywhere between pixels.
    """
    assert value_type.get_type_of_generic_parameter(parameter=CoordinateT) is float


def test_an_image_point_is_moved_by_an_image_vector() -> None:
    """
    The vector an image point is moved by is an image vector.
    """
    assert ImagePoint.get_type_of_generic_parameter(parameter=VectorT) is ImageVector


def test_the_difference_of_two_points_moves_one_onto_the_other() -> None:
    """
    Subtracting two points gives the vector that, added to the second, gives the first.
    """
    start, end = ImagePoint(x=1.5, y=2.0), ImagePoint(x=4.0, y=-1.0)
    displacement = end - start
    assert displacement == ImageVector(x=2.5, y=-3.0)
    assert start + displacement == end


def test_an_image_points_coordinates_are_its_x_and_y() -> None:
    """
    A point's coordinates follow the image axes: columns first, then rows.
    """
    point = ImagePoint(x=3.0, y=7.0)
    assert point.coordinates == (point.x, point.y)


# %% boxes anywhere on an image


def test_a_box_from_its_corner_and_size_has_that_corner_and_size() -> None:
    """
    A box built from its top left corner and size reports them back, the corner as its
    lower corner.
    """
    left, top, width, height = 1.5, 2.5, 10.0, 4.0
    box = ImageBox.from_corner_and_size(left=left, top=top, width=width, height=height)
    assert (box.left, box.top, box.width, box.height) == (left, top, width, height)
    assert box.lower == ImagePoint(x=left, y=top)


def test_the_box_covering_an_image_covers_every_pixel(resolution: Resolution) -> None:
    """
    The box covering an image rounds to the pixels of the whole image.
    """
    assert PixelBox.nearest(
        box=ImageBox.covering(resolution=resolution)
    ) == PixelBox.between(
        left=0, top=0, right=resolution.width, bottom=resolution.height
    )


def test_the_largest_centred_box_keeps_the_aspect_ratio(
    resolution: Resolution,
) -> None:
    """
    Narrower boxes fill the height and wider ones the width, centred in the room.
    """
    room = ImageBox.covering(resolution=resolution)
    square = room.largest_centred(aspect_ratio=1.0)
    assert PixelBox.nearest(box=square) == PixelBox.between(
        left=50, top=0, right=150, bottom=100
    )
    wide = room.largest_centred(aspect_ratio=4.0)
    assert PixelBox.nearest(box=wide) == PixelBox.between(
        left=0, top=25, right=200, bottom=75
    )


# %% whole pixels


def test_a_position_falls_on_the_nearest_pixel() -> None:
    """
    A position is rounded to the pixel whose centre is closest.
    """
    assert Pixel.nearest(point=ImagePoint(x=3.4, y=7.6)) == Pixel(column=3, row=8)


def test_a_pixel_box_runs_from_its_top_left_pixel_to_its_bottom_right_one() -> None:
    """
    A pixel box's corners are its first and last pixels, so its size counts both.
    """
    left, top, width, height = 10, 20, 10, 5
    box = PixelBox.between(left=left, top=top, right=left + width, bottom=top + height)
    assert box.lower == Pixel(column=left, row=top)
    assert box.upper == Pixel(column=left + width - 1, row=top + height - 1)
    assert (box.width, box.height) == (width, height)


def test_the_visible_part_of_a_box_is_cut_at_the_image_edges(
    resolution: Resolution,
) -> None:
    """
    The part of a box hanging over the image's edges is cut off at them.
    """
    hanging_over = PixelBox.between(left=-10, top=90, right=40, bottom=120)
    assert hanging_over.visible_part(resolution=resolution) == PixelBox.between(
        left=0, top=90, right=40, bottom=resolution.height
    )


def test_a_box_outside_an_image_has_no_visible_part(
    resolution: Resolution,
) -> None:
    """
    A box wholly beside the image keeps no pixel of it.
    """
    beyond = PixelBox.between(
        left=resolution.width + 5, top=0, right=resolution.width + 15, bottom=10
    )
    assert beyond.visible_part(resolution=resolution).is_empty is True
