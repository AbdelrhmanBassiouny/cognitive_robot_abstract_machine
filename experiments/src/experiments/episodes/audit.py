"""
Whether a recorded episode is whole: its rows are there and read back, what it kept
beside them is there and readable, what its trials recorded makes sense against each
other, and how its answers scored.

An audit reads the record as it was written -- the rows and the files -- rather than the
objects the run made, so a record that cannot be read back is reported as such instead
of failing wherever it happens to be read first.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from coraplex.datastructures.enums import ExecutionType
from sqlalchemy import select
from typing_extensions import Any, Dict, Iterator, List, Optional, Sequence

from experiments.episodes.artifacts import (
    ArtifactDirectory,
    EpisodeArtifact,
    EpisodeArtifacts,
    RunFile,
)
from experiments.episodes.episode import Episode, RecordedQuery
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.montessori.results_database import ResultsDatabase
from experiments.questions.working_memory import AnythingMoved
from experiments.scenarios.trial import TrialOutcome

# %% what an audit says


class Verdict(StrEnum):
    """
    What one check made of the episode, from nothing to report to broken.
    """

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"

    @property
    def severity(self) -> int:
        """
        How bad this verdict is, so the worst of several can be picked.
        """
        return list(Verdict).index(self)


class Check(StrEnum):
    """
    The checks an audit makes, named for what each looks at.
    """

    ROWS = "rows"
    WORLD = "world"
    TRANSCRIPT = "transcript"
    JOINT_TRACES = "joint traces"
    CAMERA_RECORDING = "camera recording"
    VIDEO = "video"
    QUESTIONS = "questions"
    EVENTS = "events"
    PERTURBATION = "perturbation"
    OUTCOMES = "outcomes"
    SCORES = "scores"
    READ_BACK = "read back"


@dataclass(frozen=True)
class Finding:
    """
    What one check made of the episode.
    """

    check: Check
    """
    The check that was made.
    """

    verdict: Verdict
    """
    What it made of the episode.
    """

    detail: str
    """
    What was found, in a sentence a reader can act on.
    """

    def render(self) -> str:
        """
        This finding as one line of a report.
        """
        return "%-8s %-17s %s" % (self.verdict.upper(), self.check, self.detail)


@dataclass
class EpisodeAuditReport:
    """
    Everything an audit found about one episode.
    """

    identifier: str
    """
    The episode that was audited.
    """

    description: str
    """
    The episode as its row describes it, for the head of the report.
    """

    findings: List[Finding] = field(default_factory=list)
    """
    What each check found, in the order the checks were made.
    """

    @property
    def verdict(self) -> Verdict:
        """
        The worst verdict any check reached.
        """
        return max(
            (finding.verdict for finding in self.findings),
            key=lambda verdict: verdict.severity,
            default=Verdict.PASSED,
        )

    def render(self) -> str:
        """
        This report as a readable document, one line per finding.
        """
        lines = ["Episode %s: %s" % (self.identifier, self.description)]
        lines.extend(finding.render() for finding in self.findings)
        lines.append("Verdict: %s" % self.verdict.upper())
        return "\n".join(lines) + "\n"


# %% what one trial recorded, as the checks read it


@dataclass(frozen=True)
class TrialRecord:
    """
    One trial's rows, read for the checks without rebuilding the world it ran in.
    """

    number: int
    """
    Which trial of its episode this is, counted from one.
    """

    outcome: TrialOutcome
    """
    Whether the trial reached its goal.
    """

    duration: float
    """
    How long it took, in seconds.
    """

    began_at: datetime.datetime
    """
    When it started on the wall clock.
    """

    instructions_carried_out: List[str]
    """
    What someone other than the robot was told to do to its scene.
    """

    queries: List[RecordedQuery]
    """
    Every query it asked, with its answer and score.
    """

    tick_moments: List[float]
    """
    When each tick of its event monitor happened, in seconds into the trial.
    """

    event_count: int
    """
    How many events its ticks detected altogether.
    """

    @property
    def question_moment(self) -> Optional[float]:
        """
        When the trial asked its questions, or None if it asked none.
        """
        if not self.queries:
            return None
        return self.queries[0].moment

    def answered_that_nothing_moved(self) -> bool:
        """
        Whether the trial, asked whether anything moved, said nothing did.
        """
        return any(
            isinstance(query.question, AnythingMoved) and query.answer == str(False)
            for query in self.queries
        )


# %% the audit


MOMENT_TOLERANCE = 0.5
"""
Seconds a moment stamped inside a trial may lie past the trial's own duration before it
is reported: the duration is read once the trial is over, and a moment is read as the
thing it stamps happens, so the two clocks are read a little apart.
"""


@dataclass
class EpisodeAudit:
    """
    Audits recorded episodes, one at a time, against the database they were recorded to
    and the directory their artifacts are kept in.
    """

    results_database: ResultsDatabase
    """
    The database the episodes were recorded to.
    """

    artifact_directory: ArtifactDirectory = field(default_factory=ArtifactDirectory)
    """
    Where every episode's artifacts are kept.
    """

    def recorded_identifiers(
        self, real_only: bool = False, newest: Optional[int] = None
    ) -> List[str]:
        """
        The identifiers of the recorded episodes, newest first.

        :param real_only: Whether to name only the episodes recorded on the robot.
        :param newest: How many of the newest to name, or None for all of them.
        """
        from experiments.orm.ormatic_interface import EpisodeDAO

        with self.results_database.open_session() as session:
            episodes = session.scalars(
                select(EpisodeDAO).order_by(EpisodeDAO.recorded_at.desc())
            ).all()
            named = [
                episode.identifier
                for episode in episodes
                if not real_only or episode.execution_type is ExecutionType.REAL
            ]
        return named if newest is None else named[:newest]

    def audit(self, identifier: str) -> EpisodeAuditReport:
        """
        Check one episode from its rows and files up to reading it back whole.

        :param identifier: What addresses the episode outside the database.
        """
        from experiments.orm.ormatic_interface import EpisodeDAO, RecordedTrialDAO

        with self.results_database.open_session() as session:
            rows = session.scalars(
                select(RecordedTrialDAO)
                .join(EpisodeDAO, RecordedTrialDAO.episode)
                .where(EpisodeDAO.identifier == identifier)
                .order_by(RecordedTrialDAO.number)
            ).all()
            if not rows:
                return EpisodeAuditReport(
                    identifier=identifier,
                    description="not recorded",
                    findings=[
                        Finding(
                            Check.ROWS,
                            Verdict.FAILED,
                            "no trial is recorded under this episode",
                        )
                    ],
                )
            episode_row = rows[0].episode
            episode = Episode(
                scenario_name=episode_row.scenario_name,
                execution_type=episode_row.execution_type,
                condition_names=list(episode_row.condition_names),
                perturbation_names=list(episode_row.perturbation_names),
                identifier=episode_row.identifier,
                recorded_at=episode_row.recorded_at,
            )
            trials = [self._trial_record(row) for row in rows]
            mesh_files = (
                None
                if episode_row.world is None
                else list(self._mesh_files_of(episode_row.world))
            )
        report = EpisodeAuditReport(
            identifier=identifier, description=self._describe(episode, trials)
        )
        artifacts = self.artifact_directory.open_for(episode)
        report.findings.append(self._check_rows(trials))
        report.findings.append(self._check_world(mesh_files))
        report.findings.append(self._check_transcript(artifacts))
        report.findings.append(self._check_joint_traces(artifacts, trials))
        if episode.execution_type is ExecutionType.REAL:
            report.findings.append(self._check_camera_recording(artifacts, trials))
        else:
            report.findings.append(self._check_video(artifacts))
        report.findings.append(self._check_questions(trials))
        report.findings.append(self._check_events(trials))
        report.findings.append(self._check_perturbation(episode, trials))
        report.findings.append(self._check_outcomes(trials))
        report.findings.append(self._check_scores(trials))
        if report.verdict is not Verdict.FAILED:
            report.findings.append(self._check_read_back(identifier, trials))
        return report

    # %% reading the rows

    @staticmethod
    def _trial_record(row: Any) -> TrialRecord:
        """
        One trial's rows as the checks read them.

        :param row: The trial's row, with its episode's rows reachable from it.
        """
        ticks = [association.target for association in row.ticks]
        return TrialRecord(
            number=row.number,
            outcome=row.outcome,
            duration=row.duration,
            began_at=row.began_at,
            instructions_carried_out=list(row.instructions_carried_out),
            queries=[association.target.from_dao() for association in row.queries],
            tick_moments=[tick.moment for tick in ticks],
            event_count=sum(len(tick.events) for tick in ticks),
        )

    @staticmethod
    def _mesh_files_of(world_row: Any) -> Iterator[Path]:
        """
        Every mesh file the recorded world's bodies and regions read from.

        :param world_row: The world's row.
        """
        from semantic_digital_twin.orm.ormatic_interface import (
            BodyDAO,
            MeshDAO,
            RegionDAO,
        )

        for association in world_row.kinematic_structure_entities:
            entity = association.target
            collections = []
            if isinstance(entity, BodyDAO):
                collections = [entity.visual, entity.collision]
            if isinstance(entity, RegionDAO):
                collections = [entity.area]
            for collection in collections:
                if collection is None:
                    continue
                for shape_association in collection.shapes:
                    if isinstance(shape_association.target, MeshDAO):
                        yield Path(shape_association.target.filename)

    @staticmethod
    def _describe(episode: Episode, trials: Sequence[TrialRecord]) -> str:
        """
        The episode in one line, for the head of its report.
        """
        return "%s, %s, perturbations %s, recorded %s, %d trials" % (
            episode.scenario_name,
            episode.execution_type.name,
            episode.perturbation_names or "none",
            episode.recorded_at.isoformat(timespec="seconds"),
            len(trials),
        )

    # %% health: what is there and readable

    @staticmethod
    def _check_rows(trials: Sequence[TrialRecord]) -> Finding:
        numbers = [trial.number for trial in trials]
        expected = list(range(1, len(trials) + 1))
        if numbers != expected:
            return Finding(
                Check.ROWS,
                Verdict.FAILED,
                "trials are numbered %s where 1..%d was expected"
                % (numbers, len(trials)),
            )
        return Finding(
            Check.ROWS, Verdict.PASSED, "%d trials, numbered in order" % len(trials)
        )

    @staticmethod
    def _check_world(mesh_files: Optional[Sequence[Path]]) -> Finding:
        if mesh_files is None:
            return Finding(Check.WORLD, Verdict.FAILED, "the episode kept no world")
        missing = [path for path in mesh_files if not path.is_file()]
        if missing:
            return Finding(
                Check.WORLD,
                Verdict.FAILED,
                "%d of %d mesh files the kept world reads from are gone, e.g. %s"
                % (len(missing), len(mesh_files), missing[0]),
            )
        return Finding(
            Check.WORLD,
            Verdict.PASSED,
            "the kept world reads from %d mesh files, all present" % len(mesh_files),
        )

    @staticmethod
    def _check_transcript(artifacts: EpisodeArtifacts) -> Finding:
        transcript = artifacts.directory / EpisodeArtifact.TRANSCRIPT
        if not transcript.is_file():
            return Finding(Check.TRANSCRIPT, Verdict.WARNING, "no transcript was kept")
        return Finding(Check.TRANSCRIPT, Verdict.PASSED, "kept at %s" % transcript)

    @staticmethod
    def _check_joint_traces(
        artifacts: EpisodeArtifacts, trials: Sequence[TrialRecord]
    ) -> Finding:
        samples = []
        for trial in trials:
            kept = artifacts.trial(trial.number)
            if not kept.kept_a_joint_trace:
                return Finding(
                    Check.JOINT_TRACES,
                    Verdict.FAILED,
                    "trial %d kept no joint trace" % trial.number,
                )
            trace = kept.joint_trace
            samples.append(len(trace.moments))
            if trace.moments and max(trace.moments) > trial.duration + MOMENT_TOLERANCE:
                return Finding(
                    Check.JOINT_TRACES,
                    Verdict.WARNING,
                    "trial %d: a sample at %.1f s lies past the trial's %.1f s"
                    % (trial.number, max(trace.moments), trial.duration),
                )
        if not all(samples):
            return Finding(
                Check.JOINT_TRACES,
                Verdict.WARNING,
                "samples per trial: %s; a trial without a sample saw the world's "
                "state never change while it ran" % samples,
            )
        return Finding(
            Check.JOINT_TRACES, Verdict.PASSED, "samples per trial: %s" % samples
        )

    @staticmethod
    def _check_camera_recording(
        artifacts: EpisodeArtifacts, trials: Sequence[TrialRecord]
    ) -> Finding:
        """
        Whether the camera recording a run on the robot kept spans every trial and
        yields a frame at every moment a question was asked.

        Imported here rather than at the top, so an audit of a simulated episode needs
        no ROS.
        """
        from experiments.montessori.perception.recordings import (
            REFERENCE_FRAME,
            RecordedCamera,
        )
        from experiments.paper.camera_frame import BagFrameAt
        from experiments.paper.run_plan import TrialClock

        if not artifacts.kept_a_camera_recording:
            return Finding(
                Check.CAMERA_RECORDING,
                Verdict.WARNING,
                "no camera recording was kept at %s"
                % artifacts.run_file(RunFile.CAMERA_RECORDING),
            )
        camera = RecordedCamera(
            bag=artifacts.camera_recording, reference_frame=REFERENCE_FRAME
        )
        stamps = camera.colour_stamps()
        if not stamps:
            return Finding(
                Check.CAMERA_RECORDING,
                Verdict.FAILED,
                "the camera recording holds no colour frame",
            )
        for trial in trials:
            clock = TrialClock(origin=trial.began_at)
            begins = clock.seconds_of_stamp(stamps[0])
            ends = clock.seconds_of_stamp(stamps[-1])
            if begins > MOMENT_TOLERANCE:
                return Finding(
                    Check.CAMERA_RECORDING,
                    Verdict.WARNING,
                    "trial %d: the recording begins %.1f s into the trial"
                    % (trial.number, begins),
                )
            if ends < trial.duration - MOMENT_TOLERANCE:
                return Finding(
                    Check.CAMERA_RECORDING,
                    Verdict.WARNING,
                    "trial %d: the recording ends %.1f s before the trial did"
                    % (trial.number, trial.duration - ends),
                )
            if trial.question_moment is None:
                continue
            frame = BagFrameAt(
                artifacts=artifacts, moment=trial.question_moment, clock=clock
            ).image
            if frame.ndim != 3:
                return Finding(
                    Check.CAMERA_RECORDING,
                    Verdict.FAILED,
                    "trial %d: the frame at its question moment is no colour image"
                    % trial.number,
                )
        return Finding(
            Check.CAMERA_RECORDING,
            Verdict.PASSED,
            "%d colour frames spanning every trial, one decoded at every trial's "
            "question moment" % len(stamps),
        )

    @staticmethod
    def _check_video(artifacts: EpisodeArtifacts) -> Finding:
        video = artifacts.directory / EpisodeArtifact.VIDEO
        if not video.is_file():
            return Finding(Check.VIDEO, Verdict.WARNING, "no video was kept")
        return Finding(Check.VIDEO, Verdict.PASSED, "kept at %s" % video)

    # %% logic: what the trials recorded against each other

    @staticmethod
    def _check_questions(trials: Sequence[TrialRecord]) -> Finding:
        asked: List[List[str]] = []
        for trial in trials:
            if not trial.queries:
                return Finding(
                    Check.QUESTIONS,
                    Verdict.FAILED,
                    "trial %d asked no question" % trial.number,
                )
            for query in trial.queries:
                if not 0.0 <= query.moment <= trial.duration + MOMENT_TOLERANCE:
                    return Finding(
                        Check.QUESTIONS,
                        Verdict.FAILED,
                        "trial %d: '%s' is stamped at %.1f s, outside the trial's "
                        "%.1f s"
                        % (trial.number, query.text, query.moment, trial.duration),
                    )
                if query.latency < 0.0:
                    return Finding(
                        Check.QUESTIONS,
                        Verdict.FAILED,
                        "trial %d: '%s' took a negative %.3f s"
                        % (trial.number, query.text, query.latency),
                    )
            asked.append(
                sorted(type(query.question).__name__ for query in trial.queries)
            )
        if any(questions != asked[0] for questions in asked):
            return Finding(
                Check.QUESTIONS,
                Verdict.WARNING,
                "the trials were not asked the same questions: %s"
                % [len(questions) for questions in asked],
            )
        return Finding(
            Check.QUESTIONS,
            Verdict.PASSED,
            "%d questions per trial, asked at %s s"
            % (
                len(asked[0]),
                [round(trial.question_moment, 1) for trial in trials],
            ),
        )

    @staticmethod
    def _check_events(trials: Sequence[TrialRecord]) -> Finding:
        for trial in trials:
            if not trial.tick_moments:
                return Finding(
                    Check.EVENTS,
                    Verdict.WARNING,
                    "trial %d recorded no tick of its event monitor" % trial.number,
                )
            if max(trial.tick_moments) > trial.duration + MOMENT_TOLERANCE:
                return Finding(
                    Check.EVENTS,
                    Verdict.WARNING,
                    "trial %d: a tick at %.1f s lies past the trial's %.1f s"
                    % (trial.number, max(trial.tick_moments), trial.duration),
                )
        return Finding(
            Check.EVENTS,
            Verdict.PASSED,
            "ticks per trial %s, events per trial %s"
            % (
                [len(trial.tick_moments) for trial in trials],
                [trial.event_count for trial in trials],
            ),
        )

    @staticmethod
    def _check_perturbation(episode: Episode, trials: Sequence[TrialRecord]) -> Finding:
        if not episode.perturbation_names:
            return Finding(Check.PERTURBATION, Verdict.PASSED, "an unperturbed run")
        if episode.execution_type is ExecutionType.REAL:
            for trial in trials:
                if not trial.instructions_carried_out:
                    return Finding(
                        Check.PERTURBATION,
                        Verdict.FAILED,
                        "trial %d records nobody carrying %s out"
                        % (trial.number, episode.perturbation_names),
                    )
        unnoticed = [
            trial.number for trial in trials if trial.answered_that_nothing_moved()
        ]
        if unnoticed:
            return Finding(
                Check.PERTURBATION,
                Verdict.WARNING,
                "trials %s answered that nothing moved after %s: the perturbation "
                "left no motion event" % (unnoticed, episode.perturbation_names),
            )
        return Finding(
            Check.PERTURBATION,
            Verdict.PASSED,
            "%s applied to every trial" % episode.perturbation_names,
        )

    @staticmethod
    def _check_outcomes(trials: Sequence[TrialRecord]) -> Finding:
        outcomes = [trial.outcome.name for trial in trials]
        if len(set(outcomes)) > 1:
            return Finding(
                Check.OUTCOMES,
                Verdict.WARNING,
                "the trials did not end alike: %s" % outcomes,
            )
        return Finding(Check.OUTCOMES, Verdict.PASSED, "every trial %s" % outcomes[0])

    # %% score: how the answers did

    @staticmethod
    def _check_scores(trials: Sequence[TrialRecord]) -> Finding:
        scored = [
            (trial, query)
            for trial in trials
            for query in trial.queries
            if query.answered_correctly is not None
        ]
        if not scored:
            return Finding(Check.SCORES, Verdict.FAILED, "no answer was scored")
        by_bucket: Dict[str, List[bool]] = {}
        for trial, query in scored:
            by_bucket.setdefault(query.bucket.name, []).append(query.answered_correctly)
        summary = "%d of %d scored answers correct; by bucket: %s" % (
            sum(query.answered_correctly for trial, query in scored),
            len(scored),
            ", ".join(
                "%s %d/%d" % (bucket, sum(results), len(results))
                for bucket, results in sorted(by_bucket.items())
            ),
        )
        wrong = [
            "trial %d: '%s' answered %s" % (trial.number, query.text, query.answer)
            for trial, query in scored
            if not query.answered_correctly
        ]
        if wrong:
            return Finding(
                Check.SCORES, Verdict.WARNING, "%s; wrong: %s" % (summary, wrong)
            )
        return Finding(Check.SCORES, Verdict.PASSED, summary)

    # %% reading the episode back whole

    def _check_read_back(
        self, identifier: str, trials: Sequence[TrialRecord]
    ) -> Finding:
        """
        Read the episode back as the objects a question over long-term memory is
        answered with, world included, which is what every later reader does.
        """
        recalled = LongTermMemory(self.results_database).recall_trials(identifier)
        if len(recalled) != len(trials):
            return Finding(
                Check.READ_BACK,
                Verdict.FAILED,
                "%d trials read back where %d are recorded"
                % (len(recalled), len(trials)),
            )
        return Finding(
            Check.READ_BACK,
            Verdict.PASSED,
            "%d trials read back as domain objects, world included" % len(recalled),
        )
