"""
Every table the paper prints, computed from the trials a run recorded.

The corpus below is built in memory rather than read back out of a database, so what is
asserted is the arithmetic each figure does and not the round trip - which
:mod:`test_paper_figures_from_the_database` covers separately.
"""

from __future__ import annotations

import pytest
from coraplex.datastructures.enums import ExecutionType

from experiments.episodes.episode import (
    AnsweredPredicate,
    Episode,
    InsertionAttempt,
    InsertionOutcome,
    RecordedQuery,
    RecordedTrial,
)
from experiments.experiment_definitions import Unit
from experiments.paper.figure import FigureFile, FigureName
from experiments.paper.figure_set import FigureSet
from experiments.paper.measurement import RunConditions
from experiments.paper.outcomes import ConditionOutcome, PredictionScore
from experiments.paper.queries import BackendLatency
from experiments.questions.question import Question
from experiments.scenarios.trial import TrialOutcome

from .test_episodes import SortingFailureType, minimal_plan

# %% the corpus every figure below is computed from

NO_ABLATION = RunConditions(condition_names=())
"""
The run that kept every knowledge source, which the ablated runs are compared against.
"""

WITHOUT_HOLE_SHAPES = RunConditions(condition_names=("NoHoleShapeKnowledge",))
"""
The run with the hole-shape knowledge taken away.
"""

SQUARE_HOLE = "square_hole_1"
"""
The shape one of the recorded attempts was made at.
"""

ROUND_HOLE = "circular_hole_1"
"""
The shape the other recorded attempts were made at.
"""

TWIN_BACKEND = "SemanticDigitalTwinBackend"
"""
The backend one of the recorded predicates was routed to, named as its class is.
"""

DETECTOR_BACKEND = "DetectorBackend"
"""
The backend the other recorded predicates were routed to.
"""

WHAT_IS_ON_THE_TABLE = "an(entity(body).where(body.supported_by == table))"
"""
The query asked repeatedly, so that determinism has repetitions to measure.
"""

WHERE_IS_THE_CUBE = "the(entity(body).where(body.name == cube)).position"
"""
The query asked only once, which determinism therefore has nothing to say about.
"""


def episode(
    conditions: RunConditions,
    execution_type: ExecutionType = ExecutionType.SIMULATED,
) -> Episode:
    """
    One recorded run of the sorting scenario.

    :param conditions: The knowledge sources the run switched off.
    :param execution_type: Whether the run happened in a simulator or on the robot.
    """
    return Episode(
        scenario_name="montessori_sorting",
        execution_type=execution_type,
        condition_names=list(conditions.condition_names),
    )


def trial(
    of_episode: Episode,
    outcome: TrialOutcome,
    duration: float = 10.0,
    insertion_attempts: list[InsertionAttempt] | None = None,
    queries: list[RecordedQuery] | None = None,
) -> RecordedTrial:
    """
    One trial of a recorded run.

    :param of_episode: The episode the trial belongs to.
    :param outcome: Whether the trial reached the scenario's goal.
    :param duration: How long the trial took.
    :param insertion_attempts: The insertions attempted while it ran.
    :param queries: The queries asked while it ran.
    """
    return RecordedTrial(
        episode=of_episode,
        outcome=outcome,
        duration=duration,
        insertion_attempts=list(insertion_attempts or []),
        queries=list(queries or []),
    )


def attempt(
    shape_name: str,
    outcome: InsertionOutcome,
    predicted_failure: SortingFailureType | None = None,
    observed_failure: SortingFailureType | None = None,
) -> InsertionAttempt:
    """
    One attempt to insert a shape, with what was predicted of it and what happened.

    :param shape_name: The shape the attempt was made at.
    :param outcome: How the attempt ended.
    :param predicted_failure: The failure predicted before it ran.
    :param observed_failure: The failure read off what happened.
    """
    return InsertionAttempt(
        shape_name=shape_name,
        plan=minimal_plan(),
        outcome=outcome,
        predicted_failure=predicted_failure,
        observed_failure=observed_failure,
    )


def query(
    text: str,
    answer: str,
    latency: float,
    *backends: str,
    question: Question | None = None,
    answered_correctly: bool | None = None,
) -> RecordedQuery:
    """
    One query asked while a trial ran.

    :param text: The query as it was asked.
    :param answer: The answer as it was rendered.
    :param latency: Seconds the query took to answer.
    :param backends: The backend each of its predicates was routed to.
    :param question: The question of the frozen set this query answers, if it answers
        one - the instance that was actually asked, carrying its bucket and Bloom level,
        rather than the caller naming them separately and risking the two drifting apart.
    :param answered_correctly: Whether this query's answer matched ground truth, if it
        answers a question of the frozen set.
    """
    return RecordedQuery(
        text=text,
        answer=answer,
        latency=latency,
        moment=1.0,
        question=question,
        answered_correctly=answered_correctly,
        answered_predicates=[
            AnsweredPredicate(predicate_name="supported_by", backend_name=backend)
            for backend in backends
        ],
    )


