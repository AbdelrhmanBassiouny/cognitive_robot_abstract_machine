"""
Tests for answering a query about the Montessori scene by looking at it: what the query
tells the search, what is left for the query itself to apply, and what a look refuses to
answer at all.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from experiments.montessori.perception.backend import PerceptionBackend
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import FixedScene
from experiments.montessori.semantics import MontessoriShapeCategory
from krrood.entity_query_language.exceptions import BackendCannotResolveCondition
from krrood.entity_query_language.factories import an, entity, the, variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.entity_query_language.verbalization.vocabulary.english import Directive

from .dataset import montessori_scene_fixtures
from .dataset.montessori_scene_renderer import MontessoriSceneRenderer, PlacedPiece

pytest_plugins = [montessori_scene_fixtures.__name__]
"""
The rendered scene and pipeline fixtures the tests below ask for by name.
"""


@pytest.fixture
def looking(scene: MontessoriScene) -> PerceptionBackend:
    """
    A backend answering from one already-captured look at the rendered scene.
    """
    return PerceptionBackend(source=FixedScene(captured=scene))


# %% what the query tells the search


def test_the_attribute_the_search_narrows_by_is_one_a_detection_has():
    """
    The backend names the attribute it narrows by, and a rename of that field would
    otherwise leave the name behind without anything failing.
    """
    assert PerceptionBackend.SUPPORTING_SURFACE_ATTRIBUTE_NAME in {
        field.name for field in fields(MontessoriShapeDetection)
    }


def test_the_kind_of_detection_selected_is_what_the_look_is_asked_for():
    piece = variable(MontessoriShapeDetection, [])

    request = PerceptionBackend.read_request(an(entity(piece)).build())

    assert request == SceneRequest(detection_type=MontessoriShapeDetection)


def test_a_condition_on_the_supporting_surface_narrows_the_look_to_it(
    pipeline: MontessoriPerceptionPipeline,
):
    piece = variable(MontessoriShapeDetection, [])
    query = an(entity(piece).where(piece.supporting_surface == pipeline.lid.name))

    request = PerceptionBackend.read_request(query.build())

    assert request == SceneRequest(
        detection_type=MontessoriShapeDetection,
        supporting_surface=pipeline.lid.name,
    )


def test_a_condition_the_look_cannot_act_on_leaves_it_searching_everywhere():
    piece = variable(MontessoriShapeDetection, [])
    query = an(entity(piece).where(piece.category == MontessoriShapeCategory.CUBE))

    request = PerceptionBackend.read_request(query.build())

    assert request.supporting_surface is None


def test_a_condition_about_something_other_than_the_selection_is_refused():
    piece = variable(MontessoriShapeDetection, [])
    hole = variable(ShapeSortingHoleDetection, [])
    query = an(entity(piece).where(hole.category == MontessoriShapeCategory.CUBE))

    with pytest.raises(BackendCannotResolveCondition) as raised:
        PerceptionBackend.read_request(query.build())

    assert raised.value.backend_type is PerceptionBackend


# %% what the look then does


def test_only_the_surface_asked_about_is_searched(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    request = SceneRequest(supporting_surface=pipeline.lid.name)

    searches = pipeline.searched_surfaces(scene.board, request)

    assert [search.surface for search in searches] == [pipeline.lid]


def test_every_surface_is_searched_when_the_request_names_none(
    pipeline: MontessoriPerceptionPipeline, scene: MontessoriScene
):
    searches = pipeline.searched_surfaces(scene.board, SceneRequest())

    assert [search.surface for search in searches] == [pipeline.table, pipeline.lid]


def test_no_piece_is_looked_for_when_only_the_board_was_asked_about(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
):
    frame = renderer.render(placed_pieces)

    asked_about_the_board = pipeline.detect(
        frame, SceneRequest(detection_type=MontessoriBoardDetection)
    )

    assert asked_about_the_board.shapes == []
    assert asked_about_the_board.board is not None


def test_a_look_narrowed_to_one_surface_reports_only_what_rests_on_it(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    piece_on_the_lid: PlacedPiece,
    scene_with_a_piece_on_the_lid: MontessoriScene,
):
    """
    Narrowing is the search itself running differently, not a filter over a full look:
    the table's pieces are never detected, rather than detected and discarded.
    """
    frame = renderer.render([*placed_pieces, piece_on_the_lid])

    asked_about_the_lid = pipeline.detect(
        frame, SceneRequest(supporting_surface=pipeline.lid.name)
    )

    assert [found.supporting_surface for found in asked_about_the_lid.shapes] == [
        pipeline.lid.name
    ]
    assert len(scene_with_a_piece_on_the_lid.shapes) > len(asked_about_the_lid.shapes)


def test_a_look_asked_for_everything_still_finds_the_pieces(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
    scene: MontessoriScene,
):
    frame = renderer.render(placed_pieces)

    asked_for_everything = pipeline.detect(frame, SceneRequest())

    assert len(asked_for_everything.shapes) == len(scene.shapes)


# %% answering a query


def test_a_query_runs_perception_to_answer_itself(scene: MontessoriScene):
    class CountingSource(FixedScene):
        looks: int = 0

        def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
            self.looks += 1
            return self.captured

    source = CountingSource(captured=scene)
    piece = variable(MontessoriShapeDetection, [])
    query = an(entity(piece))

    assert source.looks == 0
    results = list(query.evaluate(backend=PerceptionBackend(source=source)))
    assert source.looks == 1
    assert len(results) == len(scene.shapes)


def test_a_query_selects_a_hole_by_the_shape_it_takes(
    looking: PerceptionBackend, scene: MontessoriScene
):
    hole = variable(ShapeSortingHoleDetection, [])
    query = an(entity(hole).where(hole.category == MontessoriShapeCategory.CUBE))

    holes = list(query.evaluate(backend=looking))

    assert holes == [
        found for found in scene.holes if found.category is MontessoriShapeCategory.CUBE
    ]


def test_a_query_answers_a_pose_a_plan_can_reach_for(
    looking: PerceptionBackend, scene: MontessoriScene
):
    hole = variable(ShapeSortingHoleDetection, [])
    expected = next(
        found
        for found in scene.holes
        if found.category is MontessoriShapeCategory.TRIANGULAR_PRISM
    )

    found = the(
        entity(hole).where(hole.category == MontessoriShapeCategory.TRIANGULAR_PRISM)
    ).evaluate(backend=looking)

    assert next(iter(found)).pose.to_position().to_np() == pytest.approx(
        expected.pose.to_position().to_np()
    )


def test_a_query_over_one_kind_does_not_return_the_other(looking: PerceptionBackend):
    piece = variable(MontessoriShapeDetection, [])

    pieces = list(an(entity(piece)).evaluate(backend=looking))

    assert pieces
    assert all(not isinstance(found, ShapeSortingHoleDetection) for found in pieces)


def test_a_condition_the_search_could_not_act_on_still_filters_the_answer(
    looking: PerceptionBackend, scene: MontessoriScene
):
    piece = variable(MontessoriShapeDetection, [])
    query = an(entity(piece).where(piece.category == MontessoriShapeCategory.CUBE))

    pieces = list(query.evaluate(backend=looking))

    assert pieces == [
        found
        for found in scene.shapes
        if found.category is MontessoriShapeCategory.CUBE
    ]


def test_a_narrowed_search_still_has_its_own_condition_checked_on_the_answer(
    pipeline: MontessoriPerceptionPipeline,
    scene_with_a_piece_on_the_lid: MontessoriScene,
):
    """
    A source that cannot act on the narrowing answers with every surface's pieces, and
    the condition that narrowed the search is still what decides the answer.
    """
    piece = variable(MontessoriShapeDetection, [])
    query = an(entity(piece).where(piece.supporting_surface == pipeline.lid.name))
    on_the_lid = [
        found
        for found in scene_with_a_piece_on_the_lid.shapes
        if found.supporting_surface == pipeline.lid.name
    ]

    pieces = list(
        query.evaluate(
            backend=PerceptionBackend(
                source=FixedScene(captured=scene_with_a_piece_on_the_lid)
            )
        )
    )

    assert on_the_lid
    assert len(on_the_lid) < len(scene_with_a_piece_on_the_lid.shapes)
    assert pieces == on_the_lid


# %% how it reads


def test_a_query_answered_by_looking_verbalizes_as_looking(
    looking: PerceptionBackend,
):
    piece = variable(MontessoriDetection, [])

    text = verbalize_expression(entity(piece), backend=looking)

    assert text.startswith(Directive.LOOK_FOR.value.text)
