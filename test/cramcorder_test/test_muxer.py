"""
Tests for :mod:`cramcorder.muxer`: the tracks a video, its narration and its subtitles
are joined into.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cramcorder.encoding import VideoFile
from cramcorder.muxer import Muxer, NarrationTrack, PictureTrack, SubtitleTrack, Track

TRACK_FILE = Path("track")
INPUT_INDEX = 2

# %% the tracks


@pytest.mark.parametrize(
    "track, stream_kind",
    [
        (PictureTrack(TRACK_FILE), "v"),
        (NarrationTrack(TRACK_FILE, bit_rate=64_000), "a"),
        (SubtitleTrack(TRACK_FILE), "s"),
    ],
)
def test_a_track_takes_its_stream_from_its_own_input(
    track: Track, stream_kind: str
) -> None:
    options = track.options(INPUT_INDEX)
    assert options[:2] == ["-map", f"{INPUT_INDEX}:{stream_kind}:0"]


def test_the_narration_is_encoded_at_its_bit_rate() -> None:
    bit_rate = 48_000
    options = NarrationTrack(TRACK_FILE, bit_rate=bit_rate).options(INPUT_INDEX)
    assert options[options.index("-b:a") + 1] == str(bit_rate)


# %% the tracks joined


def test_the_subtitles_are_joined_only_when_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands = []
    monkeypatch.setattr(
        subprocess, "run", lambda command, check: commands.append(command)
    )
    muxer = Muxer(ffmpeg=Path("ffmpeg"))
    video, soundtrack, subtitles = (
        tmp_path / "video.mp4",
        tmp_path / "narration.wav",
        tmp_path / "subtitles.srt",
    )
    muxer.joined(VideoFile(video), soundtrack, tmp_path / "joined.mp4")
    muxer.joined(VideoFile(video), soundtrack, tmp_path / "joined.mp4", subtitles)
    without, with_subtitles = commands
    assert str(subtitles) not in without
    assert str(subtitles) in with_subtitles
