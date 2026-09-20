"""
Tests for :mod:`experiments.video.long_term` and the grid it plays over: the questions
put to long-term memory are built from the query language, answered by whatever the
memory says, and light the tiles their answers name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest
from krrood.entity_query_language.query.query import Query
from segmind.datastructures.events import MotionEvent, PickUpEvent
from typing_extensions import List, Optional

from experiments.video.canvas import Ink
from experiments.video.long_term import RememberedPiece, RememberedQuestion
from experiments.video.perturbations import (
    BAND_HEIGHT,
    CLOSE_UP,
    GridLabels,
    GridLayout,
    PerturbationMatrix,
)

# %% the questions


@dataclass
class MemoryThatAnswers:
    """
    A stand-in for long-term memory that names the same episodes to every question.
    """

    identifiers: List[str]
    asked: List[Query] = field(default_factory=list)

    def answer_with_identifiers(self, question: Query) -> List[str]:
        self.asked.append(question)
        return list(self.identifiers)


def test_a_question_names_the_episodes_its_answer_holds() -> None:
    question = RememberedQuestion("?", (), ("a", "b"), "lit")
    assert question.names("a")
    assert not question.names("c")


def test_the_answer_names_each_episode_once_in_one_order() -> None:
    memory = MemoryThatAnswers(["b", "a", "b"])
    question = RememberedPiece(memory).where_it_moved()  # type: ignore[arg-type]
    assert question.episodes == ("a", "b")
    assert len(memory.asked) == 1 and isinstance(memory.asked[0], Query)


def test_the_two_questions_ask_after_motions_and_pick_ups_of_the_piece() -> None:
    piece = RememberedPiece(MemoryThatAnswers([]), piece="cube")  # type: ignore[arg-type]
    moved, picked_up = piece.both()
    assert "cube" in moved.english and "move" in moved.english
    assert "pick" in picked_up.english
    assert MotionEvent.__name__ in " ".join(moved.statement)
    assert PickUpEvent.__name__ in " ".join(picked_up.statement)
    assert '"cube"' in moved.statement[-1]


def test_the_statements_match_each_class_and_name_the_event_where_it_is_matched() -> None:
    moved, picked_up = RememberedPiece(MemoryThatAnswers([]), piece="cube").both()  # type: ignore[arg-type]
    assert moved.statement[0] == "trial, tick = a(RecordedTrial), a(Tick)"
    assert "motion := a(MotionEvent)" in moved.statement[2] and "motion." in moved.statement[3]
    assert "pickup := a(PickUpEvent)" in picked_up.statement[2] and "pickup." in picked_up.statement[3]
    assert "variable(" not in " ".join(moved.statement) and "entity(" not in " ".join(moved.statement)


def test_the_second_question_marks_only_what_changed_from_the_first() -> None:
    moved, picked_up = RememberedPiece(MemoryThatAnswers([]), piece="cube").both()  # type: ignore[arg-type]
    marked = picked_up.changed_from(moved)
    assert marked[0] == [] and marked[1] == []
    assert [picked_up.statement[2][first:last] for first, last in marked[2]] == ["pickup", "PickUpEvent"]
    assert [picked_up.statement[3][first:last] for first, last in marked[3]] == ["pickup"]


# %% the grid they play over


@dataclass
class StandingFilm:
    length: float


@dataclass
class StandingRun:
    episode_identifier: str


@dataclass
class StandingTile:
    """
    A tile whose film is one flat colour, so what the grid does to it can be read back.
    """

    run: StandingRun
    film: StandingFilm
    shade: int = 128

    def picture_at(self, seconds: float):
        return np.full((9, 16, 3), self.shade, dtype=np.uint8), False


def matrix(questions: List[RememberedQuestion], asked_from: Optional[float] = None) -> PerturbationMatrix:
    tiles = [
        [
            StandingTile(StandingRun(f"{row}{column}"), StandingFilm(20.0 + row))
            for column in range(3)
        ]
        for row in range(2)
    ]
    return PerturbationMatrix(
        tiles,  # type: ignore[arg-type]
        GridLabels(),
        questions=questions,
        speed=10.0,
        question_for=4.0,
        settle_for=1.0,
        asked_from=asked_from,
        resolution=CLOSE_UP,
    )


def test_the_recordings_play_until_the_longest_has_ended() -> None:
    assert matrix([]).runs_for == pytest.approx(2.1)
    assert matrix([]).duration == pytest.approx(3.1)


def test_the_questions_come_after_the_grid_has_settled() -> None:
    first = RememberedQuestion("first?", (), ("00",), "lit")
    second = RememberedQuestion("second?", (), (), "lit")
    grid = matrix([first, second])
    assert grid.duration == pytest.approx(2.1 + 1.0 + 8.0)
    assert grid.question_at(3.0) is None
    asked, progress = grid.question_at(3.1)
    assert asked is first and progress == pytest.approx(0.0)
    asked, progress = grid.question_at(5.1)
    assert asked is first and progress == pytest.approx(0.5)
    asked, progress = grid.question_at(7.5)
    assert asked is second and progress == pytest.approx(0.1)
    asked, progress = grid.question_at(100.0)
    assert asked is second and progress == 1.0


def test_asked_early_the_questions_come_while_the_recordings_play_to_the_end() -> None:
    first = RememberedQuestion("first?", (), ("00",), "lit")
    second = RememberedQuestion("second?", (), (), "lit")
    grid = matrix([first, second], asked_from=1.5)
    assert grid.duration == pytest.approx(1.5 + 8.0)
    assert grid.runs_for == pytest.approx(grid.duration)
    assert grid.question_at(1.4) is None
    asked, progress = grid.question_at(3.5)
    assert asked is first and progress == pytest.approx(0.5)


def test_the_tiles_lie_under_the_band_above_the_subtitles() -> None:
    layout = GridLayout(CLOSE_UP, rows=2, columns=3)
    assert layout.tile(0, 0).y >= BAND_HEIGHT
    assert layout.tile(1, 2).bottom <= CLOSE_UP.stage_height - layout.margin
    assert layout.tile(1, 2).right <= CLOSE_UP.width
    assert layout.tile(0, 0).width == pytest.approx(layout.tile(0, 0).height * 16 / 9)


def test_the_answer_lights_the_tiles_it_names_and_dims_the_rest() -> None:
    question = RememberedQuestion("which?", ("a line",), ("01",), "lit")
    grid = matrix([question])
    named, unnamed = grid.layout.tile(0, 1), grid.layout.tile(0, 0)
    answered = grid.picture_at(grid.runs_for + grid.settle_for + 4.0 * 0.95)
    before = grid.picture_at(grid.runs_for)
    edge = answered[int(named.y) - 1, int(named.centre[0])]
    assert tuple(edge) == Ink.ANSWER.rgb
    inside_unnamed = (int(unnamed.centre[1]) + 20, int(unnamed.centre[0]))
    assert answered[inside_unnamed].mean() > before[inside_unnamed].mean()
    inside_named = (int(named.centre[1]) + 20, int(named.centre[0]))
    assert tuple(answered[inside_named]) == tuple(before[inside_named])


def test_the_band_marks_the_second_question_where_it_differs_from_the_first() -> None:
    first = RememberedQuestion("moved?", ("x := a(MotionEvent)",), ("01",), "lit")
    second = RememberedQuestion("picked up?", ("x := a(PickUpEvent)",), ("01",), "lit")
    grid = matrix([first, second])
    assert grid.marked_in(first) == ([],)
    assert grid.marked_in(second) == ([(7, 18)],)
    band = grid.layout.band
    first_up = grid.picture_at(grid.asked_at + 0.5)[int(band.y) : int(band.bottom), int(band.x) : int(band.right)]
    second_up = grid.picture_at(grid.asked_at + grid.question_for + 0.5)[int(band.y) : int(band.bottom), int(band.x) : int(band.right)]
    assert Ink.MARKER.rgb not in {tuple(pixel) for pixel in first_up.reshape(-1, 3)}
    assert Ink.MARKER.rgb in {tuple(pixel) for pixel in second_up.reshape(-1, 3)}
