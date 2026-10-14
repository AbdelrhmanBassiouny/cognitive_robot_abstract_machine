"""
Tests for :mod:`crollywood.encoding`: frames written out as an H.264 video that fits a
venue's limits, and the file that came out checked against those limits.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from crollywood.encoding import H264Encoder, VideoFile
from crollywood.exceptions import NothingToRead, VideoOutsideTheLimits
from crollywood.frame import Frame, Resolution
from crollywood.slides import SingleFrameSlide
from crollywood.submission import SubmissionLimits
from crollywood.timeline import TimelineScene, VideoTimeline
from krrood.units import DataSize

FRAME_SIZE = Resolution(width=320, height=480)
FRAMES_PER_SECOND = 20
VIDEO_LENGTH = timedelta(seconds=2)
SIZE_BUDGET = DataSize.of_bytes(1_000_000)
BACKGROUND_GREY = 30
SQUARE_COLOUR = (250, 120, 30)
SQUARE_ROWS = slice(100, 200)
SQUARE_WIDTH = 40
SQUARE_SPEED = 4
COLOUR_TOLERANCE = 40


def moving_frames(count: int) -> list[Frame]:
    """
    :return: Frames a moving square crosses, so there is something to encode.
    """
    frames = []
    for index in range(count):
        pixels = FRAME_SIZE.blank(BACKGROUND_GREY).pixels.copy()
        left = index * SQUARE_SPEED % FRAME_SIZE.width
        pixels[SQUARE_ROWS, left : left + SQUARE_WIDTH] = SQUARE_COLOUR
        frames.append(Frame(pixels))
    return frames


@pytest.fixture(scope="module")
def encoded(tmp_path_factory: pytest.TempPathFactory) -> VideoFile:
    """
    Two seconds of a moving square, encoded once.
    """
    frames = moving_frames(round(VIDEO_LENGTH.total_seconds() * FRAMES_PER_SECOND))
    timeline = VideoTimeline(
        scenes=[
            TimelineScene(
                role_taker=SingleFrameSlide(
                    frame, held_for=timedelta(seconds=1 / FRAMES_PER_SECOND)
                )
            )
            for frame in frames
        ],
        frames_per_second=FRAMES_PER_SECOND,
        dissolve=timedelta(0),
    )
    path = tmp_path_factory.mktemp("encoded") / "square.mp4"
    return H264Encoder(size_budget=SIZE_BUDGET).encode(timeline, path)


def limits(**changes: object) -> SubmissionLimits:
    """
    :param changes: The limits to change from ones that the encoded file satisfies.
    :return: Limits for the encoded file.
    """
    satisfied = dict(
        longest=timedelta(seconds=3),
        largest=SIZE_BUDGET.scaled(2),
        lowest=FRAME_SIZE.height,
        slowest=FRAMES_PER_SECOND,
    )
    return SubmissionLimits(**{**satisfied, **changes})


# %% what comes out


def test_the_encoded_file_has_the_timeline_size_rate_and_length(
    encoded: VideoFile,
) -> None:
    assert encoded.resolution == FRAME_SIZE
    assert encoded.frames_per_second == pytest.approx(FRAMES_PER_SECOND)
    assert encoded.duration.total_seconds() == pytest.approx(
        VIDEO_LENGTH.total_seconds(), abs=0.1
    )


def test_the_encoded_file_stays_inside_its_size_budget(encoded: VideoFile) -> None:
    assert DataSize(0) < encoded.size <= SIZE_BUDGET


def test_the_frames_read_back_resemble_the_ones_written(encoded: VideoFile) -> None:
    first = encoded.frame_at(timedelta(0))
    assert first.pixels.shape == FRAME_SIZE.shape
    # the orange square stands at the left edge in the first frame
    square = first.pixels[SQUARE_ROWS.start + 50, SQUARE_WIDTH // 2]
    assert square.astype(int).tolist() == pytest.approx(
        list(SQUARE_COLOUR), abs=COLOUR_TOLERANCE
    )


def test_a_moment_past_the_end_of_the_file_shows_its_last_frame(
    encoded: VideoFile,
) -> None:
    last = timedelta(seconds=(encoded.frame_count - 1) / encoded.frames_per_second)
    past_the_end = encoded.frame_at(encoded.duration + VIDEO_LENGTH)
    assert (past_the_end.pixels == encoded.frame_at(last).pixels).all()


def test_a_file_without_frames_has_nothing_to_read(tmp_path: Path) -> None:
    with pytest.raises(NothingToRead):
        VideoFile(tmp_path / "missing.mp4").frame_at(timedelta(0))


# %% the limits


def test_the_limits_accept_a_file_inside_them(encoded: VideoFile) -> None:
    encoded.check_within(limits())


@pytest.mark.parametrize(
    "broken_limit",
    [
        dict(longest=timedelta(seconds=1)),
        dict(largest=DataSize.of_bytes(10)),
        dict(lowest=720),
        dict(slowest=30),
    ],
    ids=["longest", "largest", "lowest", "slowest"],
)
def test_each_limit_refuses_a_file_outside_it(
    encoded: VideoFile, broken_limit: dict
) -> None:
    with pytest.raises(VideoOutsideTheLimits):
        encoded.check_within(limits(**broken_limit))