def recorded_corpus() -> list[RecordedTrial]:
    """
    Three runs' trials: an unablated simulated run of three trials, an ablated simulated
    run of two, and one trial on the robot.

    A function rather than a fixture, so the tests that record this corpus into a
    database reach the same corpus without depending on this module's fixtures.
    """
    unablated = episode(NO_ABLATION)
    ablated = episode(WITHOUT_HOLE_SHAPES)
    on_the_robot = episode(NO_ABLATION, execution_type=ExecutionType.REAL)
    return [
        trial(
            unablated,
            TrialOutcome.SUCCEEDED,
            duration=8.0,
            insertion_attempts=[
                attempt(ROUND_HOLE, InsertionOutcome.FELL_THROUGH),
            ],
            queries=[
                query(WHAT_IS_ON_THE_TABLE, "cube, cylinder", 0.2, TWIN_BACKEND),
                query(WHERE_IS_THE_CUBE, "(0.1, 0.2, 0.3)", 0.4, TWIN_BACKEND),
            ],
        ),
        trial(
            unablated,
            TrialOutcome.SUCCEEDED,
            duration=12.0,
            queries=[query(WHAT_IS_ON_THE_TABLE, "cube, cylinder", 0.6, TWIN_BACKEND)],
        ),
        trial(
            unablated,
            TrialOutcome.FAILED,
            duration=16.0,
            insertion_attempts=[
                attempt(
                    SQUARE_HOLE,
                    InsertionOutcome.DID_NOT_FALL_THROUGH,
                    predicted_failure=SortingFailureType.WRONG_HOLE,
                    observed_failure=SortingFailureType.WRONG_HOLE,
                ),
            ],
            queries=[query(WHAT_IS_ON_THE_TABLE, "cube", 1.0, DETECTOR_BACKEND)],
        ),
        trial(
            ablated,
            TrialOutcome.FAILED,
            duration=20.0,
            insertion_attempts=[
                attempt(
                    SQUARE_HOLE,
                    InsertionOutcome.DID_NOT_FALL_THROUGH,
                    predicted_failure=SortingFailureType.WRONG_HOLE,
                    observed_failure=SortingFailureType.OUT_OF_REACH,
                ),
                attempt(
                    ROUND_HOLE,
                    InsertionOutcome.DID_NOT_FALL_THROUGH,
                    observed_failure=SortingFailureType.WRONG_HOLE,
                ),
            ],
            queries=[
                query(
                    WHAT_IS_ON_THE_TABLE,
                    "cube, cylinder",
                    0.8,
                    DETECTOR_BACKEND,
                    TWIN_BACKEND,
                )
            ],
        ),
        trial(ablated, TrialOutcome.SUCCEEDED, duration=14.0),
        trial(on_the_robot, TrialOutcome.FAILED, duration=30.0),
    ]


@pytest.fixture()
def recorded_trials() -> list[RecordedTrial]:
    """
    The corpus every figure below is computed from.
    """
    return recorded_corpus()


def figure_named(name: FigureName):
    """
    The one figure of the paper's set that reports the given table.

    :param name: The table to look up.
    """
    return FigureSet.for_the_paper().figure_named(name)


def rows_of(name: FigureName, recorded_trials: list[RecordedTrial]) -> list:
    """
    One figure's rows over the given trials.

    :param name: The figure to compute.
    :param recorded_trials: The trials it is computed from.
    """
    return figure_named(name).rows(recorded_trials)


# %% what a run's conditions are called


def test_a_run_that_kept_every_knowledge_source_is_named_as_such():
    """
    A blank cell reads as a missing measurement, so the unablated run is named rather
    than left empty in the column every ablation is compared down.
    """
    assert str(NO_ABLATION) == "none"


def test_the_conditions_of_one_run_are_named_together():
    """
    Two conditions applied to the same run are one row of the ablation table, not two.
    """
    conditions = RunConditions(condition_names=("NoHoleShapeKnowledge", "NoPiecePose"))

    assert str(conditions) == "NoHoleShapeKnowledge + NoPiecePose"


# %% trial outcome per ablation condition


def test_the_success_rate_of_every_condition_is_reported(recorded_trials):
    """
    Experiment C's headline table: what taking one knowledge source away did to the run.
    """
    rows = rows_of(FigureName.TRIAL_OUTCOME_BY_CONDITION, recorded_trials)

    assert [row.conditions for row in rows] == [NO_ABLATION, WITHOUT_HOLE_SHAPES]
    assert [row.goal_reached.measurement_count for row in rows] == [4, 2]
    assert [row.goal_reached.average.mean for row in rows] == [0.5, 0.5]


