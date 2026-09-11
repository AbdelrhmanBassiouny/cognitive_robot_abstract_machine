"""
Fitting the plane a depth image measures through a surface.
"""

from __future__ import annotations

import numpy as np
import pytest
from dataclasses import replace

from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.exceptions import (
    SurfaceNotSeenWhereTheWorldPutsIt,
)
from experiments.montessori.perception.measured_plane import (
    HEIGHT_TOLERANCE,
    LEVEL_TOLERANCE,
    CameraPoseError,
    MeasuredPlane,
)
from experiments.montessori.perception.recorded_setup import TABLE_HEIGHT, table_surface
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)

# %% fitting points

TILT = 12.0
"""
How far, in degrees, the leaning plane of these tests is turned about the y-axis.
"""

HEIGHT = 0.88
"""
How high, in metres, the planes of these tests stand at their middle.
"""


def leaning_plane_points(seed: int = 0) -> np.ndarray:
    """
    Points on a plane standing at :data:`HEIGHT` and leaning by :data:`TILT`, plus a few
    far off it.

    :param seed: What draws the points' places and the outliers.
    """
    generator = np.random.default_rng(seed)
    x = generator.uniform(-0.5, 0.5, 2000)
    y = generator.uniform(-0.5, 0.5, 2000)
    z = HEIGHT - np.tan(np.radians(TILT)) * x
    outliers = generator.uniform(0.0, 0.1, 40)
    z[:40] += outliers
    return np.column_stack([x, y, z])


def test_a_level_plane_is_read_as_level_at_its_height():
    generator = np.random.default_rng(1)
    points = np.column_stack(
        [
            generator.uniform(-0.5, 0.5, 1000),
            generator.uniform(-0.5, 0.5, 1000),
            np.full(1000, HEIGHT),
        ]
    )

    plane = MeasuredPlane.fit(points)

    assert plane.tilt == pytest.approx(0.0, abs=1e-6)
    assert plane.height == pytest.approx(HEIGHT)
    assert plane.residual == pytest.approx(0.0, abs=1e-9)


def test_a_leaning_plane_is_read_with_its_tilt_despite_outliers():
    plane = MeasuredPlane.fit(leaning_plane_points())

    assert plane.tilt == pytest.approx(TILT, abs=0.05)
    np.testing.assert_allclose(
        plane.normal[:2] / np.linalg.norm(plane.normal[:2]), [1.0, 0.0], atol=1e-3
    )
    assert plane.residual < 1e-3


def test_the_normal_points_upward():
    plane = MeasuredPlane.fit(leaning_plane_points())

    assert plane.normal[2] > 0.0


# %% reading a surface off a frame


def test_the_table_of_a_capture_is_measured_as_the_frame_places_it():
    frame = SceneCapture.load("tracy_pickup_demo").to_frame()

    plane = MeasuredPlane.of_surface(frame, table_surface())

    assert plane.tilt < 1.0
    assert plane.height == pytest.approx(TABLE_HEIGHT, abs=0.01)


def test_a_camera_stated_a_quarter_turn_off_measures_the_table_leaning_that_far():
    capture = SceneCapture.load("tracy_pickup_demo")
    leaned = HomogeneousTransformationMatrix.from_xyz_rpy(
        0.0, 0.0, 0.0, 0.0, np.radians(5.0), 0.0
    ).to_np()
    frame = replace(
        capture, reference_frame_T_camera=capture.reference_frame_T_camera @ leaned
    ).to_frame()

    plane = MeasuredPlane.of_surface(frame, table_surface())

    assert plane.tilt == pytest.approx(5.0, abs=0.5)


def test_a_surface_the_camera_does_not_see_is_refused():
    capture = SceneCapture.load("tracy_pickup_demo")
    surface = replace(table_surface(), height=TABLE_HEIGHT + 0.5)

    with pytest.raises(SurfaceNotSeenWhereTheWorldPutsIt):
        MeasuredPlane.of_surface(capture.to_frame(), surface)


# %% the stated pose against the surface

LEAN = 5.0
"""
How far, in degrees, the camera's stated pose is turned off the pose a capture was taken
from, in the tests that state it wrong.
"""

RAISE = 0.05
"""
How far, in metres, the camera's stated pose is lifted off the pose a capture was taken
from, in the tests that state it wrong.
"""


def leaned_capture(name: str = "tracy_pickup_demo") -> SceneCapture:
    """
    A shipped capture whose stated camera pose is turned by :data:`LEAN` about the
    camera's own y-axis.
    """
    capture = SceneCapture.load(name)
    leaned = HomogeneousTransformationMatrix.from_xyz_rpy(
        0.0, 0.0, 0.0, 0.0, np.radians(LEAN), 0.0
    ).to_np()
    return replace(
        capture, reference_frame_T_camera=capture.reference_frame_T_camera @ leaned
    )


def test_a_pose_the_pictures_were_taken_from_is_within_tolerance():
    error = CameraPoseError.of(
        SceneCapture.load("tracy_pickup_demo").to_frame(), table_surface()
    )

    assert error.within_tolerance
    assert error.tilt < LEVEL_TOLERANCE
    assert abs(error.height) < HEIGHT_TOLERANCE


def test_a_pose_stated_leaning_is_reported_leaning_that_far():
    error = CameraPoseError.of(leaned_capture().to_frame(), table_surface())

    assert not error.within_tolerance
    assert error.tilt == pytest.approx(LEAN, abs=0.5)


def test_a_pose_stated_too_high_is_reported_by_that_height():
    capture = SceneCapture.load("tracy_pickup_demo")
    lifted = capture.reference_frame_T_camera.copy()
    lifted[2, 3] += RAISE

    error = CameraPoseError.of(
        replace(capture, reference_frame_T_camera=lifted).to_frame(), table_surface()
    )

    assert not error.within_tolerance
    assert error.height == pytest.approx(RAISE, abs=HEIGHT_TOLERANCE)


def test_the_error_names_its_tilt_and_height_in_words():
    error = CameraPoseError.of(leaned_capture().to_frame(), table_surface())

    assert f"{error.tilt:.1f}" in str(error)
    assert f"{error.height * 1000:+.0f} mm" in str(error)
