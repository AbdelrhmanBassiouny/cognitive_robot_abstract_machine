"""
Tests for narrowing a look to the stretch of the world a statement allows it: what each
stated condition leaves to rectify, and that a narrowed look answers what an unnarrowed
one does.

The viewing half of the demonstration is a script rather than a test, so what is checked
here is the steps it takes and the pictures it asks for, through a display that records
them instead of opening a window.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest
from typing_extensions import List, Optional, Tuple

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import (
    MontessoriScene,
    MontessoriShapeDetection,
)
from experiments.montessori.perception.exceptions import LookHasNoReferenceFrame
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    lid_surface,
    perception_pipeline,
    recorded_world,
    region_over,
    searched_workspace,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import FixedScene
from experiments.montessori.perception.viewer import ImageDisplay
from experiments.montessori.perception.watch_narrowing import (
    NarrowingView,
    SearchNarrowing,
    StatedCondition,
    conditions_over,
)
from krrood.entity_query_language.factories import an
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

CAPTURE_NAME = "tracy_pickup_demo"
"""
The shipped capture these tests read, which holds pieces on the table and on the lid.
"""

# %% a display that draws nowhere


@dataclass
class RecordingDisplay(ImageDisplay):
    """
    A place to put pictures that keeps them instead of showing them.

    Whether a viewer opens a window is a property of the display rather than of what
    asked it to draw, so what a run puts on screen is checkable with no screen.
    """

    drawn: List[Tuple[str, np.ndarray]] = field(default_factory=list)
    """
    Every picture handed over, with the name of the window it was meant for.
    """

    closed: bool = False
    """
    Whether the windows were taken down.
    """

    def draw(self, window_name: str, image: np.ndarray) -> None:
        self.drawn.append((window_name, image))

    def wait(self, milliseconds: int) -> Optional[int]:
        """
        :param milliseconds: Ignored: nothing is on screen to be typed at.
        :return: None, as a wait that nobody pressed a key during.
        """
        return None

    def close(self) -> None:
        self.closed = True


# %% the scene these tests look at


@pytest.fixture
def recorded_scene_world() -> World:
    """
    The world the shipped captures' own setup describes.
    """
    return recorded_world()


@pytest.fixture
def capture_pipeline(recorded_scene_world: World) -> MontessoriPerceptionPipeline:
    """
    A pipeline reading the shipped captures, placing what it finds in that world.
    """
    return perception_pipeline(recorded_scene_world)


@pytest.fixture
def capture_frame() -> RgbdFrame:
    """
    The camera data of the capture these tests read.
    """
    return SceneCapture.load(CAPTURE_NAME).to_frame()


def resting_on(name: PrefixedName) -> StatedCondition:
    """
    The condition that the thing sought rests on a named surface.

    :param name: What the world calls the surface.
    """
    return lambda sought: SupportedBy(sought, Body(name=name))


# %% what each stated condition leaves to rectify


def test_a_look_saying_nothing_reads_the_whole_searched_table(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    [bare] = narrowing.steps(capture_frame, ())

    assert bare.region == capture_pipeline.table.region


def test_each_stated_condition_leaves_less_of_the_table_to_read(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    recorded_scene_world: World,
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    steps = narrowing.steps(capture_frame, conditions_over(recorded_scene_world))

    areas = [step.searched_area for step in steps]
    assert areas == sorted(areas, reverse=True)
    assert len(set(areas)) == len(areas)


def test_a_look_supported_by_the_lid_reads_only_where_the_board_was_seen(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
):
    board = capture_pipeline.board_detector.detect(
        capture_pipeline.rectify(capture_frame, capture_pipeline.lid.height),
        capture_pipeline.reference_frame,
    )
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    bare, on_the_lid = narrowing.steps(capture_frame, (resting_on(lid_surface().name),))

    seen = WorkspaceRegion.of_outline(board.outline)
    assert on_the_lid.region.minimum_x <= seen.minimum_x
    assert on_the_lid.region.maximum_x >= seen.maximum_x
    assert on_the_lid.region.minimum_y <= seen.minimum_y
    assert on_the_lid.region.maximum_y >= seen.maximum_y
    assert on_the_lid.searched_area < bare.searched_area


def test_a_look_narrowed_away_from_every_surface_has_nothing_left_to_read(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    recorded_scene_world: World,
):
    searched = searched_workspace()
    elsewhere = region_over(
        recorded_scene_world,
        WorkspaceRegion(
            minimum_x=searched.maximum_x + 1.0,
            maximum_x=searched.maximum_x + 1.5,
            minimum_y=searched.minimum_y,
            maximum_y=searched.maximum_y,
        ),
        "off_the_table",
    )
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    _, nowhere = narrowing.steps(
        capture_frame, (lambda sought: InsideRegion(sought, elsewhere),)
    )

    assert nowhere.region is None
    assert nowhere.searched_area == 0.0


# %% what a narrowed look then answers


def test_a_narrowed_look_reports_what_the_same_look_unnarrowed_reports_there(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
):
    """
    Narrowing is an economy, so the pieces it still reads are read exactly as they were.
    """
    whole = capture_pipeline.detect(capture_frame)
    narrowed = capture_pipeline.detect(
        capture_frame, SceneRequest(supporting_surface=lid_surface().name)
    )

    assert [_as_read(piece) for piece in narrowed.shapes] == [
        _as_read(piece)
        for piece in whole.shapes
        if piece.supporting_surface == lid_surface().name
    ]


def _as_read(piece: MontessoriShapeDetection) -> Tuple[str, float, float, float]:
    """
    What a look made of one piece, to the millimetre it was measured to.

    :param piece: The detection to read.
    """
    seen_at = piece.pose.to_position().to_np()
    return (
        piece.label,
        round(float(seen_at[0]), 3),
        round(float(seen_at[1]), 3),
        round(piece.outline_agreement, 3),
    )


def test_a_region_a_look_cannot_place_is_refused_rather_than_ignored(
    recorded_scene_world: World,
):
    region = region_over(recorded_scene_world, searched_workspace(), "the_whole_table")
    backend = MontessoriPerceptionBackend(
        source=FixedScene(captured=MontessoriScene(shapes=[], board=None))
    )
    statement = an(MontessoriShapeDetection)()
    statement = statement.where(InsideRegion(statement.variable, region))

    with pytest.raises(LookHasNoReferenceFrame):
        backend.region_asked_about(backend.read_request(statement))


# %% the pictures the demonstration draws


def test_every_step_is_drawn_in_a_window_named_by_the_statement_so_far(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    recorded_scene_world: World,
):
    display = RecordingDisplay()
    narrowing = SearchNarrowing(pipeline=capture_pipeline, display=display)

    steps = narrowing.watch(capture_frame, conditions_over(recorded_scene_world))

    assert [name for name, _ in display.drawn] == [
        SearchNarrowing.window_name(view, step)
        for step in steps
        for view in (NarrowingView.CAMERA, NarrowingView.RECTIFIED)
    ]


def test_a_windows_name_says_the_look_is_a_look_and_what_it_states(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    recorded_scene_world: World,
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    steps = narrowing.steps(capture_frame, conditions_over(recorded_scene_world))

    assert all(step.label.startswith("Look for") for step in steps)
    assert steps[0].label in steps[1].label
    assert steps[1].label in steps[2].label


def test_the_rectified_picture_of_a_step_covers_exactly_what_it_left_to_read(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    recorded_scene_world: World,
):
    display = RecordingDisplay()
    narrowing = SearchNarrowing(
        pipeline=capture_pipeline,
        display=display,
        maximum_width=10_000,
        maximum_height=10_000,
    )

    steps = narrowing.watch(capture_frame, conditions_over(recorded_scene_world))

    drawn = dict(display.drawn)
    for step in steps:
        picture = drawn[SearchNarrowing.window_name(NarrowingView.RECTIFIED, step)]
        assert picture.shape[:2] == (
            step.region.height_in_pixels,
            step.region.width_in_pixels,
        )


def test_a_run_with_no_display_draws_nothing_and_still_takes_every_step(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    recorded_scene_world: World,
):
    conditions = conditions_over(recorded_scene_world)

    steps = SearchNarrowing(pipeline=capture_pipeline).watch(capture_frame, conditions)

    assert len(steps) == len(conditions) + 1