def test_the_robot_trial_is_counted_under_the_conditions_it_ran_with(recorded_trials):
    """
    An ablation is the same ablation wherever it ran, so the robot's own trials belong
    in its row rather than in a table of their own.
    """
    [unablated, _] = rows_of(FigureName.TRIAL_OUTCOME_BY_CONDITION, recorded_trials)

    assert unablated.goal_reached.measurement_count == 4


def test_every_reported_rate_carries_the_interval_it_lies_in(recorded_trials):
    """
    The item asks for confidence intervals on every rate, because a rate over a handful
    of trials pins the quantity down far less than its point value suggests.
    """
    rows = rows_of(FigureName.TRIAL_OUTCOME_BY_CONDITION, recorded_trials)

    for row in rows:
        assert (
            row.goal_reached.confidence_interval.lower <= row.goal_reached.average.mean
        )
        assert (
            row.goal_reached.average.mean <= row.goal_reached.confidence_interval.upper
        )


def test_a_condition_column_is_a_column_of_the_table(recorded_trials):
    """
    A row reports a nested measurement, so the table has to present that measurement's
    own columns rather than one column holding it whole.
    """
    assert ConditionOutcome.get_column_names() == [
        "conditions",
        "measurement_count",
        "average",
        "confidence_interval",
    ]


# %% which failures each condition produced


def test_every_observed_failure_type_is_counted_against_its_condition(recorded_trials):
    """
    The stacked failure-type bars are drawn from this table, so each bar's height is the
    share of that condition's attempts that ended in that type.
    """
    rows = rows_of(FigureName.FAILURE_TYPE_BY_CONDITION, recorded_trials)

    assert [(row.conditions, row.failure_type) for row in rows] == [
        (NO_ABLATION, SortingFailureType.WRONG_HOLE),
        (WITHOUT_HOLE_SHAPES, SortingFailureType.OUT_OF_REACH),
        (WITHOUT_HOLE_SHAPES, SortingFailureType.WRONG_HOLE),
    ]


def test_a_failure_type_share_is_taken_over_every_attempt_of_its_condition(
    recorded_trials,
):
    """
    The denominator is every attempt the condition made, not only the failed ones, or a
    condition that failed once out of fifty would report the same share as one that
    failed once out of one.
    """
    [unablated, out_of_reach, wrong_hole] = rows_of(
        FigureName.FAILURE_TYPE_BY_CONDITION, recorded_trials
    )

    assert unablated.share.average.mean == 0.5
    assert out_of_reach.share.average.mean == 0.5
    assert wrong_hole.share.average.mean == 0.5


def test_a_condition_that_attempted_nothing_reports_no_failure_row():
    """
    A share over no attempt is not zero, it is undefined, so no row is written for it.
    """
    attempted_nothing = [trial(episode(NO_ABLATION), TrialOutcome.SUCCEEDED)]

    assert rows_of(FigureName.FAILURE_TYPE_BY_CONDITION, attempted_nothing) == []


# %% how well a failure was predicted before it happened


def test_the_prediction_is_scored_for_precision_and_for_recall(recorded_trials):
    """
    The failure-prediction metric is on the roadmap's never-cut list, and it is two
    numbers: how often a prediction was right, and how often a failure was foreseen.
    """
    rows = rows_of(FigureName.FAILURE_PREDICTION, recorded_trials)

    assert [row.score for row in rows] == [
        PredictionScore.PRECISION,
        PredictionScore.RECALL,
    ]


def test_a_prediction_counts_only_when_it_named_the_failure_that_happened(
    recorded_trials,
):
    """
    Two failures were predicted and one of them named the type that actually happened,
    so precision is one in two; three failures happened and one was foreseen, so recall
    is one in three.
    """
    [precision, recall] = rows_of(FigureName.FAILURE_PREDICTION, recorded_trials)

    assert precision.agreement.measurement_count == 2
    assert precision.agreement.average.mean == 0.5
    assert recall.agreement.measurement_count == 3
    assert recall.agreement.average.mean == round(1 / 3, 2)


def test_a_score_with_nothing_to_measure_is_left_out(recorded_trials):
    """
    Precision over no prediction at all is undefined rather than zero, so it is not
    reported as a number a reader would compare against another run's.
    """
    without_predictions = [
        trial(episode(NO_ABLATION), TrialOutcome.FAILED, duration=1.0),
    ]

    rows = rows_of(FigureName.FAILURE_PREDICTION, without_predictions)

    assert rows == []


# %% what each backend answered, and how long it took


def test_every_backend_reports_the_predicates_it_answered(recorded_trials):
    """
    Experiment B's decomposition claim is per predicate: the reader has to see that one
    query's predicates went to different backends.
    """
    rows = rows_of(FigureName.QUERY_LATENCY_BY_BACKEND, recorded_trials)

    assert [row.backend_name for row in rows] == [DETECTOR_BACKEND, TWIN_BACKEND]
    assert [row.query_latency.measurement_count for row in rows] == [2, 4]


