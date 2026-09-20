"""
Tests for :mod:`experiments.video.narration`: the lines the voice says over the scenes,
where each starts, that none runs into the next, the subtitles cut from them, and the
soundtrack they are laid on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from experiments.video.narration import (
    LEAD,
    NarratedScene,
    Narration,
    NarrationOverrun,
    Line,
    Speech,
    SpokenLine,
    Storyboard,
    SubtitleCue,
    SubtitleRoom,
    Subtitled,
    starts_of,
)
from experiments.video.slides import TextSlide
from experiments.video.timeline import Frame, Resolution, Scene, Still, Timeline


@dataclass
class VoiceThatTakes:
    """
    A voice whose every word lasts the same, and says nothing.
    """

    seconds_per_word: float = 0.5
    rate: int = 100

    def speaks(self, text: str) -> Speech:
        seconds = self.seconds_per_word * len(text.split())
        return Speech(np.ones(int(seconds * self.rate), dtype=np.float32), self.rate)


def spoken(text: str, starts: float, seconds: float, rate: int = 100) -> SpokenLine:
    return SpokenLine(Line(text), starts, Speech(np.ones(int(seconds * rate), dtype=np.float32), rate))


# %% lines and speech


def test_a_line_is_said_as_written_unless_told_otherwise() -> None:
    assert Line("paper 3889").said == "paper 3889"
    assert Line("paper 3889", spoken="paper thirty-eight eighty-nine").said == "paper thirty-eight eighty-nine"


def test_speech_lasts_its_samples_over_its_rate() -> None:
    assert Speech(np.zeros(2400, dtype=np.float32), 24000).duration == pytest.approx(0.1)


# %% subtitles


def test_a_short_line_is_one_cue_over_the_whole_speech() -> None:
    line = spoken("Thank you for watching.", 10.0, 2.0)
    assert line.cues() == [SubtitleCue(10.0, 12.0, "Thank you for watching.")]


def test_a_long_line_is_cut_at_clauses_into_cues_of_at_most_two_short_lines() -> None:
    text = (
        "The framework provides a common query interface over heterogeneous knowledge "
        "sources and computations. A query's representation and grounded meaning are "
        "separated from its computation, so that different backends can answer the same "
        "query from different sources of knowledge."
    )
    line = spoken(text, 5.0, 20.0)
    cues = line.cues(characters_per_row=42, rows=2)
    assert len(cues) >= 3
    assert all(len(cue.text) <= 42 for cue in line.cues())  # one row each by default
    assert " ".join(cue.text for cue in cues) == text
    for cue in cues:
        assert len(cue.rows(42)) <= 2
        assert all(len(row) <= 42 for row in cue.rows(42))
    assert cues[0].start == 5.0 and cues[-1].end == pytest.approx(25.0)
    for earlier, later in zip(cues, cues[1:]):
        assert later.start == pytest.approx(earlier.end)
    # a cue's share of the time is its share of the letters
    assert cues[0].end - cues[0].start == pytest.approx(20.0 * len(cues[0].text) / len(text), abs=0.5)


def test_cues_are_written_as_srt() -> None:
    narration = Narration([spoken("One.", 1.0, 1.5), spoken("Two.", 61.25, 2.0)])
    assert narration.srt() == (
        "1\n00:00:01,000 --> 00:00:02,500\nOne.\n\n"
        "2\n00:01:01,250 --> 00:01:03,250\nTwo.\n\n"
    )


# %% one line after the other


def test_a_line_that_runs_into_the_next_is_refused() -> None:
    fine = Narration([spoken("a", 0.0, 4.0), spoken("b", 4.5, 2.0)])
    fine.check(runs_for=10.0)
    with pytest.raises(NarrationOverrun) as refused:
        Narration([spoken("a", 0.0, 5.0), spoken("b", 4.5, 2.0)]).check(runs_for=10.0)
    assert "a" in str(refused.value) and "0.5" in str(refused.value)
    with pytest.raises(NarrationOverrun):
        Narration([spoken("a", 0.0, 4.0), spoken("b", 9.0, 2.0)]).check(runs_for=10.0)


def test_the_soundtrack_lays_each_line_where_it_starts() -> None:
    narration = Narration([spoken("a", 1.0, 1.0), spoken("b", 3.0, 0.5)])
    track = narration.soundtrack(runs_for=5.0)
    assert track.rate == 100 and len(track.samples) == 500
    assert track.samples[50] == 0 and track.samples[150] == 1 and track.samples[250] == 0
    assert track.samples[320] == 1 and track.samples[400] == 0


# %% the storyboard


def slide(held_for: float) -> TextSlide:
    return TextSlide(["a", "b"], held_for=held_for)


@dataclass
class CloseUp(Scene):
    """
    A scene whose length comes from what it shows, not from a hold.
    """

    @property
    def duration(self) -> float:
        return 2.0

    def picture_at(self, seconds: float) -> Frame:
        return Resolution(16, 9).blank(255)


def test_a_slide_grows_to_hold_its_line_and_a_close_up_does_not() -> None:
    close_up = CloseUp()
    board = Storyboard(
        [
            NarratedScene(slide(3.0), (Line("one two three four five six seven eight"),)),  # 4 s of speech
            NarratedScene(slide(3.0), (Line("one"),)),
            NarratedScene(close_up, (Line("one two three four five six seven eight"),)),
            NarratedScene(close_up),
        ]
    )
    board.fitted_to(VoiceThatTakes(0.5))
    assert board.scenes[0].held_for == pytest.approx(4.0 + LEAD + board.tail)
    assert board.scenes[1].held_for == 3.0
    assert board.scenes[2] is close_up and close_up.duration == 2.0


def test_the_lines_start_where_their_scenes_start_plus_the_lead() -> None:
    board = Storyboard(
        [
            NarratedScene(slide(3.0), (Line("one two"),)),
            NarratedScene(slide(3.0)),
            NarratedScene(slide(3.0), (Line("three"),)),
        ]
    )
    narration = board.narrated_by(VoiceThatTakes(0.5), dissolve=0.5)
    assert [line.starts for line in narration.lines] == pytest.approx([LEAD, 5.0 + LEAD])
    assert narration.lines[0].speech.duration == pytest.approx(1.0)


def test_two_lines_on_one_scene_are_said_one_after_the_other_with_a_pause() -> None:
    board = Storyboard([NarratedScene(slide(1.0), (Line("one two"), Line("three")))])
    board.fitted_to(VoiceThatTakes(0.5))
    assert board.scenes[0].held_for == pytest.approx(LEAD + 1.0 + board.pause + 0.5 + board.tail)
    narration = board.narrated_by(VoiceThatTakes(0.5), dissolve=0.5)
    assert [line.starts for line in narration.lines] == pytest.approx([LEAD, LEAD + 1.0 + board.pause])


def test_a_line_that_runs_on_leaves_its_slide_alone_and_a_delay_moves_its_start() -> None:
    board = Storyboard(
        [
            NarratedScene(slide(1.0), (Line("one two three four five six seven eight"),), runs_on=True),
            NarratedScene(slide(3.0), (Line("five"),), delay=2.5),
        ]
    )
    board.fitted_to(VoiceThatTakes(0.5))
    assert board.scenes[0].held_for == 1.0
    assert board.scenes[1].held_for == pytest.approx(LEAD + 2.5 + 0.5 + board.tail)
    narration = board.narrated_by(VoiceThatTakes(0.5), dissolve=0.5)
    assert narration.lines[1].starts == pytest.approx(0.5 + LEAD + 2.5)
    with pytest.raises(NarrationOverrun):
        narration.check(runs_for=100.0)
    assert "free" in narration.report(runs_for=100.0)


def test_a_sentence_too_long_for_a_subtitle_is_cut_evenly_at_a_clause_end_where_one_lies_near() -> None:
    room = SubtitleRoom(characters_per_row=42, rows=2)
    sentence = (
        "The working-memory backend evaluates the support condition again in "
        "simulation: a geometric check confirms that the cube rests on the lid."
    )
    parts = room.evenly(sentence)
    assert " ".join(parts) == sentence
    assert all(room.holds(part) for part in parts)
    assert parts[0].endswith("simulation:")
    assert room.evenly("short") == ["short"]
    line = SpokenLine(Line("It holds. It does. " + sentence), 0.0, Speech(np.zeros(100, dtype=np.float32), 100))
    texts = [cue.text for cue in line.cues(characters_per_row=42, rows=2)]
    assert texts[0] == "It holds. It does."  # short sentences are joined where they fit together
    assert texts[1] == parts[0]


def test_a_cue_is_written_on_two_even_rows_when_it_needs_two() -> None:
    cue = SubtitleCue(0.0, 1.0, "The framework provides a common query interface over heterogeneous")
    rows = cue.rows(42)
    assert len(rows) == 2 and abs(len(rows[0]) - len(rows[1])) < 12
    assert SubtitleCue(0.0, 1.0, "short").rows(42) == ["short"]
    narration = Narration([SpokenLine(Line("A row. And another."), 0.0, Speech(np.zeros(100, dtype=np.float32), 100))])
    assert narration.srt().count("\n") == 4  # number, times, one row, a blank line


def test_lines_said_in_turn_start_a_pause_after_the_one_before_ends() -> None:
    lines = [Line("one two"), Line("three four five six"), Line("seven")]
    assert starts_of(VoiceThatTakes(), lines, pause=0.5) == pytest.approx([0.0, 1.5, 4.0])
    assert starts_of(VoiceThatTakes(), [], pause=0.5) == []


def test_a_subtitled_timeline_draws_the_cue_of_the_moment_into_the_band_and_nothing_else() -> None:
    resolution = Resolution(width=320, height=180)
    timeline = Timeline([Still(resolution.blank(255), held_for=4.0)], frames_per_second=10, dissolve=0.0)
    subtitled = Subtitled.over(timeline, [SubtitleCue(1.0, 2.0, "hello there")])
    assert subtitled.duration == timeline.duration and subtitled.frame_count == timeline.frame_count
    assert subtitled.cue_at(1.5) is not None and subtitled.cue_at(2.0) is None
    band = slice(int(resolution.stage_height), resolution.height)
    assert subtitled.frame_at(0.5).min() == 255
    written = subtitled.frame_at(1.5)
    assert written[band].min() < 128
    assert written[: int(resolution.stage_height)].min() == 255
