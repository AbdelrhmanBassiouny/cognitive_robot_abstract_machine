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
from semantic_digital_twin.world_description.world_entity import Body

ROOT_T_BODY = HomogeneousTransformationMatrix.from_xyz_rpy(
    1.5, -2.0, 0.25, 0.3, -1.1, 2.4
)
"""
A transform with a translation and a rotation on every axis.
"""


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
