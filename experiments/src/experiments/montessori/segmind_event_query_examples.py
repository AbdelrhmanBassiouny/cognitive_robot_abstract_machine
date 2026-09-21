"""
Example queries against the segmind events persisted per insertion attempt (see
:mod:`experiments.montessori.sorting_results`).

Each :class:`~experiments.orm.ormatic_interface.ShapeInsertionAttemptDAO` row carries
both its own ``plan_id`` and its own ``events`` (an association to the polymorphic
:class:`~experiments.orm.ormatic_interface.DetectionEventDAO` hierarchy), so an
attempt's events and its plan are always reachable from the same row -- these are worked
examples of the query shapes that relationship enables, not part of any pipeline.

Every query below builds its top-level entity fetch with ``krrood``'s
entity_query_language (EQL) rather than a raw SQLAlchemy ``select(...)``. Navigating
*into* an ``attempts``/``events`` association list once EQL has fetched the owning row
stays plain Python (see :func:`_has_event_of_type`): EQL's ``exists(var, var ==
some_list_attribute)`` was tried for that instead and silently produced a wrong
correlated subquery on this schema -- it compared the association target's own
``database_id`` directly against the owning row's ``database_id`` rather than joining
through the association table, matching by coincidence rather than by relationship. A
many-to-one attribute chain (e.g. ``attempt.plan.database_id``) does not have this
problem, since it resolves to a real join through an actual foreign key.

Run against a real results database, e.g.::

    from krrood.ormatic.utils import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///franka_montessori_500_run.db")
    session = sessionmaker(engine)()
    events_recorded_during_plan(session, plan_id=42)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from krrood.entity_query_language.factories import an, entity, the, variable
from krrood.ormatic.eql_interface import eql_to_sql
from experiments.montessori.sorting_results import (
    InsertionOutcome,
    ShapeInsertionAttempt,
    ShapeInsertionResult,
)
from experiments.orm.ormatic_interface import (
    DetectionEventDAO,
    InsertionEventDAO,
    PickUpEventDAO,
    ShapeInsertionAttemptDAO,
    ShapeInsertionResultDAO,
)

# %% all events recorded during a given plan


def events_recorded_during_plan(
    session: Session, plan_id: int
) -> list[DetectionEventDAO]:
    """
    Every segmind event detected while the attempt with plan ``plan_id`` was running.

    :param session: Open session against the results database.
    :param plan_id: A :class:`~coraplex.orm.model.PlanMapping`'s ``database_id`` (e.g.
        read off :attr:`ShapeInsertionAttemptDAO.plan_id` for an attempt of interest).
    """
    attempt = variable(type_=ShapeInsertionAttempt, domain=[])
    query = the(entity(attempt).where(attempt.plan.database_id == plan_id))
    attempt_dao = eql_to_sql(query, session).evaluate()
    return [event_association.target for event_association in attempt_dao.events]


# %% attempts with a pick-up but no insertion event


def attempts_with_pick_up_but_no_insertion(
    session: Session,
) -> list[ShapeInsertionAttemptDAO]:
    """
    Every attempt segmind saw pick up its shape but never saw pass through a hole -- the
    shape was grasped, but segmind's own detectors never registered an insertion,
    independent of the ground-truth geometry check (:meth:`~experiments.montessori.inser
    t_shape_action.InsertMontessoriShapeAction.has_fallen_through_hole`) that actually
    determined
    :attr:`~experiments.montessori.sorting_results.ShapeInsertionResult.outcome`.
    Comparing the two flags down the line is how segmind's detectors get validated
    against ground truth.

    :param session: Open session against the results database.
    """
    attempt = variable(type_=ShapeInsertionAttempt, domain=[])
    every_attempt = eql_to_sql(an(entity(attempt)), session).evaluate()
    return [
        attempt_dao
        for attempt_dao in every_attempt
        if _has_event_of_type(attempt_dao, PickUpEventDAO)
        and not _has_event_of_type(attempt_dao, InsertionEventDAO)
    ]


def _has_event_of_type(
    attempt: ShapeInsertionAttemptDAO, event_dao_type: type[DetectionEventDAO]
) -> bool:
    return any(
        isinstance(event_association.target, event_dao_type)
        for event_association in attempt.events
    )


# %% segmind's insertion detection against ground truth


@dataclass
class SegmindDetectionAccuracy:
    """
    How often segmind's own insertion-event detection on a shape's deciding attempt
    agreed with the ground-truth
    :attr:`~experiments.montessori.sorting_results.ShapeInsertionResult.outcome`
    computed by direct geometry
    (:meth:`~experiments.montessori.insert_shape_action.Inser
    tMontessoriShapeAction.has_fallen_through_hole`).
    """

    true_positives: int
    """
    Ground truth fell through, and segmind detected an insertion.
    """

    false_positives: int
    """
    Ground truth did not fall through, but segmind detected an insertion anyway.
    """

    false_negatives: int
    """
    Ground truth fell through, but segmind detected no insertion.
    """

    true_negatives: int
    """
    Ground truth did not fall through, and segmind detected no insertion either.
    """


def segmind_insertion_detection_accuracy(session: Session) -> SegmindDetectionAccuracy:
    """
    Tally segmind's insertion-event detection against ground truth across every
    persisted :class:`ShapeInsertionResultDAO`, one shape result at a time.

    Only the *last* attempt of each result is compared, since that is the attempt whose
    outcome (see :attr:`~experiments.montessori.sorting_results.ShapeInsertionResult.att
    empts`) actually decided :attr:`~ShapeInsertionResultDAO.outcome`; an earlier,
    retried attempt says nothing about the shape either way.

    :param session: Open session against the results database.
    """
    shape_result_variable = variable(type_=ShapeInsertionResult, domain=[])
    every_shape_result = eql_to_sql(
        an(entity(shape_result_variable)), session
    ).evaluate()

    tally = SegmindDetectionAccuracy(0, 0, 0, 0)
    for shape_result in every_shape_result:
        if not shape_result.attempts:
            continue
        last_attempt = max(
            shape_result.attempts, key=lambda association: association.database_id
        ).target
        segmind_detected_insertion = _has_event_of_type(last_attempt, InsertionEventDAO)
        ground_truth_fell_through = (
            shape_result.outcome == InsertionOutcome.FELL_THROUGH
        )

        if ground_truth_fell_through and segmind_detected_insertion:
            tally.true_positives += 1
        elif ground_truth_fell_through and not segmind_detected_insertion:
            tally.false_negatives += 1
        elif not ground_truth_fell_through and segmind_detected_insertion:
            tally.false_positives += 1
        else:
            tally.true_negatives += 1
    return tally


# %% every result recorded for a given shape, across every iteration


def shape_results_for_shape_key(
    session: Session, shape_key: str
) -> list[ShapeInsertionResultDAO]:
    """
    Every persisted :class:`ShapeInsertionResultDAO` for one shape, across every
    iteration in the database -- how one shape's own outcome varies run to run,
    independent of what happened to every other shape in the same iteration.

    :param session: Open session against the results database.
    :param shape_key: A shape's name with its trailing ``"_shape"`` suffix removed, e.g.
        ``"square_hole"``.
    """
    shape_result = variable(type_=ShapeInsertionResult, domain=[])
    query = an(entity(shape_result).where(shape_result.shape_key == shape_key))
    return eql_to_sql(query, session).evaluate()


# %% wall-clock time from pick-up to insertion


@dataclass
class PickUpToInsertionDuration:
    """
    How long a single attempt's physically simulated carry took, from segmind's own
    pick-up detection to its insertion detection.
    """

    shape_key: str
    """
    The shape this attempt was carrying.
    """

    duration: timedelta
    """
    Wall-clock time between the pick-up and insertion events.
    """


def pick_up_to_insertion_durations(session: Session) -> list[PickUpToInsertionDuration]:
    """
    Every attempt where segmind detected both a pick-up and an insertion, paired with
    the wall-clock time between the two -- independent of the ground-truth outcome,
    since a wedged-but-detected insertion is timed the same as a clean one.

    :param session: Open session against the results database.
    """
    shape_result_variable = variable(type_=ShapeInsertionResult, domain=[])
    every_shape_result = eql_to_sql(
        an(entity(shape_result_variable)), session
    ).evaluate()

    durations: list[PickUpToInsertionDuration] = []
    for shape_result in every_shape_result:
        for attempt_association in shape_result.attempts:
            events = [
                event_association.target
                for event_association in attempt_association.target.events
            ]
            pick_up_timestamps = [
                event.timestamp for event in events if isinstance(event, PickUpEventDAO)
            ]
            insertion_timestamps = [
                event.timestamp
                for event in events
                if isinstance(event, InsertionEventDAO)
            ]
            if not pick_up_timestamps or not insertion_timestamps:
                continue
            durations.append(
                PickUpToInsertionDuration(
                    shape_key=shape_result.shape_key,
                    duration=min(insertion_timestamps) - min(pick_up_timestamps),
                )
            )
    return durations
