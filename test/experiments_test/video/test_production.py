"""
Tests for :mod:`experiments.video.production`: a minimal storyboard made into a narrated
mp4, with its subtitles burned in or as a track, checked against a venue's limits.
"""

from __future__ import annotations

import subprocess
from enum import StrEnum
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pytest

from experiments.video.canvas import VIDEO_RESOLUTION
from experiments.video.encoding import (
    SubmissionLimits,
    VideoFile,
    VideoOutsideTheLimits,
)
from experiments.video.narration import LEAD, Line, NarratedScene, Storyboard
from experiments.video.production import (
    BYTES_PER_SECOND,
    EncoderPreset,
    Subtitling,
    VideoProduction,
)
from experiments.video.slides import ResultRow, ResultsTable, TextCard
from experiments.video.timeline import Still

from .voices import EvenlyPacedVoice

RESOLUTION = VIDEO_RESOLUTION

FRAMES_PER_SECOND = 10

VOICE = EvenlyPacedVoice(seconds_per_word=0.25, rate=16_000, level=0.1)
"""
A voice at a rate an audio encoder takes, quiet enough not to clip.
"""


def gradient() -> np.ndarray:
    """
    A picture that changes across the frame, so there is something to encode.
    """
    picture = RESOLUTION.blank(0)
    picture[..., 0] = np.linspace(0, 255, RESOLUTION.width, dtype=np.uint8)
    return picture


def minimal_storyboard() -> Storyboard:
    """
    A title card said over, a picture held, and a table of results said over.
    """
    return Storyboard(
        [
            NarratedScene(
                TextCard("A minimal video", "made by a test", held_for=1.0),
                (Line("This video was made by a test."),),
            ),
            NarratedScene(Still(gradient(), held_for=1.0)),
            NarratedScene(
                ResultsTable("Results", (ResultRow("Trials", "2 of 2"),), held_for=1.0),
                (Line("Both trials succeeded."),),
            ),
        ]
    )


def production(
    subtitling: Subtitling = Subtitling.BURNED_IN,
    limits: SubmissionLimits | None = None,
) -> VideoProduction:
    """
    The minimal storyboard made quickly by the test voice.
    """
    return VideoProduction(
        minimal_storyboard(),
        voice=VOICE,
        frames_per_second=FRAMES_PER_SECOND,
        dissolve=0.2,
        subtitling=subtitling,
        limits=limits,
        preset=EncoderPreset.FAST,
    )


class StreamKind(StrEnum):
    """
    The kinds of stream a video file holds, as ffmpeg selects them.
    """

    SOUND = "a"
    SUBTITLES = "s"


def holds_stream(video: VideoFile, kind: StreamKind) -> bool:
    """
    :param video: A video file.
    :param kind: The kind of stream.
    :return: Whether the file holds a stream of that kind.
    """
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-v",
        "error",
        "-i",
        str(video.path),
        "-map",
        f"0:{kind}",
        "-c",
        "copy",
        "-f",
        "null",
        "-",
    ]
    return subprocess.run(command, capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def burned_in(tmp_path_factory: pytest.TempPathFactory) -> VideoFile:
    """
    The minimal video with its subtitles in the picture, made once.
    """
    return production().written_to(tmp_path_factory.mktemp("burned_in") / "minimal.mp4")


# %% the video that comes out


def test_the_minimal_video_plays_its_scenes_at_their_size_and_rate(
    burned_in: VideoFile,
) -> None:
    timeline, _ = production().narrated_timeline()
    assert burned_in.resolution == RESOLUTION
    assert burned_in.frames_per_second == pytest.approx(FRAMES_PER_SECOND)
    assert burned_in.duration == pytest.approx(
        timeline.duration, abs=1.5 / FRAMES_PER_SECOND
    )


def test_the_minimal_video_carries_its_narration_and_no_subtitle_track(
    burned_in: VideoFile,
) -> None:
    assert holds_stream(burned_in, StreamKind.SOUND)
    assert not holds_stream(burned_in, StreamKind.SUBTITLES)


def test_the_minimal_video_leaves_nothing_but_itself_beside_it(
    burned_in: VideoFile,
) -> None:
    assert [path.name for path in burned_in.path.parent.iterdir()] == [
        burned_in.path.name
    ]


def test_the_subtitles_are_burned_into_the_band_while_a_line_is_said(
    burned_in: VideoFile,
) -> None:
    band = slice(int(RESOLUTION.stage_height), RESOLUTION.height)
    said = burned_in.frame_at(LEAD + 0.5)
    assert said[band].min() < 128


def test_the_video_is_encoded_to_the_budget_where_no_venue_limits_it(
    burned_in: VideoFile,
) -> None:
    assert 0 < burned_in.size <= BYTES_PER_SECOND * burned_in.duration


# %% the slides grow to hold their lines


def test_a_slide_is_held_until_its_line_has_been_said() -> None:
    made = production()
    timeline, narration = made.narrated_timeline()
    said = VOICE.speaks(narration.lines[0].line.said).duration
    assert timeline.scenes[0].duration == pytest.approx(
        LEAD + said + made.storyboard.tail
    )
    assert timeline.scenes[1].duration == 1.0


# %% subtitles as a track


def test_soft_subtitles_go_in_as_a_track_and_a_subrip_file_beside_it(
    tmp_path: Path,
) -> None:
    video = production(Subtitling.SOFT).written_to(tmp_path / "minimal.mp4")
    assert holds_stream(video, StreamKind.SUBTITLES) and holds_stream(
        video, StreamKind.SOUND
    )
    subrip = video.path.with_suffix(".srt")
    assert "This video was made by a test." in subrip.read_text()


# %% a venue's limits


def test_a_video_longer_than_the_venue_allows_is_refused(tmp_path: Path) -> None:
    too_short = SubmissionLimits(
        longest=1.0,
        largest=10_000_000,
        lowest=RESOLUTION.height,
        slowest=FRAMES_PER_SECOND,
    )
    with pytest.raises(VideoOutsideTheLimits):
        production(limits=too_short).written_to(tmp_path / "minimal.mp4")


def test_a_video_inside_the_venues_limits_is_encoded_to_its_budget(
    tmp_path: Path,
) -> None:
    limits = SubmissionLimits(
        longest=60.0,
        largest=2_000_000,
        lowest=RESOLUTION.height,
        slowest=FRAMES_PER_SECOND,
    )
    video = production(limits=limits).written_to(tmp_path / "minimal.mp4")
    assert video.size <= limits.byte_budget_for(video.duration)
