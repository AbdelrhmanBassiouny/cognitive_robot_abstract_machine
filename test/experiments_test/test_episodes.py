"""
ORM round-trip tests for :mod:`experiments.episodes.episode`: confirms that everything.

one trial recorded - the events seen per tick, the queries asked with their per-predicate
routing, and the insertion attempts with their typed and predicted failures - survives a
round trip through the generated interface under the episode it belongs to.
"""

from __future__ import annotations

from coraplex.datastructures.enums import ExecutionType
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import PlanNode
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body
from sqlalchemy import select

from experiments.episodes.episode import (
    AnsweredPredicate,
    Episode,
    FailureResolution,
    FailureType,
    InsertionAttempt,
    InsertionOutcome,
    RecordedQuery,
    RecordedTrial,
    Tick,
)
from experiments.orm.ormatic_interface import EpisodeDAO, RecordedTrialDAO
from experiments.scenarios.trial import TrialOutcome
from krrood.ormatic.data_access_objects.helper import to_dao


class SortingFailureType(FailureType):
    """
    The failure types a shape-sorting run can observe, standing in for the taxonomy that
    fills :class:`FailureType` in.
    """

    WRONG_HOLE = "wrong_hole"
    OUT_OF_REACH = "out_of_reach"


def minimal_plan() -> Plan:
    """
    The smallest ``Plan`` :class:`~coraplex.orm.model.PlanMapping` can persist: a bare
    ``Plan()`` has no nodes, and ``Plan.root`` (which persistence needs) requires
    exactly one node with no parent, so a single bare node is added.
    """
    plan = Plan()
    plan.add_node(PlanNode())
    return plan


def sorting_episode() -> Episode:
    """
    An episode of one simulated sorting run under one ablation.
    """
    return Episode(
        scenario_name="montessori_sorting",
        execution_type=ExecutionType.SIMULATED,
        condition_names=["NoHoleShapeKnowledge"],
        perturbation_names=["TargetHoleMoved"],
    )


# %% one trial's own record


def test_a_trial_is_persisted_under_its_episode(experiments_database_session):
    """
    An episode is what a later question reaches an old trial through, so the trial has
    to come back out of the database still naming it.
    """
    session = experiments_database_session
    episode = sorting_episode()
    trial = RecordedTrial(
        episode=episode, outcome=TrialOutcome.SUCCEEDED, duration=12.5
    )

    session.add(to_dao(trial))
    session.commit()

    [recorded_trial] = session.scalars(select(RecordedTrialDAO)).all()
    assert recorded_trial.outcome is TrialOutcome.SUCCEEDED
    assert recorded_trial.duration == 12.5
    assert recorded_trial.episode.scenario_name == "montessori_sorting"
    assert recorded_trial.episode.execution_type is ExecutionType.SIMULATED
    assert recorded_trial.episode.identifier == episode.identifier


def test_the_conditions_a_run_was_made_under_are_persisted(
    experiments_database_session,
):
    """
    Experiment D asks what the conditions were at the time, so a run's ablations and
    perturbations are part of what an episode records rather than of the code that ran
    it.
    """
    session = experiments_database_session

    session.add(to_dao(sorting_episode()))
    session.commit()

    [episode] = session.scalars(select(EpisodeDAO)).all()
    assert list(episode.condition_names) == ["NoHoleShapeKnowledge"]
    assert list(episode.perturbation_names) == ["TargetHoleMoved"]


def test_events_are_persisted_under_the_tick_they_were_seen_in(
    experiments_database_session,
):
    """
    Two ticks of one trial detect different segmind events; after a round trip each
    event must still be reachable only through the tick it was seen in, so a temporal
    question can order them.
    """
    session = experiments_database_session
    tracked_shape = Body(name=PrefixedName("circular_hole_1_shape"))
    trial = RecordedTrial(
        episode=sorting_episode(),
        outcome=TrialOutcome.SUCCEEDED,
        duration=12.5,
        ticks=[
            Tick(moment=1.0, events=[PickUpEvent(tracked_object=tracked_shape)]),
            Tick(moment=2.0, events=[InsertionEvent(tracked_object=tracked_shape)]),
        ],
    )

    session.add(to_dao(trial))
    session.commit()

    [recorded_trial] = session.scalars(select(RecordedTrialDAO)).all()
    ticks = [association.target for association in recorded_trial.ticks]
    events_by_moment = {
        tick.moment: {type(association.target).__name__ for association in tick.events}
        for tick in ticks
    }
    assert events_by_moment == {1.0: {"PickUpEventDAO"}, 2.0: {"InsertionEventDAO"}}


def test_a_query_keeps_the_backend_that_answered_each_predicate(
    experiments_database_session,
):
    """
    Which backend answered which predicate is exactly what Experiment B tabulates, so it
    is recorded per predicate rather than per query.
    """
    session = experiments_database_session
    trial = RecordedTrial(
        episode=sorting_episode(),
        outcome=TrialOutcome.SUCCEEDED,
        duration=12.5,
        queries=[
            RecordedQuery(
                text="the cyan piece left of the triangle on the table",
                answer="the cyan cube",
                latency=0.42,
                moment=3.0,
                answered_predicates=[
                    AnsweredPredicate(
                        predicate_name="LeftOf", backend_name="TwinBackend"
                    ),
                    AnsweredPredicate(
                        predicate_name="HasColour", backend_name="PerceptionBackend"
                    ),
                ],
            )
        ],
    )

    session.add(to_dao(trial))
    session.commit()

    [recorded_trial] = session.scalars(select(RecordedTrialDAO)).all()
    [query] = [association.target for association in recorded_trial.queries]
    assert query.latency == 0.42
    assert {
        association.target.predicate_name: association.target.backend_name
        for association in query.answered_predicates
    } == {"LeftOf": "TwinBackend", "HasColour": "PerceptionBackend"}


def test_an_attempt_keeps_the_failure_observed_the_one_predicted_and_the_resolution(
    experiments_database_session,
):
    """
    The prediction is scored against the observation, and Experiment D asks how a
    failure was resolved the last time it happened, so all three are on the attempt.
    """
    session = experiments_database_session
    trial = RecordedTrial(
        episode=sorting_episode(),
        outcome=TrialOutcome.FAILED,
        duration=8.0,
        insertion_attempts=[
            InsertionAttempt(
                shape_name="circular_hole_1",
                plan=minimal_plan(),
                outcome=InsertionOutcome.DID_NOT_FALL_THROUGH,
                predicted_failure=SortingFailureType.OUT_OF_REACH,
                observed_failure=SortingFailureType.WRONG_HOLE,
                resolution=FailureResolution.RETRIED,
            )
        ],
    )

    session.add(to_dao(trial))
    session.commit()

    [recorded_trial] = session.scalars(select(RecordedTrialDAO)).all()
    [attempt] = [
        association.target for association in recorded_trial.insertion_attempts
    ]
    assert attempt.outcome is InsertionOutcome.DID_NOT_FALL_THROUGH
    assert attempt.predicted_failure is SortingFailureType.OUT_OF_REACH
    assert attempt.observed_failure is SortingFailureType.WRONG_HOLE
    assert attempt.resolution is FailureResolution.RETRIED
    assert attempt.plan_id is not None


# %% the vocabularies the model leaves to the items that own them


def test_the_failure_taxonomy_names_the_types_rather_than_the_episode_model():
    """
    Naming the failure types here would be writing the taxonomy that
    ``failure-taxonomy-and-typing`` owns, so the base carries none and a subclass supplies
    them.
    """
    assert list(FailureType) == []
