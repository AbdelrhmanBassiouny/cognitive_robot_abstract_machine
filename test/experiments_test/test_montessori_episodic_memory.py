"""
Tests for asking a Montessori demo about the runs it already finished.

Those answers come out of the results database rather than out of the process, so these
run against a real (sqlite) one seeded with recorded outcomes. No credentials are
needed, which is what keeps them in the CI suite.
"""

from __future__ import annotations

import json

import pytest
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import PlanNode
from krrood.ormatic.data_access_objects.helper import to_dao
from typing_extensions import List, Tuple

from cramera.knowledge.queryable_knowledge import QueryScope
from cramera.live.bridge import Bridge
from experiments.montessori.live_query_source import (
    EPISODIC_MEMORY_PRESETS,
    MONTESSORI_PRESETS,
    MontessoriLiveQuerySource,
)
from experiments.montessori.results_database import ResultsDatabase
from experiments.montessori.sorting_results import (
    InsertionOutcome,
    ShapeInsertionAttempt,
    ShapeInsertionResult,
    SortingIterationResult,
)

from .test_montessori_live_query import DECLARED_PRESETS_PATH

RECORDED_OUTCOMES: List[Tuple[str, InsertionOutcome]] = [
    ("square_hole", InsertionOutcome.FELL_THROUGH),
    ("square_hole", InsertionOutcome.FELL_THROUGH),
    ("square_hole", InsertionOutcome.DID_NOT_FALL_THROUGH),
    ("circular_hole_1", InsertionOutcome.FELL_THROUGH),
    ("circular_hole_1", InsertionOutcome.ATTEMPTS_EXHAUSTED),
]
"""
What two shapes' runs ended in: the square sorted twice out of three, the round one once
out of two.
"""


def minimal_plan() -> Plan:
    """
    The smallest plan an attempt can be recorded with: ``Plan.root`` needs exactly one
    node with no parent.
    """
    plan = Plan()
    plan.add_node(PlanNode())
    return plan


@pytest.fixture(scope="module")
def recorded_runs(tmp_path_factory) -> ResultsDatabase:
    """
    A results database holding :data:`RECORDED_OUTCOMES`, one iteration.

    Built once for the module: creating the whole generated ``experiments`` schema takes
    the best part of a minute, and every test here only reads it back.
    """
    directory = tmp_path_factory.mktemp("recorded_runs")
    database = ResultsDatabase(uri="sqlite:///%s" % (directory / "results.db"))
    with database.open_session() as session:
        session.add(
            to_dao(
                SortingIterationResult(
                    iteration=1,
                    shape_results=[
                        ShapeInsertionResult(
                            shape_key=shape_key,
                            outcome=outcome,
                            attempts=[ShapeInsertionAttempt(plan=minimal_plan())],
                        )
                        for shape_key, outcome in RECORDED_OUTCOMES
                    ],
                )
            )
        )
        session.commit()
    return database


@pytest.fixture()
def bridge(recorded_runs) -> Bridge:
    """
    A bridge over a demo that offers both what it is doing and what it has recorded.
    """
    live_bridge = Bridge()
    live_bridge.register_query_source(
        MontessoriLiveQuerySource(results_database=recorded_runs)
    )
    return live_bridge


def preset_named(text: str):
    """
    The episodic-memory preset with a given label.

    :param text: The label the preset is shown under.
    """
    [preset] = [entry for entry in EPISODIC_MEMORY_PRESETS if entry.text == text]
    return preset


def ask(bridge: Bridge, code: str):
    """
    Run one query against the recorded runs.

    :param bridge: The bridge answering it.
    :param code: The query to run.
    """
    return bridge.run_query(code, QueryScope.EPISODIC_MEMORY)


# %% what a demo offers about its finished runs
class TestWhatIsOnOffer:
    def test_both_the_present_and_the_recorded_past_are_queryable(self, bridge):
        assert bridge.query_scopes() == [
            QueryScope.CURRENT_STATE,
            QueryScope.DETECTED_EVENTS,
            QueryScope.EPISODIC_MEMORY,
        ]

    def test_a_demo_with_no_results_database_offers_only_what_it_is_doing(self):
        source = MontessoriLiveQuerySource()

        assert [knowledge.scope for knowledge in source.knowledge()] == [
            QueryScope.CURRENT_STATE,
            QueryScope.DETECTED_EVENTS,
        ]

    def test_a_demo_with_no_results_database_offers_no_recorded_questions(self):
        source = MontessoriLiveQuerySource()

        assert all(
            preset.scope is not QueryScope.EPISODIC_MEMORY
            for preset in source.presets()
        )

    def test_the_recorded_questions_are_offered_under_their_own_heading(self, bridge):
        assert [
            preset.text
            for preset in bridge.query_presets()
            if preset.scope is QueryScope.EPISODIC_MEMORY
        ] == [preset.text for preset in EPISODIC_MEMORY_PRESETS]


# %% answering from the database
class TestAskingTheRecordedRuns:
    def test_every_recorded_question_runs(self, bridge):
        for preset in EPISODIC_MEMORY_PRESETS:
            assert ask(bridge, preset.code).ok, preset.text

    def test_the_success_rate_counts_each_shapes_runs(self, bridge):
        result = ask(bridge, preset_named("success rate per shape").code)

        assert result.rows == [
            {"shape_key": "circular_hole_1", "Sum": 1, "Count": 2},
            {"shape_key": "square_hole", "Sum": 2, "Count": 3},
        ]

    def test_how_the_attempts_ended_is_broken_down_per_shape(self, bridge):
        result = ask(bridge, preset_named("how did each shape's runs end?").code)

        assert result.rows == [
            {
                "shape_key": "circular_hole_1",
                "outcome": "attempts_exhausted",
                "Count": 1,
            },
            {"shape_key": "circular_hole_1", "outcome": "fell_through", "Count": 1},
            {
                "shape_key": "square_hole",
                "outcome": "did_not_fall_through",
                "Count": 1,
            },
            {"shape_key": "square_hole", "outcome": "fell_through", "Count": 2},
        ]

    def test_an_answer_survives_the_session_it_was_read_in(self, bridge):
        """
        Rows are read out before the session closes; a row still attached to a closed
        one cannot be read from afterwards.
        """
        result = ask(bridge, preset_named("every recorded run").code)

        assert len(result.rows) == len(RECORDED_OUTCOMES)

    def test_the_recorded_questions_are_not_answerable_from_the_present(self, bridge):
        """
        Each scope is its own vocabulary, so a recorded question asked of the running
        sort is a mistake worth reporting rather than an empty answer.
        """
        with pytest.raises(NameError):
            bridge.run_query(
                preset_named("every recorded run").code, QueryScope.CURRENT_STATE
            )


# %% the recorded bundle shows the same questions
class TestDeclaredBundlePresets:
    def test_the_bundle_declares_the_scope_of_every_question(self):
        """
        The bundle's ``presets.json`` is what a viewer with no demo attached shows, so
        the questions are grouped there exactly as the demo groups them.
        """
        declared = json.loads(DECLARED_PRESETS_PATH.read_text())["presets"]

        assert [entry["scope"] for entry in declared] == [
            preset.scope.value for preset in MONTESSORI_PRESETS
        ]
