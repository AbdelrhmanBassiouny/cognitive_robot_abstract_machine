"""
Example queries against the segmind events persisted per insertion attempt (see
:mod:`experiments.montessori.sorting_results`).

Each :class:`~experiments.orm.ormatic_interface.ShapeInsertionAttemptDAO` row carries
both its own ``plan_id`` and its own ``events`` (an association to the polymorphic
:class:`~experiments.orm.ormatic_interface.DetectionEventDAO` hierarchy), so an
attempt's events and its plan are always reachable from the same row -- these are worked
examples of the query shapes that relationship enables, not part of any pipeline.

Run against a real results database, e.g.::

    from krrood.ormatic.utils import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///franka_montessori_500_run.db")
    session = sessionmaker(engine)()
    events_recorded_during_plan(session, plan_id=42)
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from experiments.orm.ormatic_interface import (
    DetectionEventDAO,
    InsertionEventDAO,
    PickUpEventDAO,
    ShapeInsertionAttemptDAO,
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
    attempt = session.scalars(
        select(ShapeInsertionAttemptDAO).where(
            ShapeInsertionAttemptDAO.plan_id == plan_id
        )
    ).one()
    return [event_association.target for event_association in attempt.events]


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
    return [
        attempt
        for attempt in session.scalars(select(ShapeInsertionAttemptDAO)).all()
        if _has_event_of_type(attempt, PickUpEventDAO)
        and not _has_event_of_type(attempt, InsertionEventDAO)
    ]


def _has_event_of_type(
    attempt: ShapeInsertionAttemptDAO, event_dao_type: type[DetectionEventDAO]
) -> bool:
    return any(
        isinstance(event_association.target, event_dao_type)
        for event_association in attempt.events
    )
