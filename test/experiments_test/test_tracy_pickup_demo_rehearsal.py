"""
Tests for :mod:`experiments.tracy_experiments.pickup.pickup_demo_rehearsal`: the real
pickup demo runs over the lab stood in for, is recorded the way a run on the robot is,
and the check of what it recorded passes -- so what would go wrong in the lab goes wrong
here.

A rehearsal crosses the middleware, sorts every piece and records a bag, so each of the
two run here is run once for the module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import rclpy
from typing_extensions import Iterator

from experiments.episodes.artifacts import (
    ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE,
    ArtifactDirectory,
)
from experiments.episodes.audit import Check, EpisodeAuditReport, Verdict
from experiments.montessori.check_episode import CheckOption, main as check_episode
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.pieces import SMALLER_PIECES
from experiments.montessori.record_episode import PerturbationChoice
from experiments.montessori.results_database import ResultsDatabase
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.watched_run import SceneThePersonSetUp
from experiments.tracy_experiments.pickup.pickup_demo_real import (
    CHECK_THE_SCENE,
    perturbation_asked_for,
)
from experiments.tracy_experiments.pickup.pickup_demo_rehearsal import (
    DEFAULT_CAPTURE,
    PersonAtTheRehearsal,
    Rehearsal,
    RehearsalOption,
    check_again_command,
    parse_arguments,
    rehearsal_database_uri,
)

from .test_episode_audit import finding_of

PIECES_IN_THE_CAPTURE = list(SMALLER_PIECES.by_category)
"""
The pieces the default capture shows on the table, which is every piece of the set.
"""

# %% the rehearsals


@pytest.fixture(scope="module")
def ros() -> Iterator[None]:
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ArtifactDirectory]:
    """
    A directory of this module's own for the rehearsed episodes' artifacts, which is
    also where their worlds' meshes are kept.
    """
    directory = tmp_path_factory.mktemp("artifacts")
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(directory))
        yield ArtifactDirectory(path=directory)


@pytest.fixture(scope="module")
def database(artifacts: ArtifactDirectory) -> ResultsDatabase:
    return ResultsDatabase(uri=rehearsal_database_uri(artifacts))


def rehearsal_over(
    artifacts: ArtifactDirectory, database: ResultsDatabase, bags: Path, **arguments
) -> Rehearsal:
    """
    A rehearsal over the default capture, recording its bag into ``bags``.
    """
    capture = SceneCapture.load(DEFAULT_CAPTURE)
    return Rehearsal(
        capture=capture,
        capture_after=capture,
        pieces_placed=PIECES_IN_THE_CAPTURE,
        database=database,
        artifact_directory=artifacts,
        bag_directory=str(bags),
        **arguments,
    )


@pytest.fixture(scope="module")
def rehearsed(
    ros: None,
    artifacts: ArtifactDirectory,
    database: ResultsDatabase,
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Rehearsal, EpisodeAuditReport]:
    """
    An unperturbed run, rehearsed and checked.
    """
    rehearsal = rehearsal_over(artifacts, database, tmp_path_factory.mktemp("bags"))
    return rehearsal, rehearsal.run()


@pytest.fixture(scope="module")
def rehearsed_with_a_shove(
    ros: None,
    artifacts: ArtifactDirectory,
    database: ResultsDatabase,
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Rehearsal, EpisodeAuditReport]:
    """
    A run the person is asked to shove the cube in, rehearsed and checked -- over a
    camera that shows the same capture afterwards, since no capture of the shoved table
    exists.
    """
    rehearsal = rehearsal_over(
        artifacts,
        database,
        tmp_path_factory.mktemp("bags"),
        perturbation=perturbation_asked_for(
            PerturbationChoice.PIECE_SHOVED, MontessoriShapeCategory.CUBE
        ),
    )
    return rehearsal, rehearsal.run()


# %% what the check of the rehearsed run says


def test_the_rehearsed_episode_is_whole_and_reads_back(rehearsed):
    _, report = rehearsed

    for check in (Check.ROWS, Check.WORLD, Check.TRANSCRIPT, Check.READ_BACK):
        assert finding_of(report, check).verdict is Verdict.PASSED, report.render()


def test_the_bag_spans_the_trial_from_its_first_moment(rehearsed):
    """
    The bag is opened before the trial's clock starts, so the recording begins no later
    than the trial and shows a frame at the moment the questions were asked.
    """
    _, report = rehearsed

    assert (
        finding_of(report, Check.CAMERA_RECORDING).verdict is Verdict.PASSED
    ), report.render()


def test_the_joints_and_the_events_of_the_sorting_are_recorded(rehearsed):
    _, report = rehearsed

    assert finding_of(report, Check.JOINT_TRACES).verdict is Verdict.PASSED
    assert finding_of(report, Check.EVENTS).verdict is Verdict.PASSED
    assert finding_of(report, Check.OUTCOMES).verdict is Verdict.PASSED


def test_the_questions_are_asked_and_scored(rehearsed):
    _, report = rehearsed

    assert finding_of(report, Check.QUESTIONS).verdict is Verdict.PASSED
    assert finding_of(report, Check.SCORES).verdict is not Verdict.FAILED


def test_an_unperturbed_rehearsal_passes_as_a_whole(rehearsed):
    _, report = rehearsed

    assert report.verdict is not Verdict.FAILED, report.render()


def test_the_person_checks_the_scene_and_says_what_they_placed(rehearsed):
    rehearsal, _ = rehearsed

    assert rehearsal.person.asked == [CHECK_THE_SCENE % len(PIECES_IN_THE_CAPTURE)]


def test_the_rehearsed_episode_is_checked_again_by_the_printed_command(
    rehearsed, database, artifacts, capsys
):
    _, report = rehearsed
    command = check_again_command(report, database, artifacts)

    assert command.split()[0] == "%s=%s" % (
        ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE,
        artifacts.path,
    )
    options = command.split()[3:]
    assert check_episode(options) == 0
    assert report.identifier in capsys.readouterr().out


# %% the perturbation


def test_the_person_is_asked_to_bring_the_perturbation_about(rehearsed_with_a_shove):
    """
    The trial records the instruction, and the check passes the perturbation: the
    sorting moves every piece itself, so a shove the camera does not show is not told
    apart from it.
    """
    rehearsal, report = rehearsed_with_a_shove

    assert rehearsal.perturbation.instruction_for_a_person() in rehearsal.person.asked
    finding = finding_of(report, Check.PERTURBATION)
    assert finding.verdict is Verdict.PASSED, report.render()
    assert type(rehearsal.perturbation).__name__ in finding.detail


# %% the person


def test_the_person_shows_the_capture_taken_after_the_perturbation_only_when_asked_for_it():
    class CameraThatNotesWhatItShows:
        shown = []

        def show(self, capture):
            self.shown.append(capture)

    camera = CameraThatNotesWhatItShows()
    after = SceneCapture.load(DEFAULT_CAPTURE)
    perturbation = perturbation_asked_for(
        PerturbationChoice.PIECE_SHOVED, MontessoriShapeCategory.CUBE
    )
    person = PersonAtTheRehearsal(
        camera=camera,
        pieces_placed=PIECES_IN_THE_CAPTURE,
        capture_after=after,
        perturbation=perturbation,
    )

    person.carry_out(CHECK_THE_SCENE % 4)
    assert camera.shown == []
    person.carry_out(perturbation.instruction_for_a_person())
    assert camera.shown == [after]


def test_the_person_says_they_placed_the_pieces_they_were_told_of():
    placed = [MontessoriShapeCategory.CUBE, MontessoriShapeCategory.CYLINDER]
    person = PersonAtTheRehearsal(camera=None, pieces_placed=placed, capture_after=None)

    assert SceneThePersonSetUp(person).pieces_placed() == placed


# %% the command line


def test_the_rehearsal_takes_the_demos_options_and_its_own():
    arguments = parse_arguments(
        [
            "--record",
            RehearsalOption.CAPTURE,
            "a_capture",
            RehearsalOption.PIECES_PLACED,
            MontessoriShapeCategory.CUBE.value,
        ]
    )

    assert arguments.record
    assert arguments.capture == "a_capture"
    assert arguments.capture_after is None
    assert arguments.pieces_placed == [MontessoriShapeCategory.CUBE]


def test_the_rehearsal_shows_the_default_capture_and_every_piece_of_its_set():
    arguments = parse_arguments([])

    assert arguments.capture == DEFAULT_CAPTURE
    assert arguments.pieces_placed == PIECES_IN_THE_CAPTURE
