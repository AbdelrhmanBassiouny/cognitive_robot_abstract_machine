"""
Unit tests for :class:`NumericTransform` and :class:`NumericPoint3`.

These stand in for a :class:`HomogeneousTransformationMatrix` wherever a transform is
held only to be read back as numbers, so a thread that does not own the world can carry
one without touching CasADi.
"""

from __future__ import annotations

import numpy as np
import pytest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.numeric import NumericPoint3, NumericTransform
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Bounds, Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

ROOT_T_BODY = HomogeneousTransformationMatrix.from_xyz_rpy(
    1.5, -2.0, 0.25, 0.3, -1.1, 2.4
)
"""
A transform with a translation and a rotation on every axis.
"""


def _refuse_to_build(*args: object, **kwargs: object) -> object:
    """
    Stand in for symbolic machinery a numeric read must never reach.
    """
    raise AssertionError("a symbolic value was built")


def _frame() -> Body:
    """
    A body registered in a world, usable as a reference frame.
    """
    world = World()
    body = Body(name=PrefixedName("frame"))
    with world.modify_world():
        world.add_body(body)
    return body


# %% reading a symbolic transform out
def test_a_numeric_transform_carries_the_symbolic_transforms_numbers() -> None:
    """
    A numeric transform stands in for the symbolic one, so it has to hold the same
    matrix and name the same frame.
    """
    frame = _frame()
    symbolic = HomogeneousTransformationMatrix(
        data=ROOT_T_BODY.to_np(), reference_frame=frame
    )

    numeric = NumericTransform.from_transformation_matrix(symbolic)

    assert np.array_equal(numeric.to_np(), symbolic.to_np())
    assert numeric.reference_frame is frame


def test_a_numeric_transforms_coordinates_are_plain_floats() -> None:
    """
    A coordinate still holding a CasADi expression would be evaluated again by whoever
    reads it.
    """
    numeric = NumericTransform.from_transformation_matrix(ROOT_T_BODY)

    assert (numeric.x, numeric.y, numeric.z) == pytest.approx((1.5, -2.0, 0.25))
    assert all(type(value) is float for value in (numeric.x, numeric.y, numeric.z))


def test_an_identity_transform_names_its_frame_and_moves_nothing() -> None:
    """
    Reading a body's own geometry asks for the transform from its frame to itself.
    """
    frame = _frame()

    numeric = NumericTransform.identity(frame)

    assert np.array_equal(numeric.to_np(), np.eye(4))
    assert numeric.reference_frame is frame


# %% composing and inverting
def test_composing_a_transform_with_its_inverse_moves_nothing() -> None:
    """
    Carrying geometry between frames composes transforms, so composition and inversion
    have to agree.
    """
    numeric = NumericTransform.from_transformation_matrix(ROOT_T_BODY)

    assert (numeric @ numeric.inverse()).to_np() == pytest.approx(np.eye(4))


def test_an_inverse_matches_the_symbolic_inverse() -> None:
    """
    The numeric inverse replaces the symbolic one, so it must produce the same matrix.
    """
    numeric = NumericTransform.from_transformation_matrix(ROOT_T_BODY)

    assert numeric.inverse().to_np() == pytest.approx(ROOT_T_BODY.inverse().to_np())


# %% reading a position out
def test_a_transforms_position_reads_as_a_homogeneous_point() -> None:
    """
    A position is read back as a 4-vector ending in 1, the same shape the symbolic point
    has, so a reader does not have to know which kind it was handed.
    """
    numeric = NumericTransform.from_transformation_matrix(ROOT_T_BODY)

    assert numeric.to_position().to_np().tolist() == pytest.approx(
        [1.5, -2.0, 0.25, 1.0]
    )


def test_a_numeric_point_keeps_its_own_coordinates() -> None:
    """
    A point read out of geometry is handed on as numbers.
    """
    point = NumericPoint3(x=1.0, y=2.0, z=3.0)

    assert (point.x, point.y, point.z) == (1.0, 2.0, 3.0)
    assert point.to_np().tolist() == [1.0, 2.0, 3.0, 1.0]


# %% carrying a point cloud between frames
def test_transformed_points_match_transforming_them_one_by_one() -> None:
    """
    A mesh's vertices are carried into the world frame in one array rather than a point
    at a time, so the bulk result has to match the per-point one.
    """
    numeric = NumericTransform.from_transformation_matrix(ROOT_T_BODY)
    points = np.array([[0.0, 0.0, 0.0], [1.0, -2.0, 0.5], [-3.0, 4.0, 2.5]])

    transformed = numeric.transform_points(points)

    one_by_one = [(numeric.to_np() @ np.append(point, 1.0))[:3] for point in points]
    assert transformed == pytest.approx(np.array(one_by_one))


def test_transforming_no_points_yields_no_points() -> None:
    """
    An entity without geometry hands over an empty array, which must not be read as a
    point at the origin.
    """
    numeric = NumericTransform.from_transformation_matrix(ROOT_T_BODY)

    assert numeric.transform_points(np.empty((0, 3))).shape == (0, 3)


# %% reading a world entity out numerically
def _stacked_bodies() -> tuple[Body, Body]:
    """
    A body held one metre above another by a fixed connection.
    """
    world = World()
    lower = Body(name=PrefixedName("lower"))
    upper = Body(name=PrefixedName("upper"))
    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=lower,
                child=upper,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    0.0, 0.0, 1.0
                ),
            )
        )
    return lower, upper


def test_a_bodys_numeric_global_transform_matches_its_symbolic_one() -> None:
    """
    The numeric read replaces the symbolic one, so it must place the body where the
    symbolic one does.
    """
    _, upper = _stacked_bodies()

    assert upper.numeric_global_transform.to_np() == pytest.approx(
        upper.global_transform.to_np()
    )


def test_a_bodys_numeric_global_bounds_enclose_its_geometry_where_it_stands() -> None:
    """
    Ruling a pair of bodies out before an exact spatial relation is computed rests on
    the bounds enclosing the geometry in the frame the relation is asked about.
    """
    lower, upper = _stacked_bodies()
    upper.collision = ShapeCollection(
        [Box(scale=Scale(2.0, 4.0, 6.0), origin=HomogeneousTransformationMatrix())],
        reference_frame=upper,
    )

    bounds = upper.numeric_global_bounds

    assert bounds.lower == pytest.approx([-1.0, -2.0, -2.0])
    assert bounds.upper == pytest.approx([1.0, 2.0, 4.0])


def test_a_body_without_geometry_encloses_nothing() -> None:
    """
    Bounds that enclosed everything instead would make such a body overlap every other.
    """
    lower, _ = _stacked_bodies()

    assert not lower.numeric_global_bounds.overlaps(
        Bounds(np.full(3, -1e6), np.full(3, 1e6))
    )


def test_a_bodys_numeric_global_transform_builds_nothing_symbolic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reading a body's placement is the commonest thing a detector tick does, and it must
    not reach CasADi from a thread of its own.
    """
    _, upper = _stacked_bodies()
    expected = upper.numeric_global_transform.to_np()
    monkeypatch.setattr(World, "compute_forward_kinematics", _refuse_to_build)
    monkeypatch.setattr(HomogeneousTransformationMatrix, "__init__", _refuse_to_build)

    assert upper.numeric_global_transform.to_np() == pytest.approx(expected)
