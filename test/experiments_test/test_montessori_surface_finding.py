"""
Tests for finding a surface in the picture from what the world says it is like.

The rules and the measurement are tested apart from the pipeline, so a failure names
which of the two is wrong: the measurement is put to a depth image built here, where
what it should answer is known exactly, and the rules are put to descriptions built
here, where what the world says is the whole of the input. The rules are then put to the
shipped captures, which is what says the rules stated for this scene are right about it
rather than only self-consistent.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from typing_extensions import Tuple

from experiments.montessori.perception.camera import CameraIntrinsics, RgbdFrame
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.exceptions import (
    NoSurfaceFinderAnswersTheLook,
    SurfaceNotSeenWhereTheWorldPutsIt,
)
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.surface_finding import (
    SURFACE_SCATTER,
    MeasuredSurfaceFinder,
    ModelledSurfaceFinder,
    SoughtSurface,
    SurfaceFinder,
    SurfaceRules,
)
from experiments.montessori.perception.recorded_setup import (
    lid_surface,
    table_surface,
)
from krrood.entity_query_language.backends import PerceptionDetector
from krrood.entity_query_language.rdr.rule_tree_view import walk_rules
from experiments.montessori.perception.surfaces import WorkspaceSurface
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Box, Scale, SurfaceFinish
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

# %% a depth image of a plane, built where what it holds is known

CAMERA_HEIGHT = 1.6
"""
How high above the reference frame's origin the test camera stands, in metres.
"""

FLOOR_HEIGHT = 0.0
"""
Height of the ground the test scene's plane stands over, in metres.
"""

TEST_INTRINSICS = CameraIntrinsics(
    focal_length_x=600.0,
    focal_length_y=600.0,
    principal_point_x=320.0,
    principal_point_y=240.0,
)
"""
A pinhole camera roughly the shape of the one the captures were taken with.
"""


def looking_straight_down(x: float, y: float) -> np.ndarray:
    """
    A camera pose looking straight down at the reference frame's x-y plane.

    The optical frame's x runs along the world's x, its y against the world's y, and its
    z downwards, so a point at optical ``(u, v, d)`` stands at world
    ``(x + u, y - v, CAMERA_HEIGHT - d)``.

    :param x: Where the camera stands along the world's x-axis, in metres.
    :param y: Where the camera stands along the world's y-axis, in metres.
    """
    pose = np.eye(4)
    pose[:3, :3] = np.diag([1.0, -1.0, -1.0])
    pose[:3, 3] = [x, y, CAMERA_HEIGHT]
    return pose


def frame_showing(
    plane: WorkspaceRegion, height: float, width: int = 640, rows: int = 480
) -> RgbdFrame:
    """
    A depth image of one horizontal plane standing over a floor.

    Every pixel whose ray meets the plane inside *plane* reads the plane's own depth,
    and every other pixel reads the floor's, so the picture holds exactly one surface at
    *height* and nothing else at that height.

    :param plane: The stretch of the plane the picture shows.
    :param height: How high the plane stands above the reference frame's origin.
    :param width: Number of image columns.
    :param rows: Number of image rows.
    """
    camera = looking_straight_down(
        (plane.minimum_x + plane.maximum_x) / 2, (plane.minimum_y + plane.maximum_y) / 2
    )
    columns, image_rows = np.meshgrid(np.arange(width), np.arange(rows))
    plane_depth = CAMERA_HEIGHT - height
    x = camera[0, 3] + (columns - TEST_INTRINSICS.principal_point_x) * plane_depth / (
        TEST_INTRINSICS.focal_length_x
    )
    y = camera[1, 3] - (
        image_rows - TEST_INTRINSICS.principal_point_y
    ) * plane_depth / (TEST_INTRINSICS.focal_length_y)
    on_the_plane = (
        (x >= plane.minimum_x)
        & (x <= plane.maximum_x)
        & (y >= plane.minimum_y)
        & (y <= plane.maximum_y)
    )
    depth = np.where(on_the_plane, plane_depth, CAMERA_HEIGHT - FLOOR_HEIGHT)
    return RgbdFrame(
        color=np.zeros((rows, width, 3), dtype=np.uint8),
        depth=depth.astype(float),
        intrinsics=TEST_INTRINSICS,
        reference_frame_T_camera=camera,
    )


def modelled_surface(
    bounds: WorkspaceRegion, height: float, finish: SurfaceFinish = None
) -> WorkspaceSurface:
    """
    The surface a world would state, against which a measurement is compared.

    :param bounds: How far the world says the surface reaches.
    :param height: How high the world says its plane stands.
    :param finish: How the world says it takes light, or None where it states none.
    """
    return WorkspaceSurface(
        entity=Body(name=PrefixedName("table", "test")),
        region=bounds,
        height=height,
        finish=finish,
    )


def reaches(surface: WorkspaceSurface) -> Tuple[float, float, float, float]:
    """
    How far a surface reaches, as the four bounds in the order a region states them.

    :param surface: The surface to read.
    """
    return (
        surface.region.minimum_x,
        surface.region.maximum_x,
        surface.region.minimum_y,
        surface.region.maximum_y,
    )


# %% the measurement on its own

MODELLED_BOUNDS = WorkspaceRegion(
    minimum_x=0.35, maximum_x=1.35, minimum_y=-0.45, maximum_y=0.75
)
"""
A stretch of the world much wider than the plane standing in it, as the workspace guess
this item replaces is.
"""

PLANE_BOUNDS = WorkspaceRegion(
    minimum_x=0.55, maximum_x=0.95, minimum_y=-0.05, maximum_y=0.40
)
"""
The plane actually standing inside it.
"""

PLANE_HEIGHT = 0.88
"""
How high that plane stands, which is Tracy's own table height.
"""

NO_GROUND = WorkspaceRegion(
    minimum_x=0.75, maximum_x=0.75, minimum_y=-0.05, maximum_y=0.40
)
"""
A stretch bounded to no ground at all, which is a surface neither finder can answer.
"""


def test_a_plane_is_measured_where_the_depth_image_puts_it() -> None:
    """
    The measurement answers the stretch the plane really covers, not the stretch the
    world models around it.
    """
    measured = MeasuredSurfaceFinder().find(
        SoughtSurface(
            modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT),
            frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
        )
    )
    assert reaches(measured) == pytest.approx(
        (
            PLANE_BOUNDS.minimum_x,
            PLANE_BOUNDS.maximum_x,
            PLANE_BOUNDS.minimum_y,
            PLANE_BOUNDS.maximum_y,
        ),
        abs=2 * MODELLED_BOUNDS.resolution,
    )


def test_a_plane_standing_a_little_off_its_modelled_height_is_still_measured() -> None:
    """
    A surface is recognised by the points standing about where the world puts it, so it
    is found without its height having to agree to the millimetre.
    """
    measured = MeasuredSurfaceFinder().find(
        SoughtSurface(
            modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT),
            frame_showing(PLANE_BOUNDS, PLANE_HEIGHT + SURFACE_SCATTER / 2),
        )
    )
    assert reaches(measured) == pytest.approx(
        (
            PLANE_BOUNDS.minimum_x,
            PLANE_BOUNDS.maximum_x,
            PLANE_BOUNDS.minimum_y,
            PLANE_BOUNDS.maximum_y,
        ),
        abs=2 * MODELLED_BOUNDS.resolution,
    )


def test_everything_but_the_extent_is_left_as_the_world_states_it() -> None:
    """
    Only how far a surface reaches is measured.

    Its height is the half of the model this scene has not drifted away from, and the
    lid's own plane is derived from it, so a measurement that moved it would leave the
    two surfaces describing different tables.
    """
    modelled = modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.MIRROR)
    measured = MeasuredSurfaceFinder().find(
        SoughtSurface(
            modelled, frame_showing(PLANE_BOUNDS, PLANE_HEIGHT + SURFACE_SCATTER / 2)
        )
    )
    assert (measured.name, measured.height, measured.finish) == (
        modelled.name,
        modelled.height,
        modelled.finish,
    )


def test_a_plane_wider_than_the_world_models_is_reported_no_wider() -> None:
    """
    The measurement narrows what the world already states and never grows it, so a run
    only ever searches a stretch the world had already allowed.
    """
    measured = MeasuredSurfaceFinder().find(
        SoughtSurface(
            modelled_surface(PLANE_BOUNDS, PLANE_HEIGHT),
            frame_showing(MODELLED_BOUNDS, PLANE_HEIGHT),
        )
    )
    assert reaches(measured) == pytest.approx(
        (
            PLANE_BOUNDS.minimum_x,
            PLANE_BOUNDS.maximum_x,
            PLANE_BOUNDS.minimum_y,
            PLANE_BOUNDS.maximum_y,
        ),
        abs=2 * PLANE_BOUNDS.resolution,
    )


def test_a_picture_holding_no_plane_where_the_world_says_is_refused() -> None:
    """
    Nothing standing where the surface is modelled is a fact about the scene, so it is
    raised rather than answered with the modelled stretch as though it had been seen.
    """
    with pytest.raises(SurfaceNotSeenWhereTheWorldPutsIt):
        MeasuredSurfaceFinder().find(
            SoughtSurface(
                modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT),
                frame_showing(PLANE_BOUNDS, PLANE_HEIGHT + 10 * SURFACE_SCATTER),
            )
        )


# %% the rules


def test_a_mirror_finished_surface_is_measured_in_the_picture() -> None:
    """
    The finish is what says colour cannot outline the surface, so the picture's depth is
    what settles where it reaches.
    """
    rules = SurfaceRules()
    finder = rules.detector_for(
        SoughtSurface(
            modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.MIRROR),
            frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
        )
    )
    assert finder is rules.measured


def test_the_rules_read_the_finish_the_worlds_own_shape_states() -> None:
    """
    A rule is stated over the surface the world describes rather than over a copy of its
    properties, so a finish carried by the twin's own collision shape is what decides
    the look, with nothing in between to fall out of step with it.
    """
    table = Body(
        name=PrefixedName("brushed_steel_table", "test"),
        collision=ShapeCollection(
            [Box(scale=Scale(1.0, 1.2, 0.02), finish=SurfaceFinish.MIRROR)]
        ),
    )
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(table)
    rules = SurfaceRules()

    sought = SoughtSurface(
        WorkspaceSurface.of_body(table, world.root),
        frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
    )

    assert sought.surface.finish is SurfaceFinish.MIRROR
    assert rules.detector_for(sought) is rules.measured


def test_a_surface_the_world_states_no_finish_for_is_taken_from_the_model() -> None:
    """
    An unstated finish is not a description a look can be compiled from, so the model is
    what answers -- which is the state every world in this workspace is in.
    """
    rules = SurfaceRules()
    finder = rules.detector_for(
        SoughtSurface(
            modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT),
            frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
        )
    )
    assert finder is rules.modelled


def test_a_surface_the_world_bounds_to_nothing_is_refused() -> None:
    """
    A surface bounded to no ground at all gives both finders nothing: the model has no
    extent to state and the measurement has none to narrow, so the look is refused
    rather than answered from a guess.
    """
    rules = SurfaceRules()
    with pytest.raises(NoSurfaceFinderAnswersTheLook):
        rules.detector_for(
            SoughtSurface(
                modelled_surface(NO_GROUND, PLANE_HEIGHT, SurfaceFinish.MIRROR),
                frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
            )
        )


def test_a_rule_added_while_the_rules_are_in_use_changes_the_next_answer() -> None:
    """
    The rules outlive the surfaces they decide, so a situation nobody foresaw is given a
    rule rather than written into the code that reads them.
    """
    rules = SurfaceRules()
    glossy = SoughtSurface(
        modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.GLOSSY),
        frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
    )
    assert rules.detector_for(glossy) is rules.modelled
    rules.add_rule(glossy, rules.measured)
    assert rules.detector_for(glossy) is rules.measured


def test_the_rules_are_stated_over_the_surface_being_sought() -> None:
    """
    What a rule reads is the surface being sought itself, and what the rules work out
    about it is the slot that surface leaves open, so neither is named a second time
    here.
    """
    rules = SurfaceRules()

    assert rules.rules.case_type is SoughtSurface
    assert rules.rules.conclusion_attribute_name in vars(
        SoughtSurface(
            modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT),
            frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
        )
    )


def test_the_rules_can_be_read_as_a_tree() -> None:
    """
    A tree of rules is worth having only if it can be read, so the finder chosen for one
    surface is named in the rendering of the rules that chose it.
    """
    rules = SurfaceRules()
    sought = SoughtSurface(
        modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.MIRROR),
        frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
    )

    assert type(rules.measured).__name__ in rules.render_tree(sought)


def test_a_finder_answers_the_kind_of_look_it_binds() -> None:
    """
    A finder is one of the same family of detectors every other look is answered by, and
    what its conditions may read is part of its signature rather than a field stating it
    again.
    """
    assert issubclass(SurfaceFinder, PerceptionDetector)
    assert MeasuredSurfaceFinder.look_type() is SoughtSurface


def test_the_rules_answer_a_mirror_finished_surface_from_the_picture() -> None:
    """
    Asking the rules for a surface runs the finder they chose, so a caller states what
    it is looking at rather than which finder to use.
    """
    found = SurfaceRules().surface_in(
        modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.MIRROR),
        frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
    )
    assert reaches(found) == pytest.approx(
        (
            PLANE_BOUNDS.minimum_x,
            PLANE_BOUNDS.maximum_x,
            PLANE_BOUNDS.minimum_y,
            PLANE_BOUNDS.maximum_y,
        ),
        abs=2 * MODELLED_BOUNDS.resolution,
    )


def test_the_rules_answer_an_unannotated_surface_with_the_one_the_world_states() -> (
    None
):
    """
    Where nothing is stated the answer is the modelled surface itself, unchanged, so a
    world that says nothing new is looked at exactly as it was before.
    """
    modelled = modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT)
    assert (
        SurfaceRules().surface_in(modelled, frame_showing(PLANE_BOUNDS, PLANE_HEIGHT))
        == modelled
    )


def test_each_finder_declares_the_surfaces_it_can_answer() -> None:
    """
    Both finders need the world to bound the surface, so neither answers one it does
    not, and on a look that offers both of them everything the choice between them is
    the rules' rather than a capability's.
    """
    unbounded = SoughtSurface(
        modelled_surface(NO_GROUND, PLANE_HEIGHT, SurfaceFinish.MIRROR),
        frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
    )
    bounded = SoughtSurface(
        modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.MIRROR),
        frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
    )
    answers = [
        (
            bool(finder.asked_about(bounded).tolist()),
            bool(finder.asked_about(unbounded).tolist()),
        )
        for finder in (ModelledSurfaceFinder(), MeasuredSurfaceFinder())
    ]
    assert answers == [(True, False), (True, False)]


def test_a_measured_stretch_lands_on_the_grid_the_modelled_one_samples() -> None:
    """
    A rectified pixel samples the world point its own corner puts it over, so a stretch
    whose corner fell between the samples of the stretch it was cut from would rectify
    every point half a pixel away from where the uncut pass had it -- a different
    picture rather than less of the same one.
    """
    measured = MeasuredSurfaceFinder().find(
        SoughtSurface(
            modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT),
            frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
        )
    )
    steps = [
        (measured.region.minimum_x - MODELLED_BOUNDS.minimum_x)
        / MODELLED_BOUNDS.resolution,
        (measured.region.minimum_y - MODELLED_BOUNDS.minimum_y)
        / MODELLED_BOUNDS.resolution,
    ]
    assert steps == pytest.approx([round(step) for step in steps], abs=1e-6)


def test_a_camera_that_returns_no_depth_is_answered_from_the_model() -> None:
    """
    What the world says is not the whole of what a finder needs.

    A camera reporting only colour has nothing to measure a plane in, however well the
    world describes one, so the look falls to the model rather than being refused.
    """
    rules = SurfaceRules()
    mirror = modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.MIRROR)
    colour_only = replace(
        frame_showing(PLANE_BOUNDS, PLANE_HEIGHT),
        depth=np.zeros((480, 640), dtype=float),
    )
    assert rules.surface_in(mirror, colour_only) == mirror


def test_a_measurement_is_declared_only_where_there_is_depth_to_take_it_in() -> None:
    """
    The finder says so itself, so the rules never choose it for a look it cannot answer.
    """
    seen = frame_showing(PLANE_BOUNDS, PLANE_HEIGHT)
    mirror = modelled_surface(MODELLED_BOUNDS, PLANE_HEIGHT, SurfaceFinish.MIRROR)
    colour_only = replace(seen, depth=np.zeros((480, 640), dtype=float))
    finder = MeasuredSurfaceFinder()
    assert [
        bool(finder.asked_about(SoughtSurface(mirror, seen)).tolist()),
        bool(finder.asked_about(SoughtSurface(mirror, colour_only)).tolist()),
    ] == [True, False]


# %% the stated rules, put to the captures they were written for


@pytest.mark.parametrize("capture_name", SceneCapture.names_in())
def test_the_stated_rules_answer_every_shipped_capture_without_needing_a_new_one(
    capture_name: str,
) -> None:
    """
    A stated rule is not derived from a case, so what says it is right is a real look
    put to it: fitting each capture with the finder it should get leaves the tree the
    size it was, because every one of them was already answered that way.

    The two surfaces are the ones the recordings were taken over -- the brushed steel
    table, which the world says takes light like a mirror, and the board's lid, which it
    says nothing about.
    """
    rules = SurfaceRules()
    frame = SceneCapture.load(capture_name).to_frame()
    stated = len(walk_rules(rules.rules.conditions_root))

    for surface, expected in (
        (table_surface(), rules.measured),
        (lid_surface(), rules.modelled),
    ):
        sought = SoughtSurface(surface, frame)
        assert rules.detector_for(sought) is expected
        rules.add_rule(sought, expected)

    assert len(walk_rules(rules.rules.conditions_root)) == stated
