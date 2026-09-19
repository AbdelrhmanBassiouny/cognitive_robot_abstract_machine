"""
Tests for :mod:`experiments.video.encoding`: frames written out as an H.264 video that
fits the conference's limits, and those limits checked on the file that came out.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.video.encoding import (
    H264Encoder,
    SubmissionLimits,
    VideoFile,
    VideoOutsideTheLimits,
)
from experiments.video.timeline import Resolution, Still, Timeline

RESOLUTION = Resolution(width=320, height=480)
FRAMES_PER_SECOND = 20


def moving_frames(count: int) -> list[np.ndarray]:
    """
    Frames a moving square crosses, so there is something to encode.
    """
    frames = []
    for index in range(count):
        frame = RESOLUTION.blank(30)
        left = index * 4 % RESOLUTION.width
        frame[100:200, left : left + 40] = (250, 120, 30)
        frames.append(frame)
    return frames


@pytest.fixture(scope="module")
def encoded(tmp_path_factory: pytest.TempPathFactory) -> VideoFile:
    """
    Two seconds of a moving square, encoded once.
    """
    frames = moving_frames(2 * FRAMES_PER_SECOND)
    timeline = Timeline(
        scenes=[Still(frame, 1 / FRAMES_PER_SECOND) for frame in frames],
        frames_per_second=FRAMES_PER_SECOND,
        dissolve=0.0,
    )
    path = tmp_path_factory.mktemp("encoded") / "square.mp4"
    return H264Encoder(size_budget=1_000_000).encode(timeline, path)


# %% what comes out


def test_the_encoded_file_has_the_timeline_size_rate_and_length(
    encoded: VideoFile,
) -> None:
    assert encoded.resolution == RESOLUTION
    assert encoded.frames_per_second == pytest.approx(FRAMES_PER_SECOND)
    assert encoded.duration == pytest.approx(2.0, abs=0.1)


def test_the_encoded_file_stays_inside_its_size_budget(encoded: VideoFile) -> None:
    assert 0 < encoded.size <= 1_000_000


def test_the_frames_read_back_resemble_the_ones_written(encoded: VideoFile) -> None:
    first = encoded.frame_at(0.0)
    assert first.shape == RESOLUTION.shape
    # the orange square stands at the left edge in the first frame
    assert first[150, 20].astype(int).tolist() == pytest.approx([250, 120, 30], abs=40)


# %% the limits


def test_the_conference_limits_accept_a_file_inside_them(encoded: VideoFile) -> None:
    SubmissionLimits(longest=3.0, largest=2_000_000, lowest=480, slowest=20).check(
        encoded
    )


@pytest.mark.parametrize(
    "limits",
    [
        SubmissionLimits(longest=1.0, largest=2_000_000, lowest=480, slowest=20),
        SubmissionLimits(longest=3.0, largest=10, lowest=480, slowest=20),
        SubmissionLimits(longest=3.0, largest=2_000_000, lowest=720, slowest=20),
        SubmissionLimits(longest=3.0, largest=2_000_000, lowest=480, slowest=30),
    ],
)
def test_each_limit_refuses_a_file_outside_it(
    encoded: VideoFile, limits: SubmissionLimits
) -> None:
    with pytest.raises(VideoOutsideTheLimits):
        limits.check(encoded)


def test_the_icra_limits_are_the_call_for_papers_ones() -> None:
    limits = SubmissionLimits.icra_2027()
    assert (limits.longest, limits.largest, limits.lowest, limits.slowest) == (
        180.0,
        20_000_000,
        480,
        20,
    )
