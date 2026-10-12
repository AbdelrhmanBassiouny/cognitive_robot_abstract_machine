"""
Tests for :mod:`cramcorder.encoding`: frames written out as an H.264 video that fits a
venue's limits, and those limits checked on the file that came out.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from cramcorder.encoding import H264Encoder, SubmissionLimits, VideoFile
from cramcorder.exceptions import NothingToRead, VideoOutsideTheLimits
from cramcorder.frame import Frame, Resolution
from cramcorder.timeline import Still, Timeline

FRAME_SIZE = Resolution(width=320, height=480)
FRAMES_PER_SECOND = 20
VIDEO_LENGTH = timedelta(seconds=2)
SIZE_BUDGET = 1_000_000
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
    timeline = Timeline(
        scenes=[
            Still(frame, held_for=timedelta(seconds=1 / FRAMES_PER_SECOND))
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
        largest=2 * SIZE_BUDGET,
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
    assert 0 < encoded.size <= SIZE_BUDGET


def test_the_frames_read_back_resemble_the_ones_written(encoded: VideoFile) -> None:
    first = encoded.frame_at(timedelta(0))
    assert first.pixels.shape == FRAME_SIZE.shape
    # the orange square stands at the left edge in the first frame
    square = first.pixels[SQUARE_ROWS.start + 50, SQUARE_WIDTH // 2]
    assert square.astype(int).tolist() == pytest.approx(
        list(SQUARE_COLOUR), abs=COLOUR_TOLERANCE
    )


def test_a_moment_past_the_end_of_the_file_has_nothing_to_read(
    encoded: VideoFile,
) -> None:
    with pytest.raises(NothingToRead):
        encoded.frame_at(encoded.duration + VIDEO_LENGTH)


# %% the limits


def test_the_limits_accept_a_file_inside_them(encoded: VideoFile) -> None:
    limits().check(encoded)


@pytest.mark.parametrize(
    "broken_limit",
    [
        dict(longest=timedelta(seconds=1)),
        dict(largest=10),
        dict(lowest=720),
        dict(slowest=30),
    ],
    ids=["longest", "largest", "lowest", "slowest"],
)
def test_each_limit_refuses_a_file_outside_it(
    encoded: VideoFile, broken_limit: dict
) -> None:
    with pytest.raises(VideoOutsideTheLimits):
        limits(**broken_limit).check(encoded)


def test_the_byte_budget_is_the_largest_file_in_proportion_to_the_length() -> None:
    venue = SubmissionLimits(
        longest=timedelta(seconds=100), largest=1_000_000, lowest=480, slowest=20
    )
    assert venue.byte_budget_for(timedelta(seconds=25)) == venue.largest // 4
    assert venue.byte_budget_for(2 * venue.longest) == venue.largest
