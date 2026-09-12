"""
Run the simulated pickup demo as a recorded episode and draw the paper's query cards
from what it recorded.

Two runs are worth drawing, and this script draws either: the robot sorting the pieces
it saw, in which the piece it is asked about was picked up by an item of its own plan;
and the same run with someone shoving that piece across the table after the look and
before the sorting, in which the piece moved while the robot was idle and nothing in the
plan accounts for it.

Usage:
    python3 pickup_demo_cards.py <output-directory> [--shoved] [--piece <shape>]
        [--headless]
    python3 pickup_demo_cards.py <output-directory> --from-recording

The episode's artifacts -- the film of the table, the transcript, and the trial's own
camera film and joint trace -- are kept under the output directory beside a database
holding the trial, and the cards are written beside them. Run again with
``--from-recording`` to draw the cards from that database and those artifacts without
running the demo again.
"""

from __future__ import annotations

import argparse
import logging
import sys
from enum import StrEnum
from pathlib import Path

from experiments.episodes.artifacts import ArtifactDirectory
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.episodes.recording import open_recording
from experiments.montessori.results_database import ResultsDatabase
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.paper.query_card import QueryCardSet
from experiments.tracy_experiments.pickup.pickup_demo_mujoco import (
    DEFAULT_PIECE_ASKED_ABOUT,
    Shove,
    SimulatedLab,
    SimulatedPickupDemo,
)

logger = logging.getLogger(__name__)

SHOVED_ALONG_Y = 0.08
"""
How far someone pushes the piece across the table in the shoved run, in metres: far
enough that the robot's plan, made before the push, reaches for where the piece no
longer is.
"""


class Directory(StrEnum):
    """
    What the two things this script writes are kept under, inside the output directory.
    """

    ARTIFACTS = "artifacts"
    CARDS = "cards"
    RECORDING = "episode.db"


class Option(StrEnum):
    """
    The command line options, as they are spelled.
    """

    SHOVED = "--shoved"
    PIECE = "--piece"
    HEADLESS = "--headless"
    FROM_RECORDING = "--from-recording"


def parse_arguments(argument_list=None) -> argparse.Namespace:
    """
    :param argument_list: Arguments to read; the process's own when omitted.
    :return: What the script is asked to do.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument(
        Option.SHOVED,
        action="store_true",
        help="have someone shove the piece across the table while the robot is idle",
    )
    parser.add_argument(
        Option.PIECE,
        type=MontessoriShapeCategory,
        choices=list(MontessoriShapeCategory),
        default=DEFAULT_PIECE_ASKED_ABOUT,
        help="the piece the monitor watches and the question set is asked about",
    )
    parser.add_argument(
        Option.HEADLESS,
        action="store_true",
        help="run without MuJoCo's viewer window, as fast as the machine allows",
    )
    parser.add_argument(
        Option.FROM_RECORDING,
        action="store_true",
        help="draw the cards from the recording an earlier run left, without running",
    )
    return parser.parse_args(argument_list)


def recording_of(output_directory: Path) -> ResultsDatabase:
    """
    The database the run's trial is kept in, beside its artifacts.

    :param output_directory: The directory the run writes into.
    """
    return ResultsDatabase(
        uri="sqlite:///%s" % (output_directory / Directory.RECORDING)
    )


def draw_from_the_recording(output_directory: Path) -> int:
    """
    Draw the cards from the trial and the artifacts an earlier run left.

    :param output_directory: The directory that run wrote into.
    :return: 0 once the cards are written.
    """
    trials = LongTermMemory(recording_of(output_directory)).recall_every_trial()
    artifacts = ArtifactDirectory(path=output_directory / Directory.ARTIFACTS)
    written = QueryCardSet.for_the_paper().write_every_episode(
        trials, output_directory / Directory.CARDS, artifacts
    )
    for card in written:
        logger.info("Written %s.", card.layered_path or card.markup_path)
    return 0


def main(argument_list=None) -> int:
    """
    Run the demo once and draw its cards.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 once the cards are written.
    """
    arguments = parse_arguments(argument_list)
    if arguments.from_recording:
        return draw_from_the_recording(arguments.output_directory)
    arguments.output_directory.mkdir(parents=True, exist_ok=True)
    recording = open_recording(recording_of(arguments.output_directory))
    demo = SimulatedPickupDemo(
        lab=SimulatedLab.build(),
        headless=arguments.headless,
        paced_to_the_wall_clock=not arguments.headless,
        piece_asked_about=arguments.piece,
        shove=(
            Shove(category=arguments.piece, along_y=SHOVED_ALONG_Y)
            if arguments.shoved
            else None
        ),
        records_trials=recording,
    )
    try:
        demo.perform()
    finally:
        recording.close()
    artifacts = demo.keep(
        ArtifactDirectory(
            path=arguments.output_directory / Directory.ARTIFACTS
        ).open_for(demo.episode)
    )
    written = QueryCardSet.for_the_paper().write(
        demo.trial, arguments.output_directory / Directory.CARDS, artifacts
    )
    for card in written:
        logger.info("Written %s.", card.layered_path or card.markup_path)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
