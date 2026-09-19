"""
Generate "experience data" for the Montessori demo's insertion action by running the
scene (robot spawn and shape insertion, without RViz or the finished-scene MuJoCo
viewer) many times over, and recording every single insertion attempt -- successful and
failed alike -- as a row in a database (see
:class:`~experiments.montessori.insertion_experience.ShapeInsertionExperience`), via
ORMatic.

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.generate_insertion_experience --runs 100
    python -m experiments.montessori.generate_insertion_experience --runs 100 --headless

The database URI defaults to a local SQLite file
(:data:`DEFAULT_DATABASE_URI` in the current directory); override it with
``--database-uri`` or the ``MONTESSORI_EXPERIENCE_DATABASE_URI`` environment variable.

Requires ROS 2 (``rclpy``) and
:data:`~experiments.montessori.montessori_demo.DEFAULT_ROBOT_CLASS`'s description to be
installed, exactly like :func:`~experiments.montessori.montessori_demo.main`: unlike
the demo, this script has no ROS-optional fallback, since there is no experience data
to record without the ROS-dependent CRAM/Giskard motion stack that performs the actual
insertions.

.. note::
    :class:`~experiments.montessori.insertion_experience.ShapeInsertionExperience` must
    be included in ``experiments.orm.ormatic_interface`` before this script can persist
    anything; regenerate it with ``python scripts/regenerate_all_orm.py`` (from the
    repository root, in an environment with ROS 2 installed) if it is not already
    there.
"""

from __future__ import annotations

import argparse
import logging
import os

from sqlalchemy.orm import sessionmaker
from typing_extensions import List

from experiments.montessori.insertion_experience import ShapeInsertionExperience
from experiments.montessori.montessori_demo import (
    DEFAULT_ROBOT_CLASS,
    MAX_INSERTION_ATTEMPTS,
    _hold_controlled_joints_in_mujoco,
    _insert_shape_or_none,
)
from experiments.montessori.semantics import MontessoriShape, NoMatchingHoleError
from experiments.montessori.world import MontessoriWorld, robot_installed
from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.ormatic.data_access_objects.helper import to_dao
from krrood.ormatic.utils import create_engine
from semantic_digital_twin.utils import rclpy_installed

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URI = "sqlite:///montessori_insertion_experience.db"
"""
Database URI used when neither ``--database-uri`` nor
``MONTESSORI_EXPERIENCE_DATABASE_URI`` is given.
"""


def _run_once(run_index: int, headless: bool) -> List[ShapeInsertionExperience]:
    """
    Build a fresh Montessori scene, spawn the robot, and attempt to insert every shape
    that has a matching hole, recording every attempt (successful or not) as a
    :class:`~experiments.montessori.insertion_experience.ShapeInsertionExperience`.

    :param run_index: Index of this run, stored on every recorded experience (see
        :attr:`~experiments.montessori.insertion_experience.ShapeInsertionExperience.run_index`).
    :param headless: Whether to run the settling MuJoCo simulations without opening a
        viewer window.
    :return: One experience per insertion attempt made during this run.
    """
    # Imported lazily: pulls in rclpy at module level (see
    # experiments.montessori.montessori_demo._insert_all_shapes for the same reasoning).
    from coraplex.datastructures.dataclasses import Context

    montessori = MontessoriWorld()
    montessori.spawn_robot(DEFAULT_ROBOT_CLASS)
    _hold_controlled_joints_in_mujoco(montessori.robot)

    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )
    experiences = []
    for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape):
        try:
            montessori.board.hole_for(shape)
        except NoMatchingHoleError:
            continue

        for attempt in range(1, MAX_INSERTION_ATTEMPTS + 1):
            result = _insert_shape_or_none(shape, montessori, context, headless, attempt)
            if result is None:
                # No InsertionAttemptResult is produced when the reach target was
                # occupied, so there is nothing to record for this attempt.
                continue
            experiences.append(
                ShapeInsertionExperience(
                    run_index=run_index,
                    shape_category=shape.shape_category,
                    attempt_number=attempt,
                    target_horizontal_offset_x=float(result.target_horizontal_offset.x),
                    target_horizontal_offset_y=float(result.target_horizontal_offset.y),
                    fell_through_hole=result.fell_through_hole,
                )
            )
            if result.fell_through_hole:
                break

    return experiences


def generate_insertion_experience(runs: int, headless: bool, database_uri: str) -> None:
    """
    Run the Montessori demo's shape insertion ``runs`` times, recording every attempt
    (successful and unsuccessful) to the database at ``database_uri``.

    :param runs: How many independent demo runs to perform.
    :param headless: Whether to run the settling MuJoCo simulations without opening a
        viewer window.
    :param database_uri: Database to write the recorded experience to; see
        :data:`DEFAULT_DATABASE_URI`.
    """
    import experiments.orm.ormatic_interface as ormatic_interface

    engine = create_engine(database_uri)
    ormatic_interface.Base.metadata.create_all(engine)
    session = sessionmaker(engine)()

    for run_index in range(runs):
        logger.info("Starting run %d/%d.", run_index + 1, runs)
        experiences = _run_once(run_index, headless)
        for experience in experiences:
            session.add(to_dao(experience))
        session.commit()

        succeeded = sum(experience.fell_through_hole for experience in experiences)
        logger.info(
            "Run %d/%d done: %d/%d attempts fell through a hole.",
            run_index + 1,
            runs,
            succeeded,
            len(experiences),
        )


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments controlling how many runs to perform, whether MuJoCo
    viewer windows are opened, and which database to write to.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        type=int,
        default=100,
        help="How many independent demo runs to perform.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the settling MuJoCo simulations without opening a viewer window.",
    )
    parser.add_argument(
        "--database-uri",
        default=os.getenv("MONTESSORI_EXPERIENCE_DATABASE_URI", DEFAULT_DATABASE_URI),
        help="Database URI to write the recorded experience to.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Parse arguments and generate insertion experience, raising if the ROS-dependent
    motion stack or the robot's own description is not available: unlike
    :func:`~experiments.montessori.montessori_demo.main`, there is no useful fallback
    here, since the whole point of this script is running real insertions.
    """
    logging.basicConfig(level=logging.INFO)
    arguments = _parse_arguments()

    if not rclpy_installed():
        raise RuntimeError(
            "rclpy is not installed; generating insertion experience requires the "
            "ROS-dependent CRAM/Giskard motion stack that performs the insertions."
        )
    if not robot_installed(DEFAULT_ROBOT_CLASS):
        raise RuntimeError(
            f"{DEFAULT_ROBOT_CLASS.__name__}'s description is not installed."
        )

    generate_insertion_experience(
        arguments.runs, arguments.headless, arguments.database_uri
    )


if __name__ == "__main__":
    main()
