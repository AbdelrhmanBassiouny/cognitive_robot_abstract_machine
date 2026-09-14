"""
The real pickup demo rehearsed without the robot and the camera: the same run, over the
lab's ROS side stood in for (:mod:`~experiments.tracy_experiments.
lab_without_the_robot`), recorded the way a run on the robot is recorded and checked the
way one is checked, so what goes wrong in the lab goes wrong here first.

What is the demo's own and unchanged: the connection to the robot, the fetch of the
published world, the look through the perception node, the person's account of the
table, the perturbation, every plan the rig performs, the grippers driven through the
Robotiq action, the slip watch, the pick monitors, the bag recorded by a process of its
own, the episode kept in a database with its artifacts, and the check of it all. What
stands in: the world is Tracy's description served as the bringup serves it; the camera
shows a capture; the grippers' drivers close the fingers in the published world; the
person at the console is scripted; and the arm's motions are ticked by Giskard in this
process rather than run by its node on the robot.

Run with (ROS must be sourced; no robot and no camera need be up)::

    python -m experiments.tracy_experiments.pickup.pickup_demo_rehearsal --record

The demo's own options are taken as they are; ``--capture`` says which capture the
camera shows, ``--capture-after`` which one it shows once the person has brought the
perturbation about, and ``--pieces-placed`` what the person says they put on the table.
The episode goes to a database of its own beside the episodes' artifacts, so it is
never taken for a run on the robot, and the report of its check is printed with the
command that checks it again.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from enum import StrEnum

logging.basicConfig(level=logging.INFO, format="%(message)s")

import rclpy
from coraplex.datastructures.enums import ExecutionType
from typing_extensions import List, Optional, Sequence

from experiments.episodes.artifacts import (
    ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE,
    ArtifactDirectory,
)
from experiments.episodes.audit import EpisodeAudit, EpisodeAuditReport, Verdict
from experiments.montessori.check_episode import (
    FAILED_EXIT_CODE,
    SOUND_EXIT_CODE,
    CheckOption,
)
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.pieces import SMALLER_PIECES
from experiments.montessori.results_database import (
    ResultsDatabase,
    resolve_lasting_database,
)
from experiments.montessori.scenarios import SortingPerturbation
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.watched_run import BETWEEN_THE_PIECES_THEY_NAME
from experiments.tracy_experiments.lab_without_the_robot import (
    CaptureCamera,
    LabWithoutTheRobot,
)
from experiments.tracy_experiments.live_tracy import LiveTracy
from experiments.tracy_experiments.montessori.event_dashboard import (
    EventFeed,
    run_dashboard,
)
from experiments.tracy_experiments.pickup.pickup_demo_real import (
    BAG_NAME_PREFIX,
    DEFAULT_PIECE_ASKED_ABOUT,
    NODE_NAME,
    PickupDemo,
    argument_parser,
    perturbation_asked_for,
)
from experiments.tracy_experiments.rosbag_recording import RosbagRecorder

logger = logging.getLogger(__name__)

DEFAULT_CAPTURE = "scaled_pieces_in_a_row"
"""
The capture the camera shows unless told otherwise: the smaller set in a row on Tracy's
own table, laid out with a tape.
"""

REHEARSAL_DATABASE_NAME = "rehearsals.db"
"""
The file, beside the episodes' artifacts, the rehearsed episodes are recorded to.
"""

CHECK_SCRIPT = "experiments/scripts/check_episode.py"
"""
The script that checks a recorded episode again.
"""


class RehearsalOption(StrEnum):
    """
    The command line options a rehearsal adds to the demo's own.
    """

    CAPTURE = "--capture"
    CAPTURE_AFTER = "--capture-after"
    PIECES_PLACED = "--pieces-placed"


def rehearsal_database_uri(artifact_directory: ArtifactDirectory) -> str:
    """
    :param artifact_directory: Where the episodes' artifacts are kept.
    :return: The database the rehearsed episodes are recorded to, which sits beside
        them.
    """
    artifact_directory.path.mkdir(parents=True, exist_ok=True)
    return "sqlite:///%s" % (artifact_directory.path / REHEARSAL_DATABASE_NAME)


# %% the person


@dataclass
class PersonAtTheRehearsal:
    """
    The person at the console and the table during a rehearsal: does whatever they are
    asked at once, says they placed the pieces the capture shows, and brings the
    perturbation about by having the camera show the capture taken after it.
    """

    camera: CaptureCamera
    """
    The camera, which shows what the person did.
    """

    pieces_placed: List[MontessoriShapeCategory]
    """
    The pieces they say they put on the table.
    """

    capture_after: SceneCapture
    """
    The capture the camera shows once they have brought the perturbation about.
    """

    perturbation: Optional[SortingPerturbation] = None
    """
    What they are asked to bring about, or None for an unperturbed run.
    """

    asked: List[str] = field(default_factory=list)
    """
    The instructions given so far, in order.
    """

    def carry_out(self, instruction: str) -> None:
        self.asked.append(instruction)
        if (
            self.perturbation is not None
            and instruction == self.perturbation.instruction_for_a_person()
        ):
            self.camera.show(self.capture_after)

    def answer(self, question: str) -> str:
        return BETWEEN_THE_PIECES_THEY_NAME.join(
            str(category) for category in self.pieces_placed
        )


# %% the rehearsal


@dataclass
class Rehearsal:
    """
    One rehearsal of the demo: what the camera shows, what the person says, and how the
    run is recorded and checked.
    """

    capture: SceneCapture
    """
    The capture the camera shows.
    """

    capture_after: SceneCapture
    """
    The capture the camera shows once the person has brought the perturbation about.
    """

    pieces_placed: List[MontessoriShapeCategory]
    """
    The pieces the person says they put on the table.
    """

    database: ResultsDatabase
    """
    The database the episode is recorded to.
    """

    artifact_directory: ArtifactDirectory = field(default_factory=ArtifactDirectory)
    """
    Where the episode's artifacts are kept.
    """

    asked_about: MontessoriShapeCategory = DEFAULT_PIECE_ASKED_ABOUT
    """
    The kind of piece the question set is asked about.
    """

    perturbation: Optional[SortingPerturbation] = None
    """
    What the person is asked to bring about, or None for an unperturbed run.
    """

    bag_directory: Optional[str] = None
    """
    Where the bag is recorded, or None to record none.
    """

    keep_every_nth_frame: int = 1
    """
    How much of the camera streams the bag keeps.
    """

    feed: EventFeed = field(default_factory=EventFeed)
    """
    Where the events the rig's monitors report are streamed to.
    """

    person: Optional[PersonAtTheRehearsal] = field(init=False, default=None)
    """
    The person at the console and the table, once the rehearsal has run.
    """

    def run(self) -> EpisodeAuditReport:
        """
        Bring the lab up, run the demo over it and check what it recorded.

        ROS must already be initialised.

        :return: The report of the check.
        """
        with LabWithoutTheRobot.brought_up(self.capture) as lab:
            self.person = PersonAtTheRehearsal(
                camera=lab.camera,
                pieces_placed=self.pieces_placed,
                capture_after=self.capture_after,
                perturbation=self.perturbation,
            )
            with LiveTracy.connected(NODE_NAME) as tracy:
                artifacts = PickupDemo(
                    tracy=tracy,
                    person=self.person,
                    database=self.database,
                    asked_about=self.asked_about,
                    perturbation=self.perturbation,
                    bag=self.bag_for(lab),
                    motion_execution=ExecutionType.SIMULATED,
                    artifact_directory=self.artifact_directory,
                    feed=self.feed,
                ).run()
        return EpisodeAudit(
            results_database=self.database,
            artifact_directory=self.artifact_directory,
        ).audit(artifacts.episode.identifier)

    def bag_for(self, lab: LabWithoutTheRobot) -> Optional[RosbagRecorder]:
        """
        The bag the run records, of the topics the lab publishes, or None for a run that
        records none.

        :param lab: The lab the run is over.
        """
        if self.bag_directory is None:
            return None
        return RosbagRecorder.timestamped(
            BAG_NAME_PREFIX,
            self.bag_directory,
            topics=lab.published_topics,
            keep_every_nth_frame=self.keep_every_nth_frame,
        )


def check_again_command(
    report: EpisodeAuditReport, database: ResultsDatabase, directory: ArtifactDirectory
) -> str:
    """
    :param report: The report of a rehearsed episode's check.
    :param database: The database it was recorded to.
    :param directory: Where its artifacts are kept.
    :return: The command that checks the episode again.
    """
    return "%s=%s python %s %s %s %s %s" % (
        ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE,
        directory.path,
        CHECK_SCRIPT,
        CheckOption.EPISODE,
        report.identifier,
        CheckOption.DATABASE_URI,
        database.uri,
    )


# %% the command line


def parse_arguments(argument_list: Optional[Sequence[str]]) -> argparse.Namespace:
    """
    :param argument_list: Arguments to read; the process's own when None.
    :return: The demo's own arguments, and the rehearsal's.
    """
    parser = argparse.ArgumentParser(
        description="Rehearse the real pickup demo without the robot and the camera.",
        parents=[argument_parser(add_help=False)],
    )
    parser.add_argument(
        RehearsalOption.CAPTURE,
        default=DEFAULT_CAPTURE,
        help="the capture the camera shows",
    )
    parser.add_argument(
        RehearsalOption.CAPTURE_AFTER,
        default=None,
        help=(
            "the capture the camera shows once the person has brought the "
            "perturbation about; the same one unless said otherwise"
        ),
    )
    parser.add_argument(
        RehearsalOption.PIECES_PLACED,
        nargs="+",
        type=MontessoriShapeCategory,
        choices=list(MontessoriShapeCategory),
        default=list(SMALLER_PIECES.by_category),
        help="the pieces the person says they put on the table",
    )
    return parser.parse_args(argument_list)


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    """
    Rehearse the demo and print the report of the check, with the command that checks
    the episode again.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 when no check failed, 1 otherwise.
    """
    arguments = parse_arguments(argument_list)
    artifact_directory = ArtifactDirectory()
    database = resolve_lasting_database(
        rehearsal_database_uri(artifact_directory)
        if arguments.database_uri is None
        else arguments.database_uri
    )
    capture = SceneCapture.load(arguments.capture)
    rehearsal = Rehearsal(
        capture=capture,
        capture_after=(
            capture
            if arguments.capture_after is None
            else SceneCapture.load(arguments.capture_after)
        ),
        pieces_placed=arguments.pieces_placed,
        database=database,
        artifact_directory=artifact_directory,
        asked_about=arguments.ask_about,
        perturbation=perturbation_asked_for(arguments.perturbation, arguments.piece),
        bag_directory=arguments.bag_directory if arguments.record else None,
        keep_every_nth_frame=arguments.keep_every_nth_frame,
    )
    run_dashboard(rehearsal.feed)
    rclpy.init()
    try:
        report = rehearsal.run()
    finally:
        # An interruption from the keyboard reaches rclpy's own signal handler first,
        # which has already shut ROS down by the time this runs.
        rclpy.try_shutdown()
    print(report.render(), flush=True)
    print(
        "Check it again with:\n  %s"
        % check_again_command(report, database, artifact_directory),
        flush=True,
    )
    return FAILED_EXIT_CODE if report.verdict is Verdict.FAILED else SOUND_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
