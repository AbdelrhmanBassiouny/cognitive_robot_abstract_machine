"""
Auditing the camera recording a run on the robot keeps: whether it spans every trial and
yields a frame at every moment a question was asked.

Kept apart from :mod:`test_episode_audit` because a camera recording is a rosbag, which
only a checkout with ROS can write.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from coraplex.datastructures.enums import ExecutionType

from experiments.episodes.audit import Check, Verdict
from experiments.paper.run_plan import NANOSECONDS_PER_SECOND

from .test_episode_audit import RecordedRun, finding_of, run, trial_of
from .test_montessori_recorded_camera import (
    A_SECOND,
    FRAMES_TAKEN,
    RECORDING_BEGAN_AT,
    write_recording,
)

# %% a run on the robot that recorded its camera


@pytest.fixture
def real_run(run: RecordedRun) -> RecordedRun:
    """
    A run on the robot, ready to record.
    """
    run.episode.execution_type = ExecutionType.REAL
    return run


def keep_the_frames_taken(real_run: RecordedRun, tmp_path: Path) -> None:
    """
    Leave the recording of :data:`FRAMES_TAKEN` as the episode's camera recording.
    """
    real_run.artifact_directory.open_for(real_run.episode).keep_camera_recording(
        write_recording(tmp_path / "recording", FRAMES_TAKEN)
    )


def began_at(stamp: int) -> datetime:
    """
    The instant of the wall clock a recording's stamp names.

    :param stamp: Nanoseconds since the epoch.
    """
    return datetime.fromtimestamp(stamp / NANOSECONDS_PER_SECOND)


# %% the recording against the trials


def test_a_recording_spanning_the_trial_passes(
    real_run: RecordedRun, tmp_path: Path
) -> None:
    trial = trial_of(real_run.episode)
    trial.began_at = began_at(RECORDING_BEGAN_AT)
    real_run.record(trial)
    keep_the_frames_taken(real_run, tmp_path)

    finding = finding_of(real_run.audit(), Check.CAMERA_RECORDING)

    assert finding.verdict is Verdict.PASSED
    assert str(len(FRAMES_TAKEN)) in finding.detail


def test_a_recording_that_opened_after_the_trial_began_is_a_warning(
    real_run: RecordedRun, tmp_path: Path
) -> None:
    """
    A trial's first moments before the recording opened are shown its first frame, so
    the trial reads back, but what the camera saw then is not there.
    """
    trial = trial_of(real_run.episode)
    trial.began_at = began_at(RECORDING_BEGAN_AT - A_SECOND)
    real_run.record(trial)
    keep_the_frames_taken(real_run, tmp_path)

    finding = finding_of(real_run.audit(), Check.CAMERA_RECORDING)

    assert finding.verdict is Verdict.WARNING
    assert "1.0 s into the trial" in finding.detail


def test_a_recording_that_closed_before_the_trial_ended_is_a_warning(
    real_run: RecordedRun, tmp_path: Path
) -> None:
    trial = trial_of(real_run.episode)
    trial.began_at = began_at(RECORDING_BEGAN_AT)
    trial.duration = (FRAMES_TAKEN[-1].stamp - RECORDING_BEGAN_AT) / A_SECOND + 10.0
    real_run.record(trial)
    keep_the_frames_taken(real_run, tmp_path)

    finding = finding_of(real_run.audit(), Check.CAMERA_RECORDING)

    assert finding.verdict is Verdict.WARNING
    assert "before the trial did" in finding.detail


def test_a_recording_holding_no_frame_fails(
    real_run: RecordedRun, tmp_path: Path
) -> None:
    real_run.record(trial_of(real_run.episode))
    real_run.artifact_directory.open_for(real_run.episode).keep_camera_recording(
        write_recording(tmp_path / "recording", [])
    )

    assert (
        finding_of(real_run.audit(), Check.CAMERA_RECORDING).verdict is Verdict.FAILED
    )
