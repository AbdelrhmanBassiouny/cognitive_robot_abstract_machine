"""
Auditing a recorded episode: whether its rows and files are there and read back, whether
what its trials recorded makes sense, and how its answers scored.

Every test records an episode the way a run does -- through the recorder into a database
file, with its artifacts beside it -- and then either audits it as it stands or breaks
one thing and audits that. The camera recording a run on the robot keeps is a rosbag, so
the checks over one live in :mod:`test_episode_audit_camera`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import pytest
import trimesh
from coraplex.datastructures.enums import ExecutionType
from semantic_digital_twin.adapters.mujoco_video_recording import RecordedVideo
from segmind.datastructures.events import PickUpEvent, TranslationEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Mesh
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List, Optional

from experiments.episodes.artifacts import (
    ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE,
    ArtifactDirectory,
    Transcript,
    keep_mesh,
)
from experiments.episodes.audit import (
    Check,
    EpisodeAudit,
    EpisodeAuditReport,
    Finding,
    Verdict,
)
from experiments.episodes.episode import (
    Episode,
    MovedBySomeoneElse,
    PerformedPlan,
    RecordedQuery,
    RecordedTrial,
    Tick,
)
from experiments.episodes.recording import open_recording
from experiments.episodes.trace import JointTrace
from experiments.montessori.check_episode import (
    FAILED_EXIT_CODE,
    SOUND_EXIT_CODE,
    main,
)
from experiments.montessori.results_database import ResultsDatabase
from experiments.questions.working_memory import AnythingMoved, NumberOfOwnBodies
from experiments.scenarios.trial import TrialOutcome

from .test_episode_artifacts import coloured_frames
from .test_episodes import minimal_plan

# %% an episode recorded the way a run records one

TRIAL_DURATION = 4.0
"""
How long every recorded trial took, in seconds.
"""

ASKED_AT = 3.0
"""
When every trial asked its questions, in seconds into the trial.
"""

TICKED_AT = 2.0
"""
When every trial's monitor ticked, in seconds into the trial.
"""


def world_of_one_kept_mesh() -> World:
    """
    The smallest world whose record reads from a mesh file: one body wearing a mesh kept
    beside the artifacts.
    """
    world = World()
    body = Body(name=PrefixedName("shape_sorter"))
    body.visual = ShapeCollection(
        [keep_mesh(trimesh.creation.box((0.1, 0.1, 0.1)))], reference_frame=body
    )
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
    return world


def answered(question, answer: str, correctly: Optional[bool] = True) -> RecordedQuery:
    """
    One question asked at :data:`ASKED_AT` and scored as given.

    :param question: The question that was asked.
    :param answer: What was answered.
    :param correctly: How the answer scored, or None if it was not scored.
    """
    return RecordedQuery(
        role_taker=question,
        answer=answer,
        latency=0.01,
        moment=ASKED_AT,
        answered_correctly=correctly,
    )


def trial_of(
    episode: Episode,
    outcome: TrialOutcome = TrialOutcome.SUCCEEDED,
    queries: Optional[List[RecordedQuery]] = None,
    instructions_carried_out: Optional[List[str]] = None,
) -> RecordedTrial:
    """
    One finished trial of the given episode, asked two questions and ticked once unless
    told otherwise.

    :param episode: The episode the trial belongs to.
    :param outcome: How the trial ended.
    :param queries: What it was asked, or None for the two questions every trial here is
        asked.
    :param instructions_carried_out: What someone other than the robot did to its scene,
        or None for nothing.
    """
    if queries is None:
        queries = [
            answered(NumberOfOwnBodies(), str(1)),
            answered(AnythingMoved(), str(False)),
        ]
    return RecordedTrial(
        episode=episode,
        outcome=outcome,
        duration=TRIAL_DURATION,
        queries=queries,
        ticks=[
            Tick(
                moment=TICKED_AT,
                events=[PickUpEvent(tracked_object=episode.world.bodies[0])],
            )
        ],
        instructions_carried_out=list(instructions_carried_out or []),
    )


def a_trace_of_one_sample(world: World) -> JointTrace:
    """
    A joint trace holding where the world's joints stood at one moment.

    :param world: The world whose joints are traced.
    """
    trace = JointTrace()
    trace.sample(world, TICKED_AT)
    return trace


@dataclass
class RecordedRun:
    """
    An episode recorded into a database file with its artifacts beside it, the way a run
    leaves one, and the audit that reads it back.
    """

    results_database: ResultsDatabase
    """
    The database the episode was recorded to.
    """

    artifact_directory: ArtifactDirectory
    """
    Where its artifacts were kept.
    """

    episode: Episode
    """
    The episode that was recorded.
    """

    trials: List[RecordedTrial] = field(default_factory=list)
    """
    Its trials, in the order they were recorded.
    """

    def record(
        self,
        *trials: RecordedTrial,
        joint_traces: bool = True,
        video: bool = True,
    ) -> None:
        """
        Record the given trials with the episode's world, and keep the transcript, a
        video of a simulated run, and a joint trace for each trial, unless told
        otherwise.

        :param trials: The trials to record, numbered in order.
        :param joint_traces: Whether each trial keeps a trace of its joints.
        :param video: Whether a simulated run keeps its video.
        """
        recording = open_recording(self.results_database)
        artifacts = self.artifact_directory.open_for(self.episode)
        for number, trial in enumerate(trials, start=1):
            trial.number = number
            recording.record(trial)
            self.trials.append(trial)
            if joint_traces:
                artifacts.trial(number).keep_joint_trace(
                    a_trace_of_one_sample(self.episode.world)
                )
        recording.close()
        artifacts.keep_transcript(Transcript(episode=self.episode, trials=self.trials))
        if video and self.episode.execution_type is ExecutionType.SIMULATED:
            artifacts.keep_video(
                RecordedVideo(frames=coloured_frames(4), frames_per_second=30)
            )

    def audit(self) -> EpisodeAuditReport:
        """
        Audit the recorded episode.
        """
        return EpisodeAudit(
            results_database=self.results_database,
            artifact_directory=self.artifact_directory,
        ).audit(self.episode.identifier)


@pytest.fixture
def run(tmp_path: Path, monkeypatch) -> RecordedRun:
    """
    A simulated run ready to record, with a world whose one mesh is kept beside the
    artifacts.
    """
    monkeypatch.setenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE, str(tmp_path))
    episode = Episode(
        scenario_name="the scene stands still",
        execution_type=ExecutionType.SIMULATED,
    )
    episode.world = world_of_one_kept_mesh()
    return RecordedRun(
        results_database=ResultsDatabase(
            uri="sqlite:///%s" % (tmp_path / "results.db")
        ),
        artifact_directory=ArtifactDirectory(path=tmp_path),
        episode=episode,
    )


def finding_of(report: EpisodeAuditReport, check: Check) -> Finding:
    """
    What one check found.

    :param report: The report to read.
    :param check: The check to read the finding of.
    """
    [finding] = [finding for finding in report.findings if finding.check is check]
    return finding


# %% an episode with nothing wrong


def test_a_sound_episode_passes_every_check(run: RecordedRun) -> None:
    run.record(trial_of(run.episode), trial_of(run.episode))

    report = run.audit()

    assert report.verdict is Verdict.PASSED, report.render()
    assert [finding.check for finding in report.findings] == [
        Check.ROWS,
        Check.WORLD,
        Check.TRANSCRIPT,
        Check.JOINT_TRACES,
        Check.VIDEO,
        Check.QUESTIONS,
        Check.EVENTS,
        Check.PERTURBATION,
        Check.OUTCOMES,
        Check.SCORES,
        Check.READ_BACK,
    ]


def test_a_sound_episode_is_read_back_whole(run: RecordedRun) -> None:
    run.record(trial_of(run.episode), trial_of(run.episode))

    report = run.audit()

    assert finding_of(report, Check.READ_BACK).verdict is Verdict.PASSED


def test_the_report_names_the_episode_and_every_finding(run: RecordedRun) -> None:
    run.record(trial_of(run.episode))

    report = run.audit()
    rendered = report.render()

    assert run.episode.identifier in rendered
    assert run.episode.scenario_name in rendered
    for finding in report.findings:
        assert finding.check in rendered
        assert finding.detail in rendered


# %% health: what is there and readable


def test_an_unrecorded_episode_fails_on_its_rows(run: RecordedRun) -> None:
    report = run.audit()

    assert finding_of(report, Check.ROWS).verdict is Verdict.FAILED
    assert report.verdict is Verdict.FAILED


def test_a_world_whose_mesh_file_is_gone_fails_the_world_check(
    run: RecordedRun,
) -> None:
    """
    A recorded world names its meshes by file, so a file gone missing since is what a
    reader of the world trips over; the audit says which.
    """
    run.record(trial_of(run.episode))
    [body] = run.episode.world.bodies
    [mesh] = body.visual.shapes
    assert isinstance(mesh, Mesh)
    Path(mesh.filename).unlink()

    report = run.audit()

    world = finding_of(report, Check.WORLD)
    assert world.verdict is Verdict.FAILED
    assert mesh.filename in world.detail
    assert Check.READ_BACK not in [finding.check for finding in report.findings]


def test_a_plans_world_whose_mesh_file_is_gone_fails_the_world_check(
    run: RecordedRun,
) -> None:
    """
    A plan keeps the world it was performed in, and that world goes into the record with
    the trial, so its meshes are checked with the episode's own.
    """
    plan = minimal_plan()
    plan.initial_world = world_of_one_kept_mesh()
    trial = trial_of(run.episode)
    trial.plans.append(PerformedPlan(plan=plan))
    run.record(trial)
    [body] = plan.initial_world.bodies
    [mesh] = body.visual.shapes
    Path(mesh.filename).unlink()

    report = run.audit()

    world = finding_of(report, Check.WORLD)
    assert world.verdict is Verdict.FAILED
    assert mesh.filename in world.detail


def test_an_episode_that_kept_no_world_fails_the_world_check(
    run: RecordedRun,
) -> None:
    trial = trial_of(run.episode)
    run.episode.world = None
    run.record(trial, joint_traces=False)

    assert finding_of(run.audit(), Check.WORLD).verdict is Verdict.FAILED


def test_a_trial_without_a_joint_trace_fails_that_check(run: RecordedRun) -> None:
    run.record(trial_of(run.episode), joint_traces=False)

    finding = finding_of(run.audit(), Check.JOINT_TRACES)

    assert finding.verdict is Verdict.FAILED
    assert "trial 1" in finding.detail


def test_a_joint_trace_without_a_sample_is_a_warning(run: RecordedRun) -> None:
    """
    A trial whose world never changed state leaves an empty trace, which is not a lost
    file but is nothing to read where the joints stood either.
    """
    run.record(trial_of(run.episode), joint_traces=False)
    run.artifact_directory.open_for(run.episode).trial(1).keep_joint_trace(JointTrace())

    assert finding_of(run.audit(), Check.JOINT_TRACES).verdict is Verdict.WARNING


def test_a_simulated_episode_without_a_video_is_a_warning(run: RecordedRun) -> None:
    run.record(trial_of(run.episode), video=False)

    assert finding_of(run.audit(), Check.VIDEO).verdict is Verdict.WARNING


def test_a_real_episode_without_a_camera_recording_is_a_warning(
    run: RecordedRun,
) -> None:
    run.episode.execution_type = ExecutionType.REAL
    run.record(trial_of(run.episode))

    report = run.audit()

    assert finding_of(report, Check.CAMERA_RECORDING).verdict is Verdict.WARNING
    assert Check.VIDEO not in [finding.check for finding in report.findings]


# %% logic: what the trials recorded against each other


def test_a_trial_that_asked_nothing_fails_the_questions_check(
    run: RecordedRun,
) -> None:
    run.record(trial_of(run.episode, queries=[]))

    assert finding_of(run.audit(), Check.QUESTIONS).verdict is Verdict.FAILED


def test_a_question_stamped_past_the_end_of_its_trial_fails(run: RecordedRun) -> None:
    late = answered(NumberOfOwnBodies(), str(1))
    late.moment = TRIAL_DURATION + 5.0
    run.record(trial_of(run.episode, queries=[late]))

    finding = finding_of(run.audit(), Check.QUESTIONS)

    assert finding.verdict is Verdict.FAILED
    assert late.text in finding.detail


def test_trials_asked_different_questions_are_a_warning(run: RecordedRun) -> None:
    run.record(
        trial_of(run.episode),
        trial_of(run.episode, queries=[answered(NumberOfOwnBodies(), str(1))]),
    )

    assert finding_of(run.audit(), Check.QUESTIONS).verdict is Verdict.WARNING


def test_a_trial_whose_monitor_never_ticked_is_a_warning(run: RecordedRun) -> None:
    unwatched = trial_of(run.episode)
    unwatched.ticks = []
    run.record(unwatched)

    assert finding_of(run.audit(), Check.EVENTS).verdict is Verdict.WARNING


def test_a_perturbed_trial_on_the_robot_that_nobody_acted_on_fails(
    run: RecordedRun,
) -> None:
    """
    On the robot a perturbation is carried out by the person at the table, and a trial
    that records no instruction to them recorded a perturbation that never happened.
    """
    run.episode.execution_type = ExecutionType.REAL
    run.episode.perturbation_names = ["PieceShoved"]
    run.record(trial_of(run.episode))

    assert finding_of(run.audit(), Check.PERTURBATION).verdict is Verdict.FAILED


def test_a_perturbation_that_left_no_motion_event_is_a_warning(
    run: RecordedRun,
) -> None:
    """
    Something moved the scene, so a trial that then answers that nothing moved has a
    perturbation its event monitor never saw.
    """
    run.episode.execution_type = ExecutionType.REAL
    run.episode.perturbation_names = ["PieceShoved"]
    run.record(
        trial_of(
            run.episode,
            instructions_carried_out=["Push the cube 10 cm across the table."],
        )
    )

    finding = finding_of(run.audit(), Check.PERTURBATION)

    assert finding.verdict is Verdict.WARNING
    assert "PieceShoved" in finding.detail


def test_a_perturbation_the_run_noticed_passes(run: RecordedRun) -> None:
    run.episode.perturbation_names = ["PieceShoved"]
    run.record(
        trial_of(
            run.episode,
            queries=[answered(AnythingMoved(), str(True))],
        )
    )

    assert finding_of(run.audit(), Check.PERTURBATION).verdict is Verdict.PASSED


MOVED_AT = 0.5
"""
When the person was told to move the piece, in seconds into the trial.
"""

SORT_STARTS_AT = 1.5
"""
When the robot's first plan after the move started, in seconds into the trial.
"""

BEFORE_THE_SORT = 1.0
"""
A moment between the move and the sort, in seconds into the trial.
"""

DURING_THE_SORT = 2.5
"""
A moment after the sort started, in seconds into the trial.
"""


def a_sorting_trial_whose_piece_translated_at(
    episode: Episode, translated_at: float, anything_moved: bool
) -> RecordedTrial:
    """
    A trial in which the person moved the episode's piece, the robot then sorted, and
    the monitor saw the piece translate once.

    :param episode: The episode the trial belongs to.
    :param translated_at: When the monitor saw the piece translate, in seconds into the
        trial.
    :param anything_moved: What the trial answered when asked whether anything moved.
    """
    piece = episode.world.bodies[0]
    trial = trial_of(
        episode,
        queries=[answered(AnythingMoved(), str(anything_moved))],
        instructions_carried_out=["Push the piece 10 cm across the table."],
    )
    sort = minimal_plan()
    sort.root.start_time = trial.began_at + timedelta(seconds=SORT_STARTS_AT)
    trial.plans = [PerformedPlan(plan=sort)]
    trial.moved_by_someone_else = [
        MovedBySomeoneElse(moment=MOVED_AT, things_moved=[piece.name])
    ]
    trial.ticks.append(
        Tick(moment=translated_at, events=[TranslationEvent(tracked_object=piece)])
    )
    return trial


def test_a_moved_piece_seen_translating_before_the_sort_is_noticed(
    run: RecordedRun,
) -> None:
    """
    What the robot's own motions move cannot be the person's move, so the move is
    noticed by a translation of what they moved between being told and the next plan,
    whatever the question about motion answered once the sort had run.
    """
    run.episode.perturbation_names = ["PieceShoved"]
    run.record(
        a_sorting_trial_whose_piece_translated_at(
            run.episode, BEFORE_THE_SORT, anything_moved=False
        )
    )

    assert finding_of(run.audit(), Check.PERTURBATION).verdict is Verdict.PASSED


def test_a_moved_piece_seen_translating_only_during_the_sort_is_a_warning(
    run: RecordedRun,
) -> None:
    run.episode.perturbation_names = ["PieceShoved"]
    run.record(
        a_sorting_trial_whose_piece_translated_at(
            run.episode, DURING_THE_SORT, anything_moved=True
        )
    )

    assert finding_of(run.audit(), Check.PERTURBATION).verdict is Verdict.WARNING


def test_trials_that_did_not_end_alike_are_a_warning(run: RecordedRun) -> None:
    run.record(
        trial_of(run.episode, outcome=TrialOutcome.SUCCEEDED),
        trial_of(run.episode, outcome=TrialOutcome.FAILED),
    )

    finding = finding_of(run.audit(), Check.OUTCOMES)

    assert finding.verdict is Verdict.WARNING
    assert TrialOutcome.SUCCEEDED.name in finding.detail
    assert TrialOutcome.FAILED.name in finding.detail


# %% score: how the answers did


def test_a_wrong_answer_is_reported_with_its_question(run: RecordedRun) -> None:
    wrong = answered(NumberOfOwnBodies(), str(7), correctly=False)
    run.record(trial_of(run.episode, queries=[wrong]))

    finding = finding_of(run.audit(), Check.SCORES)

    assert finding.verdict is Verdict.WARNING
    assert wrong.text in finding.detail
    assert wrong.answer in finding.detail


def test_the_scores_are_summed_by_bucket(run: RecordedRun) -> None:
    right = answered(NumberOfOwnBodies(), str(1))
    run.record(
        trial_of(run.episode, queries=[right]), trial_of(run.episode, queries=[right])
    )

    finding = finding_of(run.audit(), Check.SCORES)

    assert finding.verdict is Verdict.PASSED
    assert "%s 2/2" % right.bucket.name in finding.detail


def test_an_episode_none_of_whose_answers_were_scored_fails(run: RecordedRun) -> None:
    run.record(
        trial_of(
            run.episode, queries=[answered(NumberOfOwnBodies(), str(1), correctly=None)]
        )
    )

    assert finding_of(run.audit(), Check.SCORES).verdict is Verdict.FAILED


# %% the command line


def test_the_script_checks_the_named_episode_and_exits_soundly(
    run: RecordedRun, capsys
) -> None:
    run.record(trial_of(run.episode))

    exit_code = main(
        [
            "--episode",
            run.episode.identifier,
            "--database-uri",
            run.results_database.uri,
        ]
    )

    assert exit_code == SOUND_EXIT_CODE
    assert run.episode.identifier in capsys.readouterr().out


def test_the_script_exits_non_zero_when_a_check_failed(run: RecordedRun) -> None:
    run.record(trial_of(run.episode, queries=[]))

    exit_code = main(
        [
            "--episode",
            run.episode.identifier,
            "--database-uri",
            run.results_database.uri,
        ]
    )

    assert exit_code == FAILED_EXIT_CODE


def test_the_newest_episodes_are_the_ones_recorded_last(
    run: RecordedRun, tmp_path: Path
) -> None:
    run.record(trial_of(run.episode))
    later = Episode(
        scenario_name="the scene stands still", execution_type=ExecutionType.REAL
    )
    later.world = world_of_one_kept_mesh()
    RecordedRun(
        results_database=run.results_database,
        artifact_directory=run.artifact_directory,
        episode=later,
    ).record(trial_of(later))
    audit = EpisodeAudit(results_database=run.results_database)

    assert audit.recorded_identifiers() == [later.identifier, run.episode.identifier]
    assert audit.recorded_identifiers(newest=1) == [later.identifier]
    assert audit.recorded_identifiers(real_only=True) == [later.identifier]


def test_the_script_checks_the_newest_episode_when_told_nothing_else(
    run: RecordedRun, capsys
) -> None:
    run.record(trial_of(run.episode))

    main(["--database-uri", run.results_database.uri])

    assert run.episode.identifier in capsys.readouterr().out
