"""
Scoring the frozen question set against a memory and recording the outcome as episode
rows, and the two paper tables computed from what was recorded.
"""

from __future__ import annotations

from krrood.entity_query_language.backends import EntityQueryLanguageBackend
from semantic_digital_twin.reasoning.predicates import SupportedBy

from experiments.episodes.episode import RecordedTrial
from experiments.paper.figure import FigureName
from experiments.questions.long_term_memory import AnythingMovedInTheEpisode
from experiments.questions.question import BloomLevel, Bucket
from experiments.questions.working_memory import ObjectColours, ObjectsSeen
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.testing import two_arm_robot_world

from .test_paper_figures import (
    NO_ABLATION,
    TWIN_BACKEND,
    episode,
    query,
    repeated_question,
    rows_of,
    trial,
)
from .test_questions import QuestionedScene, robot, scene

# %% scoring a question set against a memory


def test_answer_and_record_scores_every_question_of_the_set(
    scene: QuestionedScene, robot: AbstractRobot
):
    recorded = scene.question_set.answer_and_record(robot)

    assert len(recorded) == len(scene.question_set.questions)
    for question, row in zip(scene.question_set.questions, recorded):
        assert row.text == question.english
        assert row.question is question
        assert row.bucket is question.bucket
        assert row.bloom_level is question.bloom_level
        assert row.answered_correctly is True
        assert row.latency >= 0.0


def test_a_scored_question_records_which_backend_answered_each_predicate(
    scene: QuestionedScene, robot: AbstractRobot
):
    """
    A live question is selected in this process, and the predicates its query puts are
    what the latency of answering it is attributed to.
    """
    recorded = scene.question_set.answer_and_record(robot)

    routed = [answered for row in recorded for answered in row.answered_predicates]
    assert {answered.backend_name for answered in routed} == {
        EntityQueryLanguageBackend.__name__
    }
    assert SupportedBy.__name__ in {answered.predicate_name for answered in routed}


def test_an_ordinary_query_is_not_mistaken_for_a_scored_question():
    """
    A query built the way any other query is recorded, not through
    :meth:`~experiments.questions.question_set.QuestionSet.answer_and_record`, still
    names the question it asked but carries no ``answered_correctly``.
    """
    ordinary = query(repeated_question(), "cube, cylinder", 0.1, TWIN_BACKEND)

    assert ordinary.answered_correctly is None


# %% accuracy per bucket and per level of Bloom's taxonomy


def scored_corpus() -> list[RecordedTrial]:
    """
    One trial carrying two scene questions (one right, one wrong) and one temporal
    question over long-term memory (right), plus an ordinary query the tables must
    ignore.
    """
    return [
        trial(
            episode(NO_ABLATION),
            TrialOutcome.SUCCEEDED,
            queries=[
                query(
                    ObjectsSeen(),
                    "cube, cylinder",
                    0.1,
                    answered_correctly=True,
                ),
                query(
                    ObjectColours(),
                    "red, blue",
                    0.1,
                    answered_correctly=False,
                ),
                query(
                    AnythingMovedInTheEpisode(episode_identifier="episode-1"),
                    "cube",
                    0.1,
                    answered_correctly=True,
                ),
                query(repeated_question(), "cube, cylinder", 0.1, TWIN_BACKEND),
            ],
        )
    ]


def test_accuracy_by_bucket_reports_only_scored_buckets_in_bucket_order():
    rows = rows_of(FigureName.ACCURACY_BY_BUCKET, scored_corpus())

    assert [row.bucket for row in rows] == [
        Bucket.SCENE,
        Bucket.TEMPORAL_AND_AGENCY,
    ]
    assert [row.accuracy.measurement_count for row in rows] == [2, 1]
    assert [row.accuracy.average.mean for row in rows] == [0.5, 1.0]


def test_accuracy_by_bloom_level_reports_only_scored_levels_in_taxonomy_order():
    rows = rows_of(FigureName.ACCURACY_BY_BLOOM_LEVEL, scored_corpus())

    assert [row.bloom_level for row in rows] == [
        BloomLevel.REMEMBERING,
        BloomLevel.UNDERSTANDING,
    ]
    assert [row.accuracy.measurement_count for row in rows] == [1, 2]
    assert [row.accuracy.average.mean for row in rows] == [1.0, 0.5]


def test_a_score_with_nothing_scored_is_left_out():
    without_scored_questions = [
        trial(
            episode(NO_ABLATION),
            TrialOutcome.SUCCEEDED,
            queries=[query(repeated_question(), "cube, cylinder", 0.1, TWIN_BACKEND)],
        )
    ]

    assert rows_of(FigureName.ACCURACY_BY_BUCKET, without_scored_questions) == []
    assert rows_of(FigureName.ACCURACY_BY_BLOOM_LEVEL, without_scored_questions) == []
