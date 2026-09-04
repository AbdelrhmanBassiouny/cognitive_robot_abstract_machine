"""
Tests for working out how a look is answered from what was asked for, rather than from a
pipeline configured in advance.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.entity_query_language.factories import ConditionType, and_, not_

from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.exceptions import (
    NoWayOfLookingAnswersTheRequest,
)
from experiments.montessori.perception.look_choice import (
    WAY_OF_LOOKING_ATTRIBUTE_NAME,
    RequestedLook,
    SceneToSearch,
    WayOfLooking,
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

# %% what the rules read about a request


def test_an_unnarrowed_request_asks_for_the_pieces_and_the_board():
    asked = RequestedLook.of(SceneRequest())

    assert asked.pieces_are_asked_for
    assert asked.the_board_is_asked_for


def test_a_request_for_shapes_does_not_ask_for_the_board():
    asked = RequestedLook.of(SceneRequest(detection_type=MontessoriShapeDetection))

    assert asked.pieces_are_asked_for
    assert not asked.the_board_is_asked_for


def test_a_request_for_the_board_does_not_ask_for_the_pieces():
    asked = RequestedLook.of(SceneRequest(detection_type=MontessoriBoardDetection))

    assert not asked.pieces_are_asked_for
    assert asked.the_board_is_asked_for


def test_a_request_for_the_holes_asks_for_the_board_that_carries_them():
    asked = RequestedLook.of(SceneRequest(detection_type=ShapeSortingHoleDetection))

    assert not asked.pieces_are_asked_for
    assert asked.the_board_is_asked_for


# %% which way of looking the rules conclude


def test_a_request_for_the_pieces_is_answered_by_searching_the_surfaces(
    pipeline: MontessoriPerceptionPipeline,
):
    chosen = pipeline.look_rules.way_of_looking_for(
        RequestedLook.of(SceneRequest(detection_type=MontessoriShapeDetection))
    )

    assert chosen is pipeline.look_rules.find_the_pieces


def test_a_request_for_the_board_alone_is_answered_without_searching_for_pieces(
    pipeline: MontessoriPerceptionPipeline,
):
    chosen = pipeline.look_rules.way_of_looking_for(
        RequestedLook.of(SceneRequest(detection_type=MontessoriBoardDetection))
    )

    assert chosen is pipeline.look_rules.find_the_board


def test_an_unnarrowed_request_is_answered_by_the_way_that_reports_both(
    pipeline: MontessoriPerceptionPipeline,
):
    chosen = pipeline.look_rules.way_of_looking_for(RequestedLook.of(SceneRequest()))

    assert chosen is pipeline.look_rules.find_the_pieces


# %% a kind of request no rule covers


class DetectionOfSomethingElse(MontessoriDetection):
    """
    A detection neither the pieces nor the board can answer, so no stated rule reaches a
    request narrowed to it.
    """

    @property
    def label(self) -> str:
        return "something else"


class ReportNothing(WayOfLooking):
    """
    A way of looking that answers a request by reporting an empty scene, so a rule added
    at runtime can be told apart from every rule stated when the rules were built.
    """

    def capability(self, request: RequestedLook) -> ConditionType:
        return and_(
            not_(request.pieces_are_asked_for),
            not_(request.the_board_is_asked_for),
        )

    def take(self, scene: SceneToSearch) -> MontessoriScene:
        return MontessoriScene()


def test_a_request_no_rule_covers_is_refused_rather_than_answered_with_nothing(
    pipeline: MontessoriPerceptionPipeline,
):
    unknown = RequestedLook.of(SceneRequest(detection_type=DetectionOfSomethingElse))

    with pytest.raises(NoWayOfLookingAnswersTheRequest):
        pipeline.look_rules.way_of_looking_for(unknown)


def test_a_way_of_looking_added_at_runtime_answers_the_next_request_of_that_kind(
    pipeline: MontessoriPerceptionPipeline,
):
    unknown = RequestedLook.of(SceneRequest(detection_type=DetectionOfSomethingElse))
    added = ReportNothing()

    pipeline.look_rules.add_rule(unknown, added)

    assert pipeline.look_rules.way_of_looking_for(unknown) is added


def test_adding_a_way_of_looking_leaves_the_rules_already_stated_answering_as_before(
    pipeline: MontessoriPerceptionPipeline,
):
    unknown = RequestedLook.of(SceneRequest(detection_type=DetectionOfSomethingElse))

    pipeline.look_rules.add_rule(unknown, ReportNothing())

    assert (
        pipeline.look_rules.way_of_looking_for(RequestedLook.of(SceneRequest()))
        is pipeline.look_rules.find_the_pieces
    )


def test_the_rules_can_be_read_as_a_tree(pipeline: MontessoriPerceptionPipeline):
    rendered = pipeline.look_rules.render_tree(RequestedLook.of(SceneRequest()))

    assert type(pipeline.look_rules.find_the_pieces).__name__ in rendered


# %% what a way of looking then does


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


def test_the_ways_of_looking_carry_the_detectors_the_pipeline_no_longer_holds(
    pipeline: MontessoriPerceptionPipeline,
):
    assert isinstance(pipeline.look_rules.find_the_board, FindTheBoard)
    assert isinstance(pipeline.look_rules.find_the_pieces, FindThePieces)
    assert (
        pipeline.look_rules.find_the_pieces.find_the_board
        is pipeline.look_rules.find_the_board
    )


def test_the_attribute_the_rules_conclude_is_a_real_field_of_a_request():
    """
    The engine names the concluded attribute by string, so the constant that spells it
    is held against the dataclass rather than trusted to have stayed in step with it.
    """
    assert WAY_OF_LOOKING_ATTRIBUTE_NAME in {
        field.name for field in fields(RequestedLook)
    }
