"""
Tests for working out how a look is answered from what was asked for, rather than from a
pipeline configured in advance.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.backends import PerceptionDetector
from krrood.entity_query_language.factories import ConditionType, and_, not_

from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.detector_choice import (
    PieceDetector,
    TargetOnSurface,
)
from experiments.montessori.perception.exceptions import NoDetectorAnswersTheRequest
from experiments.montessori.perception.look_choice import (
    SceneDetector,
    SceneToSearch,
)
from experiments.montessori.perception.pipeline import (
    FindThePieces,
    FindTheBoard,
    MontessoriPerceptionPipeline,
)
from experiments.montessori.perception.scene_request import SceneRequest

from .dataset import montessori_scene_fixtures
from .dataset.montessori_scene_renderer import MontessoriSceneRenderer, PlacedPiece

pytest_plugins = [montessori_scene_fixtures.__name__]

# %% what a request says about itself


def test_an_unnarrowed_request_asks_for_the_pieces_and_the_board():
    asked = SceneRequest()

    assert asked.pieces_are_asked_for
    assert asked.the_board_is_asked_for


def test_a_request_for_shapes_does_not_ask_for_the_board():
    asked = SceneRequest(detection_type=MontessoriShapeDetection)

    assert asked.pieces_are_asked_for
    assert not asked.the_board_is_asked_for


def test_a_request_for_the_board_does_not_ask_for_the_pieces():
    asked = SceneRequest(detection_type=MontessoriBoardDetection)

    assert not asked.pieces_are_asked_for
    assert asked.the_board_is_asked_for


def test_a_request_for_the_holes_asks_for_the_board_that_carries_them():
    asked = SceneRequest(detection_type=ShapeSortingHoleDetection)

    assert not asked.pieces_are_asked_for
    assert asked.the_board_is_asked_for


# %% which detector the rules conclude


def test_a_request_for_the_pieces_is_answered_by_searching_the_surfaces(
    pipeline: MontessoriPerceptionPipeline,
):
    chosen = pipeline.look_rules.detector_for(
        SceneRequest(detection_type=MontessoriShapeDetection)
    )

    assert chosen is pipeline.look_rules.find_the_pieces


def test_a_request_for_the_board_alone_is_answered_without_searching_for_pieces(
    pipeline: MontessoriPerceptionPipeline,
):
    chosen = pipeline.look_rules.detector_for(
        SceneRequest(detection_type=MontessoriBoardDetection)
    )

    assert chosen is pipeline.look_rules.find_the_board


def test_an_unnarrowed_request_is_answered_by_the_detector_that_reports_both(
    pipeline: MontessoriPerceptionPipeline,
):
    chosen = pipeline.look_rules.detector_for(SceneRequest())

    assert chosen is pipeline.look_rules.find_the_pieces


def test_the_rules_are_stated_over_the_request_itself(
    pipeline: MontessoriPerceptionPipeline,
):
    """
    The description a rule reads is the request, not a copy of it: a second class
    restating what a request already says is what the rules were written to avoid, and
    what they conclude is named by the statement they were built from.
    """
    assert pipeline.look_rules.rules.case_type is SceneRequest
    assert pipeline.look_rules.rules.conclusion_attribute_name in vars(SceneRequest())


# %% a kind of request no rule covers


class DetectionOfSomethingElse(MontessoriDetection):
    """
    A detection neither the pieces nor the board can answer, so no stated rule reaches a
    request narrowed to it.
    """

    @property
    def label(self) -> str:
        return "something else"


class ReportNothing(SceneDetector):
    """
    A detector that answers a request by reporting an empty scene, so a rule added at
    runtime can be told apart from every rule stated when the rules were built.
    """

    def capability(self, request: SceneRequest) -> ConditionType:
        return and_(
            not_(request.pieces_are_asked_for),
            not_(request.the_board_is_asked_for),
        )

    def detect(self, scene: SceneToSearch) -> MontessoriScene:
        return MontessoriScene()


def test_a_request_no_rule_covers_is_refused_rather_than_answered_with_nothing(
    pipeline: MontessoriPerceptionPipeline,
):
    unknown = SceneRequest(detection_type=DetectionOfSomethingElse)

    with pytest.raises(NoDetectorAnswersTheRequest):
        pipeline.look_rules.detector_for(unknown)


def test_a_detector_added_at_runtime_answers_the_next_request_of_that_kind(
    pipeline: MontessoriPerceptionPipeline,
):
    unknown = SceneRequest(detection_type=DetectionOfSomethingElse)
    added = ReportNothing()

    pipeline.look_rules.add_rule(unknown, added)

    assert pipeline.look_rules.detector_for(unknown) is added


def test_adding_a_detector_leaves_the_rules_already_stated_answering_as_before(
    pipeline: MontessoriPerceptionPipeline,
):
    unknown = SceneRequest(detection_type=DetectionOfSomethingElse)

    pipeline.look_rules.add_rule(unknown, ReportNothing())

    assert (
        pipeline.look_rules.detector_for(SceneRequest())
        is pipeline.look_rules.find_the_pieces
    )


def test_the_rules_can_be_read_as_a_tree(pipeline: MontessoriPerceptionPipeline):
    rendered = pipeline.look_rules.render_tree(SceneRequest())

    assert type(pipeline.look_rules.find_the_pieces).__name__ in rendered


# %% one detector concept, two families of them


def test_each_family_of_detectors_states_the_kind_of_look_it_answers():
    """
    What a detector's conditions may read is part of its signature, so both families
    answer it from the type they bind rather than from a field stating it again.
    """
    assert issubclass(SceneDetector, PerceptionDetector)
    assert issubclass(PieceDetector, PerceptionDetector)
    assert FindTheBoard.look_type() is SceneRequest
    assert PieceDetector.look_type() is TargetOnSurface


def test_a_detector_answers_only_the_looks_it_states_it_can():
    detector = FindTheBoard()

    assert detector.answers(SceneRequest(detection_type=MontessoriBoardDetection))
    assert not detector.answers(SceneRequest(detection_type=MontessoriShapeDetection))


# %% what a detector then does


def test_a_look_for_the_board_alone_runs_no_piece_detector(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
):
    found = pipeline.detect(
        renderer.render(placed_pieces),
        SceneRequest(detection_type=MontessoriBoardDetection),
    )

    assert found.board is not None
    assert found.shapes == []


def test_a_look_for_the_pieces_reports_the_board_it_measured_the_surfaces_by(
    pipeline: MontessoriPerceptionPipeline,
    renderer: MontessoriSceneRenderer,
    placed_pieces: list[PlacedPiece],
):
    found = pipeline.detect(
        renderer.render(placed_pieces),
        SceneRequest(detection_type=MontessoriShapeDetection),
    )

    assert found.board is not None
    assert len(found.shapes) == len(placed_pieces)


def test_the_detectors_carry_what_the_pipeline_no_longer_holds(
    pipeline: MontessoriPerceptionPipeline,
):
    assert isinstance(pipeline.look_rules.find_the_board, FindTheBoard)
    assert isinstance(pipeline.look_rules.find_the_pieces, FindThePieces)
    assert (
        pipeline.look_rules.find_the_pieces.find_the_board
        is pipeline.look_rules.find_the_board
    )
