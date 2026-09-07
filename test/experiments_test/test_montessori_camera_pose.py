"""
Tests for correcting where the camera stands from what the twin already models.

A plane the world describes and a depth image of it are two accounts of one scene, so
where they disagree one of them is wrong. These tests build the disagreement on purpose
-- a picture of a level plane read through a pose that is tilted -- so what the fit
should recover is known exactly, and then check the three things that make it an
operation rather than a returned number: that the correction is only the tilt, that it
outlives the frame it was fitted in, and that a disagreement too large to be a pose is
refused rather than absorbed.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from experiments.montessori.perception.camera import BelievedCameraPose, RgbdFrame
from experiments.montessori.perception.exceptions import (
    CameraTiltedFurtherThanTrusted,
)
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.surface_finding import (
    LARGEST_TRUSTED_TILT,
    FittedSurfaceFinder,
    MeasuredSurfaceFinder,
    SoughtSurface,
    SurfaceRules,
)
from experiments.montessori.perception.recorded_setup import table_surface
from experiments.montessori.perception.surfaces import WorkspaceSurface
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.geometry import SurfaceFinish
from semantic_digital_twin.world_description.world_entity import Body

from .dataset.montessori_capture_truths import CAPTURE_TRUTHS
from .test_montessori_surface_finding import (
    CAMERA_HEIGHT,
    frame_showing,
)

# %% a picture read through a pose that is wrong

PLANE_HEIGHT = 0.88
"""
How high the plane these tests photograph stands, in metres.
"""

PLANE_BOUNDS = WorkspaceRegion(
    minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
)
"""
The stretch of plane the picture shows, which is also what the world models.
"""

TILT = math.radians(2.0)
"""
How far the pose these tests read a level plane through is turned away from level, in
radians.

