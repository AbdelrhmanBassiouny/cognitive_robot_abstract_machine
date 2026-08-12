"""
Run every worked example in :mod:`experiments.montessori.segmind_event_query_examples`
against a real results database and print what each one returns.

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.segmind_event_query_report
    python -m experiments.montessori.segmind_event_query_report --shape-key circular_hole_1
    python -m experiments.montessori.segmind_event_query_report --plan-id 7

.. note::
    :mod:`experiments.orm.ormatic_interface` must be importable and up to date (see
    ``python scripts/regenerate_all_orm.py``) before this can query anything.
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

import experiments.orm.ormatic_interface as ormatic_interface
from experiments.montessori.segmind_event_query_examples import (
    attempts_with_pick_up_but_no_insertion,
    events_recorded_during_plan,
    pick_up_to_insertion_durations,
    segmind_insertion_detection_accuracy,
    shape_results_for_shape_key,
)
from krrood.ormatic.utils import create_engine

DEFAULT_DATABASE_URI = (
    "postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/"
    "franka_montessori_sorting_results"
)
"""
Database URI used when neither ``--database-uri`` nor
``FRANKA_MONTESSORI_SORTING_DATABASE_URI`` is given, matching
:data:`~experiments.montessori.franka_montessori_demo.DEFAULT_DATABASE_URI`.
"""

DEFAULT_SHAPE_KEY = "square_hole"
"""
Shape
:func:`~experiments.montessori.segmind_event_query_examples.shape_results_for_shape_key`
is run against when ``--shape-key`` is not given.
"""


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments selecting the results database and which shape/plan the
    parameterized examples run against.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-uri",
        default=os.getenv(
            "FRANKA_MONTESSORI_SORTING_DATABASE_URI", DEFAULT_DATABASE_URI
        ),
        help="Database URI to query. Defaults to DEFAULT_DATABASE_URI, overridable via "
        "FRANKA_MONTESSORI_SORTING_DATABASE_URI.",
    )
    parser.add_argument(
        "--shape-key",
        default=DEFAULT_SHAPE_KEY,
        help=(
            "Shape key to look up every result for, e.g. 'square_hole'. Defaults to "
            f"'{DEFAULT_SHAPE_KEY}'."
        ),
    )
    parser.add_argument(
        "--plan-id",
        type=int,
        default=None,
        help=(
            "A ShapeInsertionAttemptDAO.plan_id to fetch every recorded event for. "
            "Defaults to an arbitrary attempt already in the database, so this runs "
            "without an argument on any non-empty results database."
        ),
    )
    return parser.parse_args()


def _an_existing_plan_id(session: Session) -> int:
    """
    :param session: Open session against the results database.
    :return: An arbitrary persisted attempt's ``plan_id``, for running
        :func:`~experiments.montessori.segmind_event_query_examples.events_recorded_during_plan`
        without the caller having to know one in advance.
    :raises NoResultFound: If the database has no persisted attempts at all.
    """
    return session.scalars(
        select(ormatic_interface.ShapeInsertionAttemptDAO.plan_id).limit(1)
    ).one()


def main() -> None:
    """
    Open a session against ``--database-uri`` and print the result of every worked
    example query in :mod:`experiments.montessori.segmind_event_query_examples`.
    """
    arguments = _parse_arguments()
    engine = create_engine(arguments.database_uri)
    session = sessionmaker(engine)()

    plan_id = arguments.plan_id
    if plan_id is None:
        plan_id = _an_existing_plan_id(session)

    print(f"=== events_recorded_during_plan(plan_id={plan_id}) ===")
    for event in events_recorded_during_plan(session, plan_id):
        print(f"  {type(event).__name__} at {event.timestamp}")

    print()
    print("=== attempts_with_pick_up_but_no_insertion ===")
    for attempt in attempts_with_pick_up_but_no_insertion(session):
        print(f"  attempt database_id={attempt.database_id}, plan_id={attempt.plan_id}")

    print()
    print("=== segmind_insertion_detection_accuracy ===")
    print(f"  {segmind_insertion_detection_accuracy(session)}")

    print()
    print(f"=== shape_results_for_shape_key(shape_key={arguments.shape_key!r}) ===")
    for result in shape_results_for_shape_key(session, arguments.shape_key):
        print(f"  database_id={result.database_id}, outcome={result.outcome}")

    print()
    print("=== pick_up_to_insertion_durations ===")
    for duration in pick_up_to_insertion_durations(session):
        print(f"  {duration.shape_key}: {duration.duration}")


if __name__ == "__main__":
    main()