def test_a_backend_reports_the_latency_of_the_queries_it_answered_in(recorded_trials):
    """
    A backend answering two predicates of one query is measured against that query
    twice, which is what makes the count a count of predicates rather than of queries.
    """
    [detector, _] = rows_of(FigureName.QUERY_LATENCY_BY_BACKEND, recorded_trials)

    assert detector.query_latency.average.mean == 0.9
    assert detector.query_latency.average.unit is Unit.SECONDS


def test_backend_latency_is_a_column_of_the_table(recorded_trials):
    """
    The nested measurement is presented as its own columns here too, so every figure of
    the paper reports a quantity the same way.
    """
    assert BackendLatency.get_column_names() == [
        "backend_name",
        "measurement_count",
        "average",
        "confidence_interval",
    ]


# %% whether a repeated question came back with the same answer


def test_a_repeated_question_reports_how_often_it_agreed_with_itself(recorded_trials):
    """
    The determinism runs are on the never-cut list: a system that answers the same
    question differently each time has not answered it.
    """
    [agreement] = rows_of(FigureName.QUERY_DETERMINISM, recorded_trials)

    assert agreement.query == WHAT_IS_ON_THE_TABLE
    assert agreement.agreement.measurement_count == 4
    assert agreement.agreement.average.mean == 0.75


def test_a_question_asked_once_is_not_reported_as_deterministic(recorded_trials):
    """
    One asking always agrees with itself, so reporting it would put a row of ones in a
    table whose whole subject is disagreement across repetitions.
    """
    rows = rows_of(FigureName.QUERY_DETERMINISM, recorded_trials)

    assert WHERE_IS_THE_CUBE not in [row.query for row in rows]


# %% simulation against the robot


def test_the_robot_and_the_simulator_are_reported_apart(recorded_trials):
    """
    The item's own promise is that the robot numbers drop into the same tables by
    rerunning the script, which is only visible if the two are told apart.
    """
    rows = rows_of(FigureName.TRIAL_OUTCOME_BY_EXECUTION_TYPE, recorded_trials)

    assert [row.execution_type for row in rows] == [
        ExecutionType.REAL,
        ExecutionType.SIMULATED,
    ]
    assert [row.goal_reached.measurement_count for row in rows] == [1, 5]
    assert [row.goal_reached.average.mean for row in rows] == [0.0, 0.6]


# %% the set of figures, and what the script writes


def test_the_paper_prints_every_figure_the_set_names():
    """
    The set is what the script writes, so a figure named in the paper but missing from
    it is a table nothing regenerates.
    """
    figures = FigureSet.for_the_paper()

    assert {figure.name for figure in figures.figures} == set(FigureName)


def test_a_figure_renders_as_a_captioned_table(recorded_trials):
    """
    Every table in the paper explains what it shows, so a figure is rendered as a
    caption around its table rather than as a bare table.
    """
    figure = figure_named(FigureName.TRIAL_OUTCOME_BY_CONDITION)

    rendered = figure.render(recorded_trials)

    assert rendered.startswith("#figure(")
    assert figure.caption in rendered


def test_writing_a_figure_leaves_its_table_and_the_rows_behind_it(
    recorded_trials, tmp_path
):
    """
    A number in the paper is traceable to the rows it came from only if the rows are
    written beside the table that presents them.
    """
    figure = figure_named(FigureName.TRIAL_OUTCOME_BY_CONDITION)

    written = figure.write(recorded_trials, tmp_path)

    assert written.figure is FigureName.TRIAL_OUTCOME_BY_CONDITION
    assert written.table_path == tmp_path / figure.file_name(FigureFile.TYPST_TABLE)
    assert written.row_manifest_path == tmp_path / figure.file_name(
        FigureFile.ROW_MANIFEST
    )
    assert written.table_path.read_text() == figure.render(recorded_trials)


def test_writing_the_set_leaves_every_figure_of_the_paper(recorded_trials, tmp_path):
    """
    One script regenerates every table, so writing the set has to leave a file per
    figure rather than per figure that happened to have rows.
    """
    written = FigureSet.for_the_paper().write(recorded_trials, tmp_path)

    assert [each.figure for each in written] == list(FigureName)
    assert all(each.table_path.exists() for each in written)


def test_a_figure_over_no_trial_at_all_is_still_written(tmp_path):
    """
    The item's point is that the tables exist before any experiment has run, so an empty
    database has to leave an empty table rather than raise.
    """
    written = FigureSet.for_the_paper().write([], tmp_path)

    assert all(each.table_path.exists() for each in written)
    assert all(each.row_manifest_path.read_text() == "[]" for each in written)
