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
from typing_extensions import Any, Callable, List, Optional, Tuple

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
    DetectedMontessoriShape,
)
from experiments.montessori.perception.exceptions import LookHasNoReferenceFrame
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.overlay import CameraView, DetectionOverlay
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.hole_geometry import HOLE_NAME_BY_CATEGORY
from experiments.montessori.perception.recorded_setup import (
    board_holes_in,
    camera_in,
    CAMERA_NAME,
    SETUP_NAME,
    perception_pipeline,
    recorded_world,
    region_over,
    searched_workspace,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import FixedScene, RecordedFrame
from experiments.montessori.perception.viewer import ImageDisplay
from experiments.montessori.perception.step_by_step import (
    DEMONSTRATION_CAPTURE,
    NarrowingView,
    RecordedLook,
    SearchNarrowing,
    WatchedCapture,
    show_step_by_step,
)
from experiments.montessori.perception.watch_narrowing import (
    look_for_the_cube_on_the_lid,
)
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.vocabulary.english import Directive
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.reasoning.predicates import (
    Above,
    Between,
    Colored,
    InFrontOf,
    InsideRegion,
    Near,
    RightOf,
    SupportedBy,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

CAPTURE_NAME = DEMONSTRATION_CAPTURE
"""
The shipped capture these tests read, which is the demonstration's own: it holds pieces
on the table and on the lid, so a narrowing has something to leave out.
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


@pytest.fixture
def capture_board(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
) -> MontessoriBoardDetection:
    """
    The board as that capture shows it, which is what says where its holes lie.
    """
    return capture_pipeline.board_in(capture_frame)


@pytest.fixture
def capture_look(
    recorded_scene_world: World,
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    capture_board,
) -> RecordedLook:
    """
    The look these tests state their statements over: the capture's own world, the
    pipeline reading it, its pictures, and the board they show.
    """
    return RecordedLook(
        world=recorded_scene_world,
        pipeline=capture_pipeline,
        frame=capture_frame,
        board=capture_board,
        seen_from=capture_frame.point_of_view(
            recorded_scene_world.root, camera_in(recorded_scene_world, capture_frame)
        ),
    )


@pytest.fixture
def square_hole(recorded_scene_world: World, capture_board) -> Body:
    """
    The board's square hole, placed in the world where this look found the board.
    """
    return board_holes_in(recorded_scene_world, capture_board)[
        HOLE_NAME_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    ]


@pytest.fixture
def lid(capture_pipeline: MontessoriPerceptionPipeline) -> Body:
    """
    The board's lid, as the body of the world the pipeline measured its surface of.
    """
    return capture_pipeline.lid.entity


StatedCondition = Callable[[Any], Any]
"""
Something a statement can say about the piece it is looking for.

Written as a call taking that piece, since a condition is stated about the statement's
own variable and the variable does not exist until the statement does.
"""


def seen_from(world: World) -> HomogeneousTransformationMatrix:
    """
    The point of view a direction stated about this table is read from: the world's own
    frame, which is the one the robot stands and reaches in.

    :param world: The world it stands in.
    """
    return HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=world.root)


def resting_on(surface: Body) -> StatedCondition:
    """
    The condition that the thing sought rests on a surface of the world.

    :param surface: The body of the world the piece rests on.
    """
    return lambda sought: SupportedBy(sought, surface)


def stating(*conditions: StatedCondition) -> Match[DetectedMontessoriShape]:
    """
    A statement asking a look for a piece that satisfies every given condition.

    :param conditions: What it says about the piece, in the order it says them.
    """
    statement = a(DetectedMontessoriShape)()
    if not conditions:
        return statement
    return statement.where(*(condition(statement.variable) for condition in conditions))


# %% what each stated condition leaves to rectify


def test_a_look_saying_nothing_reads_the_whole_searched_table(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    [bare] = narrowing.steps(capture_frame, stating())

    assert bare.region == capture_pipeline.table.region


def test_no_stated_condition_leaves_more_of_the_table_to_read(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    capture_board,
    capture_look: RecordedLook,
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    steps = narrowing.steps(
        capture_frame,
        look_for_the_cube_on_the_lid(capture_look),
        capture_board,
    )

    areas = [step.searched_area for step in steps]
    assert areas == sorted(areas, reverse=True)


def test_each_condition_saying_where_the_thing_is_leaves_less_of_the_table_to_read(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    recorded_scene_world: World,
    square_hole: Body,
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    bare, on_the_lid, in_front = narrowing.steps(
        capture_frame,
        stating(
            resting_on(capture_pipeline.lid.entity),
            lambda sought: InFrontOf(
                sought, square_hole, seen_from(recorded_scene_world)
            ),
        ),
    )

    assert bare.searched_area > on_the_lid.searched_area > in_front.searched_area


def test_a_stated_color_narrows_what_is_fitted_rather_than_where_to_look(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
):
    """
    A colour says which pieces are worth fitting, not where they are, so it leaves the
    same stretch of table to read and fewer pieces to try in it.
    """
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    bare, cyan = narrowing.steps(
        capture_frame, stating(lambda sought: Colored(sought, cube.color))
    )

    assert cyan.region == bare.region
    assert cyan.request.color == cube.color


def test_a_look_supported_by_the_lid_reads_only_where_the_board_was_seen(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
):
    board = capture_pipeline.board_in(capture_frame)
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    bare, on_the_lid = narrowing.steps(
        capture_frame, stating(resting_on(capture_pipeline.lid.entity))
    )

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
    capture_board,
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
        capture_frame, stating(lambda sought: InsideRegion(sought, elsewhere))
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
        capture_frame, SceneRequest(supporting_surface=capture_pipeline.lid.entity)
    )

    assert [_as_read(piece) for piece in narrowed.shapes] == [
        _as_read(piece)
        for piece in whole.shapes
        if piece.supporting_surface == capture_pipeline.lid.name
    ]


def _as_read(piece: DetectedMontessoriShape) -> Tuple[str, float, float, float]:
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


def test_a_placement_a_look_cannot_read_is_refused_rather_than_ignored(
    recorded_scene_world: World,
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
):
    """
    A relation says where a thing is against the frame the world places things in, so a
    look reporting its detections in no frame has nothing to check one against -- and
    the promise to check it is what makes the narrowing an economy rather than the
    answer.
    """
    seen = capture_pipeline.detect(capture_frame).shapes[0]
    region = region_over(recorded_scene_world, searched_workspace(), "the_whole_table")
    backend = MontessoriPerceptionBackend(
        source=FixedScene(captured=MontessoriScene(shapes=[seen]))
    )
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(InsideRegion(statement.variable, region))

    with pytest.raises(LookHasNoReferenceFrame):
        backend.relations_hold(seen, backend.read_request(statement))


# %% the pictures the demonstration draws


def test_a_run_draws_two_windows_per_step_and_a_last_one_for_the_answer(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    capture_board,
    capture_look: RecordedLook,
):
    display = RecordingDisplay()
    narrowing = SearchNarrowing(pipeline=capture_pipeline, display=display)

    steps = narrowing.watch(
        capture_frame,
        look_for_the_cube_on_the_lid(capture_look),
        capture_board,
    )

    assert [name for name, _ in display.drawn] == [
        SearchNarrowing.window_name(view, step)
        for step in steps
        for view in (NarrowingView.CAMERA, NarrowingView.RECTIFIED)
    ] + [SearchNarrowing.window_name(NarrowingView.ANSWER, steps[-1])]


def test_a_windows_name_says_the_look_is_a_look_and_says_more_at_every_step(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    capture_board,
    capture_look: RecordedLook,
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)

    steps = narrowing.steps(
        capture_frame,
        look_for_the_cube_on_the_lid(capture_look),
        capture_board,
    )

    assert all(step.label.startswith("Look for") for step in steps)
    lengths = [len(step.label) for step in steps]
    assert lengths == sorted(lengths)
    assert len({step.label for step in steps}) == len(steps)


@pytest.fixture
def watched(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    capture_board,
    capture_look: RecordedLook,
) -> Tuple[SearchNarrowing, RecordingDisplay, List]:
    """
    The demonstration's own statement watched at full size, with every picture kept.
    """
    display = RecordingDisplay()
    narrowing = SearchNarrowing(
        pipeline=capture_pipeline,
        display=display,
        maximum_width=10_000,
        maximum_height=10_000,
    )
    steps = narrowing.watch(
        capture_frame,
        look_for_the_cube_on_the_lid(capture_look),
        capture_board,
    )
    return narrowing, display, steps


def test_the_rectified_picture_of_a_step_is_what_it_left_to_read_turned_to_the_camera(
    watched,
):
    """
    A rectified patch is indexed the way it is measured, a quarter turn from the way the
    camera sees the same table, so the picture drawn of it is that patch turned back --
    which is what makes a direction stated from where the camera stands read on screen
    the way it was said.
    """
    _, display, steps = watched

    drawn = dict(display.drawn)
    for step in steps:
        picture = drawn[SearchNarrowing.window_name(NarrowingView.RECTIFIED, step)]
        assert picture.shape[:2] == (
            step.region.width_in_pixels,
            step.region.height_in_pixels,
        )


def test_the_rectified_picture_reads_the_way_the_camera_sees_the_plane(
    watched, capture_frame
):
    """
    Measured against the camera's own image rather than assumed: the two pieces on the
    lid keep the way they lie from one another, so what is left of the picture is turned
    the way the statement's own directions are read.
    """
    narrowing, _, steps = watched
    on_the_lid = steps[1]
    pieces = on_the_lid.found

    drawn = narrowing.rectified_view(on_the_lid, capture_frame).to_pixels(
        np.array([piece.pose.to_position().to_np()[:2] for piece in pieces]),
        on_the_lid.plane_height,
    )
    seen = capture_frame.project(
        np.array([piece.pose.to_position().to_np()[:3] for piece in pieces])
    )

    assert len(pieces) == 2
    assert np.array_equal(
        np.sign(np.diff(drawn, axis=0)), np.sign(np.diff(seen, axis=0))
    )


def test_a_steps_pictures_are_what_it_left_to_read_and_carry_no_marks(
    watched, capture_pipeline: MontessoriPerceptionPipeline, capture_frame
):
    """
    A step says where there is still to look, so its two pictures are that stretch of
    the scene as the camera and the detectors read it, with nothing drawn over them.
    """
    narrowing, display, steps = watched
    step = steps[-1]

    drawn = dict(display.drawn)

    assert np.array_equal(
        drawn[SearchNarrowing.window_name(NarrowingView.RECTIFIED, step)],
        narrowing.rectified_view(step, capture_frame).to_image(),
    )
    assert np.array_equal(
        drawn[SearchNarrowing.window_name(NarrowingView.CAMERA, step)],
        capture_pipeline.workspace_over(step.region).clip(
            capture_frame.color, capture_frame
        ),
    )


def test_the_answer_is_marked_in_the_whole_picture_the_narrowing_ends_in(
    watched, capture_frame
):
    """
    What all the narrowing was for is one piece, so the run ends by putting the camera's
    whole image back on screen with that piece boxed in it.
    """
    _, display, steps = watched
    answer = steps[-1]

    drawn = dict(display.drawn)[
        SearchNarrowing.window_name(NarrowingView.ANSWER, answer)
    ]

    assert [piece.category for piece in answer.found] == [MontessoriShapeCategory.CUBE]
    assert np.array_equal(
        drawn,
        DetectionOverlay().draw(
            CameraView(frame=capture_frame), MontessoriScene(shapes=list(answer.found))
        ),
    )
    assert drawn.shape == capture_frame.color.shape


def test_the_demonstration_states_its_way_down_to_the_cube_alone(watched):
    """
    Each condition of the statement the demonstration watches leaves less of the table
    to read and fewer pieces in it, down to the one piece it was written to find.
    """
    _, _, steps = watched

    assert [[piece.category for piece in step.found] for step in steps] == [
        [
            MontessoriShapeCategory.RECTANGULAR_PRISM,
            MontessoriShapeCategory.TRIANGULAR_PRISM,
            MontessoriShapeCategory.CUBE,
            MontessoriShapeCategory.CYLINDER,
        ],
        [MontessoriShapeCategory.CUBE, MontessoriShapeCategory.CYLINDER],
        [MontessoriShapeCategory.CUBE],
        [MontessoriShapeCategory.CUBE],
        [MontessoriShapeCategory.CUBE],
    ]
    assert steps[0].searched_area > steps[1].searched_area > steps[2].searched_area


def test_a_run_with_no_display_draws_nothing_and_still_takes_every_step(
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    capture_board,
    capture_look: RecordedLook,
):
    narrowing = SearchNarrowing(pipeline=capture_pipeline)
    statement = look_for_the_cube_on_the_lid(capture_look)

    watched = narrowing.watch(capture_frame, statement, capture_board)

    assert [step.label for step in watched] == [
        step.label for step in narrowing.steps(capture_frame, statement, capture_board)
    ]


# %% what a stated placement leaves for a look to report


@pytest.fixture
def looking_at_the_capture(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
) -> MontessoriPerceptionBackend:
    """
    A backend that takes a fresh look at the capture for every statement, so what a
    statement narrows is what is actually searched.
    """
    return MontessoriPerceptionBackend(
        source=RecordedFrame(pipeline=capture_pipeline, frame=capture_frame)
    )


def looking_on_the_lid(lid: Body, condition: StatedCondition):
    """
    A statement asking a look for a piece resting on the board's lid that also satisfies
    one further condition.

    :param lid: The body of the world the piece rests on.
    :param condition: The condition to add.
    """
    statement = a(DetectedMontessoriShape)()
    statement = statement.where(resting_on(lid)(statement.variable))
    return statement.where(condition(statement.variable))


def categories_reported(found) -> List[MontessoriShapeCategory]:
    """
    :param found: What a look reported.
    :return: What each piece was recognised as.
    """
    return [piece.category for piece in found]


def test_which_way_a_piece_lies_from_a_hole_is_read_from_where_it_is_seen(
    looking_at_the_capture: MontessoriPerceptionBackend,
    square_hole: Body,
    capture_frame,
    recorded_scene_world: World,
    lid: Body,
):
    """
    Read from where the camera stands, a direction means what it means on screen.

    Measured on this capture: the cube stands 28 mm above the square hole in the picture
    and the cylinder 34 mm to its right, so *right of* leaves the cylinder and the cube
    is told from it by *above* -- which the two of them standing on one table is what
    makes possible, since neither is above the other in the world.
    """
    seen = capture_frame.point_of_view(recorded_scene_world.root)

    assert categories_reported(
        looking_on_the_lid(
            lid, lambda sought: Above(sought, square_hole, seen)
        ).evaluate(backend=looking_at_the_capture)
    ) == [MontessoriShapeCategory.CUBE]
    assert categories_reported(
        looking_on_the_lid(
            lid, lambda sought: RightOf(sought, square_hole, seen)
        ).evaluate(backend=looking_at_the_capture)
    ) == [MontessoriShapeCategory.CYLINDER]


def test_the_two_sides_of_a_hole_hold_different_pieces(
    looking_at_the_capture: MontessoriPerceptionBackend,
    square_hole: Body,
    recorded_scene_world: World,
    lid: Body,
):
    """
    Measured on this capture rather than assumed: the cube stands in front of the square
    hole and to the robot's left of it, the cylinder behind it and to the robot's right,
    so which direction is stated decides which of the two a look reports.
    """
    seen = seen_from(recorded_scene_world)

    assert categories_reported(
        looking_on_the_lid(
            lid, lambda sought: InFrontOf(sought, square_hole, seen)
        ).evaluate(backend=looking_at_the_capture)
    ) == [MontessoriShapeCategory.CUBE]
    assert categories_reported(
        looking_on_the_lid(
            lid, lambda sought: RightOf(sought, square_hole, seen)
        ).evaluate(backend=looking_at_the_capture)
    ) == [MontessoriShapeCategory.CYLINDER]


def test_a_look_between_two_holes_reports_what_stands_between_them(
    looking_at_the_capture: MontessoriPerceptionBackend,
    recorded_scene_world: World,
    capture_board,
    lid: Body,
):
    holes = board_holes_in(recorded_scene_world, capture_board)

    found = looking_on_the_lid(
        lid,
        lambda sought: Between(
            sought,
            holes[HOLE_NAME_BY_CATEGORY[MontessoriShapeCategory.CUBE]],
            holes[HOLE_NAME_BY_CATEGORY[MontessoriShapeCategory.TRIANGULAR_PRISM]],
        ),
    ).evaluate(backend=looking_at_the_capture)

    assert categories_reported(found) == [MontessoriShapeCategory.CUBE]


def test_a_look_near_a_hole_reaches_as_far_as_the_radius_it_was_asked_for(
    looking_at_the_capture: MontessoriPerceptionBackend,
    square_hole: Body,
    lid: Body,
):
    """
    The two pieces on this lid stand 35 mm and 75 mm from the square hole, so a reach
    between the two tells them apart and one past both reports them both.
    """
    close = looking_on_the_lid(
        lid, lambda sought: Near(sought, square_hole, radius=0.05)
    ).evaluate(backend=looking_at_the_capture)
    wider = looking_on_the_lid(
        lid, lambda sought: Near(sought, square_hole, radius=0.10)
    ).evaluate(backend=looking_at_the_capture)

    assert categories_reported(close) == [MontessoriShapeCategory.CUBE]
    assert set(categories_reported(wider)) == {
        MontessoriShapeCategory.CUBE,
        MontessoriShapeCategory.CYLINDER,
    }


def test_a_look_asked_for_a_color_reports_only_the_pieces_that_wear_it(
    looking_at_the_capture: MontessoriPerceptionBackend,
):
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    prism = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.TRIANGULAR_PRISM]
    statement = a(DetectedMontessoriShape)()

    found = statement.where(Colored(statement.variable, prism.color)).evaluate(
        backend=looking_at_the_capture
    )

    assert cube.color != prism.color
    assert found
    assert all(piece.color == prism.color for piece in found)


def test_a_piece_is_found_in_a_stretch_smaller_than_the_piece_itself(
    looking_at_the_capture: MontessoriPerceptionBackend,
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_frame,
    lid: Body,
):
    """
    A statement says where the thing is, not which pixels may be read, so a stretch
    narrower than the piece standing in it is still a stretch that piece is found in --
    and it is measured exactly as the unnarrowed look measured it.
    """
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    [unnarrowed] = [
        piece
        for piece in capture_pipeline.detect(capture_frame).shapes
        if piece.category is cube.category
    ]
    reach = cube.radius / 2

    [narrowed] = looking_on_the_lid(
        lid, lambda sought: Near(sought, unnarrowed.pose, radius=reach)
    ).evaluate(backend=looking_at_the_capture)

    assert reach < cube.radius
    assert _as_read(narrowed) == _as_read(unnarrowed)


# %% how the statement the demonstration watches reads


def test_the_camera_is_put_in_the_world_where_the_look_was_taken_from(
    recorded_scene_world: World, capture_frame
):
    """
    A direction is read from somewhere, and a recording carries no camera, so the camera
    is placed in the world from the look itself -- at the very spot that look was taken
    from, and named so a statement can say it was seen from there.
    """
    camera = camera_in(recorded_scene_world, capture_frame)

    assert camera.name == PrefixedName(CAMERA_NAME, SETUP_NAME)
    assert camera.global_pose.to_np() == pytest.approx(
        capture_frame.point_of_view(recorded_scene_world.root).to_np()
    )


def test_the_statement_reads_as_one_look_taken_from_the_camera(
    capture_frame,
    capture_pipeline: MontessoriPerceptionPipeline,
    capture_look: RecordedLook,
):
    """
    The whole statement is one look: the things it relates the piece to are described
    inside it rather than opening looks of their own, and every direction it states says
    the camera it was read from rather than the matrix that camera's pose is kept as.
    """
    statement = look_for_the_cube_on_the_lid(capture_look)
    looking = MontessoriPerceptionBackend(
        source=RecordedFrame(pipeline=capture_pipeline, frame=capture_frame)
    )

    text = verbalize_expression(statement, backend=looking)

    assert text.count(Directive.LOOK_FOR.value.text) == 1
    assert text.count(f"as seen from the {CAMERA_NAME}") == 2


# %% the demonstration is one call, and everything it needs is a source file's


def test_a_capture_named_on_the_command_line_is_the_one_watched():
    """
    Which capture a run watches, and whether it draws anything, is what the command line
    says, and the demonstration's own capture where it says nothing.
    """
    asked_for = WatchedCapture.from_command_line(["some_capture", "--without-windows"])
    unasked = WatchedCapture.from_command_line([])

    assert asked_for.name == "some_capture"
    assert asked_for.draws_windows is False
    assert unasked.name == DEMONSTRATION_CAPTURE
    assert unasked.draws_windows is True


def test_a_look_taken_from_a_capture_carries_the_board_that_capture_shows(
    capture_pipeline: MontessoriPerceptionPipeline, capture_frame
):
    """
    A statement is written over a look rather than over a capture name, so taking one
    settles the world it is described in, the pictures it reads and the board they show.
    """
    look = RecordedLook.taken_from(
        WatchedCapture(name=CAPTURE_NAME, draws_windows=False)
    )

    assert look.pipeline.table.name == capture_pipeline.table.name
    assert look.board.pose.to_position().to_np() == pytest.approx(
        capture_pipeline.board_in(capture_frame).pose.to_position().to_np()
    )


def test_watching_a_statement_step_by_step_needs_nothing_but_the_statement(
    capture_look: RecordedLook,
):
    """
    The demonstration names the statement and nothing else: the capture, the world, the
    pipeline and the display are the watching's rather than the caller's.
    """
    watched = show_step_by_step(
        look_for_the_cube_on_the_lid,
        WatchedCapture(name=CAPTURE_NAME, draws_windows=False),
    )

    taken_by_hand = SearchNarrowing(pipeline=capture_look.pipeline).steps(
        capture_look.frame,
        look_for_the_cube_on_the_lid(capture_look),
        capture_look.board,
    )
    assert [step.label for step in watched] == [step.label for step in taken_by_hand]