Two degrees is small enough to be a calibration error rather than a different scene, and
large enough that the plane it makes of a level one slopes by more than a surface's own
points scatter across the stretch photographed here.
"""


def modelled_surface(
    finish: SurfaceFinish = SurfaceFinish.GLOSSY,
    bounds: WorkspaceRegion = PLANE_BOUNDS,
) -> WorkspaceSurface:
    """
    The surface the world states, against which the picture is read.

    :param finish: How the world says the surface takes light.
    :param bounds: How far the world says it reaches.
    """
    return WorkspaceSurface(
        entity=Body(name=PrefixedName("table", "camera_pose_test")),
        region=bounds,
        height=PLANE_HEIGHT,
        finish=finish,
    )


def turned_about_y(angle: float) -> np.ndarray:
    """
    A rotation about the reference frame's y-axis.

    :param angle: How far to turn, in radians.
    """
    turn = np.eye(3)
    turn[0, 0] = turn[2, 2] = math.cos(angle)
    turn[0, 2] = math.sin(angle)
    turn[2, 0] = -math.sin(angle)
    return turn


def read_through_a_tilted_pose(angle: float = TILT) -> RgbdFrame:
    """
    A picture of the level plane, carrying a pose that is turned away from level.

    The depth image is of a plane that really is level; only the pose the frame states
    is wrong, which is exactly what a camera whose calibration has drifted gives.

    :param angle: How far the stated pose is turned, in radians.
    """
    frame = frame_showing(PLANE_BOUNDS, PLANE_HEIGHT)
    tilted = frame.reference_frame_T_camera.copy()
    tilted[:3, :3] = turned_about_y(angle) @ tilted[:3, :3]
    return replace(frame, reference_frame_T_camera=tilted)


def sought_through(frame: RgbdFrame, **surface: object) -> SoughtSurface:
    """
    The look a finder is put to: the world's own surface, seen in one picture.

    :param frame: The picture the surface is looked for in.
    :param surface: What the world states about the surface, as :func:`modelled_surface`
        takes it.
    """
    return SoughtSurface(modelled_surface(**surface), frame)


def slope_of(finder: FittedSurfaceFinder, sought: SoughtSurface) -> float:
    """
    How far the plane a picture holds stands away from level, in radians, read through
    whatever pose the finder currently believes.

    :param finder: The finder whose belief the picture is read through.
    :param sought: The surface the world models, and the picture it is sought in.
    """
    frame = sought.frame
    if finder.believed_pose is not None:
        frame = finder.believed_pose.applied_to(frame)
    points = finder.measurement.points_standing_at(sought.surface, frame)
    return finder.tilt_of(points)


# %% the tilt, and only the tilt


def test_a_camera_reading_a_level_plane_as_sloping_is_turned_back_until_it_is_level():
    """
    The disagreement between a plane the world calls level and one the picture reads as
    sloping is a pose error, and it is the whole of what this fit corrects.
    """
    finder = FittedSurfaceFinder()
    sought = sought_through(read_through_a_tilted_pose())

    assert slope_of(finder, sought) == pytest.approx(TILT, abs=math.radians(0.05))

    finder.find(sought)

    assert slope_of(finder, sought) == pytest.approx(0.0, abs=math.radians(0.05))


def test_the_height_under_the_camera_is_left_where_the_world_puts_it():
    """
    The measured height is the half of the model this setup has not drifted away from,
    so a correction turns the camera rather than moving it: where it stands is untouched
    and the plane keeps the height the world states.
    """
    finder = FittedSurfaceFinder()
    sought = sought_through(read_through_a_tilted_pose())

    finder.find(sought)

    corrected = finder.believed_pose.reference_frame_T_camera
    assert corrected[:3, 3] == pytest.approx(sought.frame.camera_position)
    assert corrected[2, 3] == pytest.approx(CAMERA_HEIGHT)


def test_a_correction_no_larger_than_the_picture_is_read_at_leaves_the_pose_alone():
    """
    A picture already agreeing with the model has nothing to correct, so the pose it is
    read through is the one it came with.
    """
    finder = FittedSurfaceFinder()
    sought = sought_through(frame_showing(PLANE_BOUNDS, PLANE_HEIGHT))

    finder.find(sought)

    assert finder.believed_pose.reference_frame_T_camera == pytest.approx(
        sought.frame.reference_frame_T_camera, abs=1e-3
    )


# %% a disagreement too large to be a pose


def test_a_tilt_larger_than_the_setup_trusts_is_refused_rather_than_absorbed():
    """
    A solve with only a transform to move will explain any disagreement as a pose error,
    including one that is really a wrong model, so how far the camera may be turned is
    stated and a fit reaching past it says so instead of answering.
    """
    finder = FittedSurfaceFinder()
    sought = sought_through(read_through_a_tilted_pose(LARGEST_TRUSTED_TILT * 2.0))

    with pytest.raises(CameraTiltedFurtherThanTrusted):
        finder.find(sought)


def test_a_refused_fit_states_nothing_about_where_the_camera_is():
    """
    A refusal is not a half-answer: the pose is believed only once the turn it took to
    reach it has been read as one the camera could have drifted by.
    """
    finder = FittedSurfaceFinder()

    with pytest.raises(CameraTiltedFurtherThanTrusted):
        finder.find(
            sought_through(read_through_a_tilted_pose(LARGEST_TRUSTED_TILT * 2.0))
        )

    assert finder.believed_pose is None


# %% a correction that outlives the frame it was fitted in


def test_the_correction_is_kept_and_read_the_next_frame_through():
    """
    A camera pose is a value on one frame, so a correction that is not kept is a number
    nobody holds.

    The next picture from the same camera is read through the belief the last one left.
    """
    finder = FittedSurfaceFinder()
    finder.find(sought_through(read_through_a_tilted_pose()))
    believed = finder.believed_pose

    next_frame = read_through_a_tilted_pose()

    assert believed.applied_to(next_frame).reference_frame_T_camera == pytest.approx(
        believed.reference_frame_T_camera
    )


def test_the_belief_names_the_finder_that_fitted_it():
    """
    A belief records the thing whose say-so it is, so what else that source says can be
    asked of it rather than inferred from a label.
    """
    finder = FittedSurfaceFinder()

    finder.find(sought_through(read_through_a_tilted_pose()))

    assert finder.believed_pose.source is finder


# %% the measurement may move the model, not only cut it down


def test_a_surface_reaching_past_the_model_is_reported_reaching_past_it():
    """
    What separates this finder from the measurement it is built on: a plane really wider
    than the world models is answered at the width it was seen at, because the fit is
    allowed to move the model rather than only narrow it.
    """
    finder = FittedSurfaceFinder()
    modelled = modelled_surface(
        bounds=WorkspaceRegion(
            minimum_x=0.60, maximum_x=1.10, minimum_y=-0.05, maximum_y=0.35
        )
    )
    sought = SoughtSurface(modelled, frame_showing(PLANE_BOUNDS, PLANE_HEIGHT))
    narrowed = MeasuredSurfaceFinder().find(sought).region

    found = finder.find(sought).region

    assert found.minimum_x < modelled.region.minimum_x
    assert found.maximum_x > modelled.region.maximum_x
    assert found.minimum_y < modelled.region.minimum_y
    assert found.maximum_y > modelled.region.maximum_y
    assert narrowed.minimum_x >= modelled.region.minimum_x
    assert narrowed.maximum_x <= modelled.region.maximum_x


def test_everything_but_the_extent_is_left_as_the_world_states_it():
    """
    A fit answers where the surface reaches; what the surface is remains what the world
    says it is.
    """
    finder = FittedSurfaceFinder()
    sought = sought_through(frame_showing(PLANE_BOUNDS, PLANE_HEIGHT))

    found = finder.find(sought)

    assert found.entity is sought.surface.entity
    assert found.height == sought.surface.height
    assert found.finish is sought.surface.finish


# %% chosen by a rule, not by an edit


def test_a_fitted_finder_answers_a_surface_it_was_added_by_one_rule_for():
    """
    The rules already choose among whatever declares it can answer a surface, so this
    finder joins them by a rule stated while they are in use rather than by an edit to
    either finder already there.
    """
    rules = SurfaceRules()
    finder = FittedSurfaceFinder()
    sought = sought_through(frame_showing(PLANE_BOUNDS, PLANE_HEIGHT))
    assert rules.detector_for(sought) is rules.modelled

    rules.add_rule(sought, finder)

    assert rules.detector_for(sought) is finder


def test_a_fitted_finder_answers_only_a_picture_it_can_read_a_plane_in():
    """
    A fit needs the depth the plane is measured in, so a camera returning none is not
    one this finder says it can answer.
    """
    frame = frame_showing(PLANE_BOUNDS, PLANE_HEIGHT)
    without_depth = replace(frame, depth=np.zeros_like(frame.depth))
    finder = FittedSurfaceFinder()

    assert not finder.asked_about(sought_through(without_depth)).tolist()
    assert finder.asked_about(sought_through(frame)).tolist()


# %% put to the setup the recordings were taken on


@pytest.mark.parametrize("name", sorted(CAPTURE_TRUTHS))
def test_the_recorded_setup_is_already_level_within_what_a_drifted_mount_explains(
    name: str,
):
    """
    What says these rules are right about this scene rather than only self-consistent:
    on every shipped capture the table is seen leaning by less than a drifted mount
    explains, so the fit answers rather than refusing, and turning the camera by what it
    answers leaves the table standing nearer to level than it was read at.
    """
    finder = FittedSurfaceFinder()
    sought = SoughtSurface(table_surface(), SceneCapture.load(name).to_frame())
    before = slope_of(finder, sought)

    found = finder.find(sought)

    assert found.height == table_surface().height
    assert before < finder.largest_trusted_tilt
    assert slope_of(finder, sought) < before
