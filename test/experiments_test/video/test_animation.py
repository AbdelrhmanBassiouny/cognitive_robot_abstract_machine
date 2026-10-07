"""
Tests for :mod:`experiments.video.animation`: the beats an animated scene plays its
steps against, and how a wrong number of beats is refused.
"""

from __future__ import annotations

import pytest
from typing_extensions import Tuple

from experiments.video.animation import AnimationStep, BeatMiscount, BeatSchedule
from experiments.video.narration import Line, Storyboard, starts_of

from .voices import EvenlyPacedVoice


@pytest.fixture
def voice() -> EvenlyPacedVoice:
    """
    A voice that says every word in the same time.
    """
    return EvenlyPacedVoice(seconds_per_word=0.5)


@pytest.fixture
def pause() -> float:
    """
    The silence a storyboard leaves between two lines of one scene.
    """
    return Storyboard(narrated=[]).pause


@pytest.fixture
def lines() -> Tuple[Line, ...]:
    """
    Three lines of different lengths, so the beats of a schedule differ in length.
    """
    return (Line("One word"), Line("Two words said here"), Line("Three"))


@pytest.fixture
def schedule(
    lines: Tuple[Line, ...], voice: EvenlyPacedVoice, pause: float
) -> BeatSchedule:
    """
    The schedule an animation of those lines plays against.
    """
    return BeatSchedule.of(lines, voice, pause=pause)


# %% the beats a schedule holds


def test_a_schedule_holds_one_beat_per_line(
    schedule: BeatSchedule, lines: Tuple[Line, ...]
) -> None:
    assert [beat.line for beat in schedule.beats] == list(lines)


def test_a_beat_lasts_its_line_plus_the_pause(
    schedule: BeatSchedule,
    lines: Tuple[Line, ...],
    voice: EvenlyPacedVoice,
    pause: float,
) -> None:
    for beat, line in zip(schedule.beats, lines):
        assert beat.duration == pytest.approx(line.spoken_by(voice).duration + pause)


def test_a_beat_starts_where_its_line_starts(
    schedule: BeatSchedule,
    lines: Tuple[Line, ...],
    voice: EvenlyPacedVoice,
    pause: float,
) -> None:
    assert schedule.starts == pytest.approx(starts_of(voice, lines, pause))


def test_a_schedule_lasts_as_long_as_its_beats_together(
    schedule: BeatSchedule,
) -> None:
    assert schedule.duration == pytest.approx(
        sum(beat.duration for beat in schedule.beats)
    )


# %% steps are scaled down to fit a beat, never stretched


def test_steps_longer_than_their_beat_are_scaled_down_to_fit(
    schedule: BeatSchedule,
) -> None:
    beat = schedule.beats[2]
    steps = (AnimationStep(weight=10.0), AnimationStep(weight=10.0))

    lengths = beat.lengths_of(steps)

    assert sum(lengths) <= beat.duration
    assert lengths[0] == pytest.approx(lengths[1])


def test_steps_shorter_than_their_beat_keep_their_length(
    schedule: BeatSchedule,
) -> None:
    beat = schedule.beats[1]
    steps = (AnimationStep(weight=0.2), AnimationStep(weight=0.3))

    assert beat.lengths_of(steps) == pytest.approx([0.2, 0.3])


def test_a_step_never_runs_shorter_than_the_shortest_a_beat_allows(
    schedule: BeatSchedule,
) -> None:
    beat = schedule.beats[2]
    many = tuple(AnimationStep(weight=1.0) for _ in range(100))

    assert min(beat.lengths_of(many)) == pytest.approx(beat.shortest_step)


def test_the_rest_of_a_beat_is_waited_out(schedule: BeatSchedule) -> None:
    beat = schedule.beats[1]
    steps = (AnimationStep(weight=0.2),)

    assert beat.waits_after(steps) == pytest.approx(beat.duration - 0.2)


def test_a_beat_its_steps_fill_waits_out_only_its_headroom(
    schedule: BeatSchedule,
) -> None:
    beat = schedule.beats[0]
    steps = (AnimationStep(weight=100.0),)

    assert beat.waits_after(steps) == pytest.approx(beat.headroom)


# %% playing a different number of beats than there are lines


def test_playing_fewer_beats_than_there_are_lines_is_refused(
    schedule: BeatSchedule,
) -> None:
    with pytest.raises(BeatMiscount):
        schedule.check_played(2)


def test_playing_more_beats_than_there_are_lines_is_refused(
    schedule: BeatSchedule,
) -> None:
    with pytest.raises(BeatMiscount):
        schedule.check_played(4)


def test_playing_one_beat_per_line_is_accepted(
    schedule: BeatSchedule, lines: Tuple[Line, ...]
) -> None:
    assert schedule.check_played(len(lines)) is None


def test_the_miscount_names_what_was_played_and_how_many_lines_there_are(
    schedule: BeatSchedule, lines: Tuple[Line, ...]
) -> None:
    with pytest.raises(BeatMiscount) as refused:
        schedule.check_played(1)

    assert refused.value.played == 1
    assert refused.value.lines == len(lines)
