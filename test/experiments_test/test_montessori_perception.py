"""
Tests for the continuous Montessori perception pipeline and the query interface it
answers through.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from typing_extensions import List

from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.hypotheses import (
    BelievedPlace,
    PieceHypothesis,
)
from experiments.montessori.perception.occupancy import Occupancy, OccupiedVolume
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.scene_source import FixedScene, PerceivedObjects
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY, hue_distance
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.montessori.world import MontessoriWorld
from krrood.entity_query_language.factories import a, the
from krrood.patterns.belief_source import BeliefSource
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Pose

from .dataset import montessori_scene_fixtures
from .dataset.montessori_belief_sources import SomethingThatAskedForALook
from .dataset.montessori_scene_fixtures import SCENE_REGION
from .dataset.montessori_scene_renderer import (
    LID_COLOR,
    MontessoriSceneRenderer,
    PlacedPiece,
)

pytest_plugins = [montessori_scene_fixtures.__name__]
"""
The rendered scene and pipeline fixtures the tests below ask for by name.
"""

# %% the pipeline


def test_pipeline_finds_every_hole_the_board_has(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    assert scene.board is not None
    assert len(scene.holes) == len(renderer.hole_footprints())


def test_pipeline_puts_each_hole_within_three_millimetres_of_its_true_centre(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    detected = [tuple(hole.pose.to_position().to_np()[:2]) for hole in scene.holes]

    for footprint in renderer.hole_footprints():
        expected_x, expected_y = renderer.hole_center(footprint)
        nearest = min(math.hypot(x - expected_x, y - expected_y) for x, y in detected)
        assert nearest == pytest.approx(0.0, abs=0.003)


def test_pipeline_reports_hole_centres_on_the_board_lid(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    for hole in scene.holes:
        assert float(hole.pose.to_position().to_np()[2]) == pytest.approx(
            renderer.lid_height
        )


def test_pipeline_recognises_the_shape_of_the_widest_holes(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer
):
    expected = {
        footprint.category
        for footprint in renderer.hole_footprints()
        if min(footprint.size.x, footprint.size.y) > 0.02
    }

    assert expected <= {hole.category for hole in scene.holes}


def test_pipeline_finds_each_loose_piece_where_it_stands(
    scene: MontessoriScene, placed_pieces: list[PlacedPiece]
):
    detected = [tuple(piece.pose.to_position().to_np()[:2]) for piece in scene.shapes]

    for placed in placed_pieces:
        nearest = min(math.hypot(x - placed.x, y - placed.y) for x, y in detected)
        assert nearest == pytest.approx(0.0, abs=0.006)


def test_pipeline_cancels_the_parallax_that_stretches_a_piece(
    scene: MontessoriScene, renderer: MontessoriSceneRenderer, placed_pieces
):
    [cube] = [
        placed
        for placed in placed_pieces
        if placed.category is MontessoriShapeCategory.CUBE
    ]
    [true_footprint] = [
        footprint
        for footprint in renderer.hole_footprints()
        if footprint.category is MontessoriShapeCategory.CUBE
    ]
    nearest = min(
        scene.shapes,
        key=lambda piece: math.hypot(
            float(piece.pose.to_position().to_np()[0]) - cube.x,
            float(piece.pose.to_position().to_np()[1]) - cube.y,
        ),
    )

    assert nearest.footprint.length == pytest.approx(
        max(true_footprint.size.x, true_footprint.size.y), abs=0.008
    )


def test_pipeline_does_not_report_the_board_lid_as_a_loose_piece(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    """
    Whatever stands within the board's outline rests on its lid, so the table's own pass
    may report nothing there -- least of all the lid itself.
    """
    assert scene.board is not None
    for piece in scene.shapes:
        if piece.supporting_surface == pipeline.lid.name:
            continue
        position = piece.pose.to_position().to_np()
        assert not scene.board.encloses(float(position[0]), float(position[1]))


def test_pipeline_reports_no_board_when_none_is_in_view(
    pipeline: MontessoriPerceptionPipeline, renderer: MontessoriSceneRenderer
):
    empty = renderer.render([])
    empty.color[:, :] = cv2.cvtColor(
        np.full((1, 1, 3), (30, 13, 156), dtype=np.uint8), cv2.COLOR_HSV2BGR
    )[0, 0]

    assert pipeline.detect(empty).board is None


# %% pieces standing on a raised surface


@pytest.fixture
def piece_on_the_lid(renderer: MontessoriSceneRenderer) -> PlacedPiece:
    """
    A cube standing on the board's lid, clear of the holes cut through it.
    """
    x, y = renderer.clear_lid_position()
    return PlacedPiece(
        MontessoriShapeCategory.CUBE, x=x, y=y, surface_height=renderer.lid_height
    )


@pytest.fixture
def scene_with_a_piece_on_the_lid(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
) -> MontessoriScene:
    return pipeline.detect(renderer.render([*placed_pieces, piece_on_the_lid]))


def _pieces_near(
    scene: MontessoriScene, placed: PlacedPiece
) -> list[MontessoriShapeDetection]:
    """
    The detections standing within one piece's own outline of where it was placed.

    :param scene: The look at the scene to search.
    :param placed: The piece whose position the detections are measured against.
    """
    reach = placed.known_piece.turned_outline(0.0).max()
    return [
        piece
        for piece in scene.shapes
        if math.hypot(
            float(piece.pose.to_position().to_np()[0]) - placed.x,
            float(piece.pose.to_position().to_np()[1]) - placed.y,
        )
        <= reach
    ]


def test_a_piece_standing_on_the_board_lid_is_found_where_it_stands(
    scene_with_a_piece_on_the_lid: MontessoriScene, piece_on_the_lid: PlacedPiece
):
    detected = [
        tuple(piece.pose.to_position().to_np()[:2])
        for piece in scene_with_a_piece_on_the_lid.shapes
    ]

    nearest = min(
        math.hypot(x - piece_on_the_lid.x, y - piece_on_the_lid.y) for x, y in detected
    )
    assert nearest == pytest.approx(0.0, abs=0.006)


def test_a_piece_standing_on_the_lid_is_reported_once(
    scene_with_a_piece_on_the_lid: MontessoriScene, piece_on_the_lid: PlacedPiece
):
    assert len(_pieces_near(scene_with_a_piece_on_the_lid, piece_on_the_lid)) == 1


def test_a_piece_standing_on_the_lid_rests_at_the_lid_height(
    scene_with_a_piece_on_the_lid: MontessoriScene,
    piece_on_the_lid: PlacedPiece,
    renderer: MontessoriSceneRenderer,
):
    [detected] = _pieces_near(scene_with_a_piece_on_the_lid, piece_on_the_lid)

    assert detected.surface_height == pytest.approx(renderer.lid_height, abs=0.001)


def test_a_piece_standing_on_the_lid_is_attributed_to_the_lid(
    scene_with_a_piece_on_the_lid: MontessoriScene,
    piece_on_the_lid: PlacedPiece,
    pipeline: MontessoriPerceptionPipeline,
):
    [detected] = _pieces_near(scene_with_a_piece_on_the_lid, piece_on_the_lid)

    assert detected.supporting_surface == pipeline.lid.name


def test_a_piece_standing_on_the_table_is_attributed_to_the_table(
    scene_with_a_piece_on_the_lid: MontessoriScene,
    placed_pieces: list[PlacedPiece],
    pipeline: MontessoriPerceptionPipeline,
):
    for placed in placed_pieces:
        [detected] = _pieces_near(scene_with_a_piece_on_the_lid, placed)
        assert detected.supporting_surface == pipeline.table.name


def test_the_board_is_still_found_under_a_piece_standing_on_its_lid(
    scene_with_a_piece_on_the_lid: MontessoriScene,
    renderer: MontessoriSceneRenderer,
):
    assert scene_with_a_piece_on_the_lid.board is not None
    assert len(scene_with_a_piece_on_the_lid.holes) == len(renderer.hole_footprints())


# %% the table the board stands in front of


def test_what_the_board_hides_reaches_from_the_table_up_to_its_own_lid(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
):
    frame = renderer.render([*placed_pieces, piece_on_the_lid])
    board = pipeline.detect(frame).board

    hidden = pipeline.table_hidden_by(board, frame)

    assert hidden.bottom == pytest.approx(pipeline.table.height)
    assert hidden.top == pytest.approx(board.lid_height)


def test_what_the_board_hides_covers_the_table_it_stands_on(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
):
    frame = renderer.render([*placed_pieces, piece_on_the_lid])
    board = pipeline.detect(frame).board
    standing_on_the_table = OccupiedVolume(
        outline=board.outline, bottom=pipeline.table.height, top=board.lid_height
    )

    hidden = pipeline.table_hidden_by(board, frame)

    assert hidden.shared_area(standing_on_the_table) == pytest.approx(
        standing_on_the_table.area, rel=1e-3
    )


def test_a_reading_taken_off_the_table_the_board_hides_is_not_reported(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
):
    frame = renderer.render([*placed_pieces, piece_on_the_lid])
    scene = pipeline.detect(frame)
    occupancy = Occupancy()
    occupancy.claim(pipeline.table_hidden_by(scene.board, frame))
    against_the_board = MontessoriShapeDetection(
        pose=Pose.from_xyz_rpy(
            *scene.board.pose.to_position().to_np()[:2],
            pipeline.table.height + 0.015,
        ),
        footprint=scene.shapes[0].footprint,
        hypothesis=scene.shapes[0].hypothesis,
        outline=scene.board.outline,
        category=MontessoriShapeCategory.CUBE,
        supporting_surface=pipeline.table.name,
        height=0.03,
        outline_agreement=0.7,
    )

    assert occupancy.keep_one_detection_per_place([against_the_board]) == []


# %% what a look expects to find before it segments anything


def test_a_look_expects_the_piece_the_world_says_it_placed(
    renderer: MontessoriSceneRenderer,
):
    """
    The world names which piece it put where, so the belief names one candidate rather
    than every piece the set contains.
    """
    montessori = MontessoriWorld()
    pipeline = MontessoriPerceptionPipeline(
        table=WorkspaceSurface(
            name=PrefixedName("table", "world_expectations"),
            region=SCENE_REGION,
            height=renderer.table_height,
        ),
        lid=WorkspaceSurface(
            name=PrefixedName("board_lid", "world_expectations"),
            region=SCENE_REGION,
            height=renderer.lid_height,
        ),
        world=montessori.world,
    )
    placed = montessori.world.get_semantic_annotations_by_type(MontessoriShape)

    from_the_world = [
        hypothesis
        for hypothesis in pipeline.expected_pieces()
        if hypothesis.source is montessori.world
    ]

    assert {hypothesis.candidates for hypothesis in from_the_world} == {
        (KNOWN_PIECE_BY_CATEGORY[shape.shape_category],)
        for shape in placed
        if pipeline.table.region.contains(
            *shape.root.global_pose.to_position().to_np()[:2]
        )
    }


def test_a_look_with_no_world_behind_it_expects_nothing_of_its_own(
    pipeline: MontessoriPerceptionPipeline,
):
    assert pipeline.world is None
    assert pipeline.expected_pieces() == []


# %% a piece colour cannot separate from what it rests on


def lid_search(
    pipeline: MontessoriPerceptionPipeline, frame
) -> tuple[SurfaceSearch, MontessoriBoardDetection]:
    """
    The board's own pass over one frame, and the board it found.

    :param pipeline: The pipeline taking the look.
    :param frame: The camera data to search.
    """
    board = pipeline.board_detector.detect(
        pipeline.rectify(frame, pipeline.lid.height), pipeline.reference_frame
    )
    [search] = [
        search
        for search in pipeline.searched_surfaces(board)
        if search.surface is pipeline.lid
    ]
    return search, board


def pieces_on_the_lid(
    pipeline: MontessoriPerceptionPipeline, frame, expected
) -> List[MontessoriShapeDetection]:
    """
    What one pass over the board's lid finds, given what it was told to expect.

    :param pipeline: The pipeline taking the look.
    :param frame: The camera data to search.
    :param expected: What is believed to be on the lid already.
    """
    search, _ = lid_search(pipeline, frame)
    return pipeline.piece_detector.detect(
        pipeline.rectify(frame, pipeline.lid.height),
        pipeline.rectify(
            frame, pipeline.lid.height + pipeline.piece_detector.piece_height
        ),
        frame,
        pipeline.reference_frame,
        search,
        expected,
    )


@pytest.fixture
def prism_on_the_lid(renderer: MontessoriSceneRenderer) -> PlacedPiece:
    """
    An amber prism standing on the board's wooden lid, which measures within the hue
    tolerance of the lid itself, so colour segmentation cannot cut it out.
    """
    stands_at = renderer.clear_lid_position()
    return PlacedPiece(
        MontessoriShapeCategory.TRIANGULAR_PRISM,
        x=stands_at[0],
        y=stands_at[1],
        surface_height=renderer.lid_height,
    )


def test_a_piece_wearing_the_surfaces_own_hue_is_not_separated_from_it_by_colour(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    prism_on_the_lid: PlacedPiece,
):
    """
    The lid's wood and the amber pieces measure within the hue tolerance of each other,
    so a mask of the piece's colour takes the whole lid with it and leaves no outline.
    """
    prism = prism_on_the_lid.known_piece
    assert (
        hue_distance(prism.hue, LID_COLOR[0]) <= pipeline.piece_detector.hue_tolerance
    )

    found = pieces_on_the_lid(
        pipeline, renderer.render([prism_on_the_lid]), expected=()
    )

    assert not [
        piece
        for piece in found
        if piece.pose.to_position().to_np()[:2]
        == pytest.approx((prism_on_the_lid.x, prism_on_the_lid.y), abs=0.01)
    ]


def test_a_piece_wearing_the_surfaces_own_hue_is_found_where_it_is_expected(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    prism_on_the_lid: PlacedPiece,
):
    """
    The evidence is in the picture either way; the belief is what makes it reachable.
    """
    expected = PieceHypothesis(
        place=BelievedPlace(
            surface=pipeline.lid.name,
            center=PlanarPoint(prism_on_the_lid.x, prism_on_the_lid.y),
        ),
        source=SomethingThatAskedForALook(),
        candidates=(prism_on_the_lid.known_piece,),
    )

    found = pieces_on_the_lid(
        pipeline, renderer.render([prism_on_the_lid]), expected=[expected]
    )

    [answered] = [piece for piece in found if piece.hypothesis is expected]
    assert answered.category is prism_on_the_lid.category
    assert answered.pose.to_position().to_np()[:2] == pytest.approx(
        (prism_on_the_lid.x, prism_on_the_lid.y), abs=0.005
    )


def test_a_detection_carries_the_belief_it_answered(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    """
    A result says what was looked for and what suggested it, not only what was found.
    """
    for piece in scene.shapes:
        assert isinstance(piece.hypothesis.source, BeliefSource)
        assert piece.category in {
            candidate.category for candidate in piece.hypothesis.candidates
        }


def test_a_detection_a_colour_suggested_names_the_detector_that_read_it(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    """
    The source is the detector itself, so a reader can ask it how it was looking.
    """
    assert scene.shapes
    for piece in scene.shapes:
        assert piece.hypothesis.source is pipeline.piece_detector


# %% querying it


def test_a_query_over_perceived_objects_runs_perception_to_answer_itself(
    scene: MontessoriScene,
):
    class CountingSource(FixedScene):
        looks: int = 0

        def scene(self) -> MontessoriScene:
            self.looks += 1
            return self.captured

    source = CountingSource(captured=scene)
    perceived = PerceivedObjects(source=source)
    query = a(MontessoriShapeDetection).from_(perceived)

    assert source.looks == 0
    results = query.tolist()
    assert source.looks == 1
    assert len(results) == len(scene.shapes)


def test_a_query_selects_a_hole_by_the_shape_it_takes(scene: MontessoriScene):
    perceived = PerceivedObjects(source=FixedScene(captured=scene))

    holes = (
        a(ShapeSortingHoleDetection)(category=MontessoriShapeCategory.CUBE)
        .from_(perceived)
        .tolist()
    )

    assert holes
    for hole in holes:
        assert hole.category is MontessoriShapeCategory.CUBE


def test_a_query_answers_a_pose_a_plan_can_reach_for(scene: MontessoriScene):
    perceived = PerceivedObjects(source=FixedScene(captured=scene))
    [expected] = [
        hole
        for hole in scene.holes
        if hole.category is MontessoriShapeCategory.TRIANGULAR_PRISM
    ][:1]

    hole = the(
        a(ShapeSortingHoleDetection)(category=MontessoriShapeCategory.TRIANGULAR_PRISM)
        .from_(perceived)
        .expression
    ).tolist()[0]

    assert hole.pose.to_position().to_np() == pytest.approx(
        expected.pose.to_position().to_np()
    )


def test_a_query_over_one_kind_does_not_return_the_other(scene: MontessoriScene):
    perceived = PerceivedObjects(source=FixedScene(captured=scene))

    pieces = a(MontessoriShapeDetection).from_(perceived).tolist()

    assert pieces
    assert all(not isinstance(piece, ShapeSortingHoleDetection) for piece in pieces)


# %% how tall a piece is taken to stand


def test_a_piece_the_depth_image_cannot_resolve_stands_at_its_nominal_height(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    nominal = pipeline.piece_detector.piece_height
    stands_at = {
        surface.name: surface.height for surface in (pipeline.table, pipeline.lid)
    }

    for piece in scene.shapes:
        resting_height = stands_at[piece.supporting_surface]
        assert piece.height == pytest.approx(nominal)
        assert piece.surface_height == pytest.approx(resting_height)
        assert piece.top_height == pytest.approx(resting_height + nominal)


def test_a_hole_has_no_thickness_to_stand_above_its_own_surface(
    scene: MontessoriScene,
):
    hole = scene.holes[0]

    assert hole.top_height == hole.surface_height
