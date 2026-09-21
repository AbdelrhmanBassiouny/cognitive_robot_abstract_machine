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

from experiments.video.canvas import VIDEO_RESOLUTION, Ink
from experiments.video.long_term import RememberedPiece, RememberedQuestion
from experiments.video.perturbations import (
    ZOOM,
    GridLabels,
    GridLayout,
    GridSequence,
    Phase,
    Zoom,
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


def test_the_answer_is_kept_to_the_episodes_the_questions_are_asked_over() -> None:
    memory = MemoryThatAnswers(["a", "b", "c"])
    question = RememberedPiece(memory, over=frozenset({"b", "c", "d"})).where_the_robot_picked_it_up()  # type: ignore[arg-type]
    assert question.episodes == ("b", "c")
    assert len(memory.asked) == 1


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
    A tile whose film is one flat colour, so what the grid does to it can be read back;
    the moment asked for is kept, and the phase is given.
    """

    run: StandingRun
    film: StandingFilm
    shade: int = 128
    phase: Optional[Phase] = None
    asked: List[float] = field(default_factory=list)

    def picture_at(self, seconds: float):
        self.asked.append(seconds)
        return np.full((9, 16, 3), self.shade, dtype=np.uint8), self.phase


QUESTION = RememberedQuestion("which?", ("a line",), ("01",), "lit")


def sequence(zooms=(Zoom(0, 2, 20.0, 2.0), Zoom(1, 1, 8.0, 3.0))) -> GridSequence:
    tiles = [
        [StandingTile(StandingRun(f"{row}{column}"), StandingFilm(20.0 + row)) for column in range(3)]
        for row in range(2)
    ]
    return GridSequence(
        tiles,  # type: ignore[arg-type]
        GridLabels(header="a header", long_term_header="asked over the seven"),
        zooms,
        QUESTION,
        speed=10.0,
        play_for=4.0,
        asked_after=0.5,
        question_for=6.0,
    )


def test_the_grid_plays_pauses_through_the_zooms_and_plays_on() -> None:
    grid = sequence()
    zooms = 2 * ZOOM + 2.0 + 2 * ZOOM + 3.0
    assert grid.resumes_at == pytest.approx(4.0 + zooms)
    assert grid.asked_at == pytest.approx(4.0 + zooms + 0.5)
    assert grid.duration == pytest.approx(4.0 + zooms + 0.5 + 6.0)
    assert grid.recording_at(2.0) == pytest.approx(20.0)
    assert grid.recording_at(6.0) == pytest.approx(40.0)  # paused
    assert grid.recording_at(grid.resumes_at + 1.0) == pytest.approx(50.0)


def test_a_zoom_grows_holds_and_shrinks_and_replays_its_tile_from_where_it_is_told() -> None:
    grid = sequence()
    assert grid.zoom_at(3.9) is None
    zoom, out, held = grid.zoom_at(4.0 + ZOOM / 2)
    assert zoom is grid.zooms[0] and 0.0 < out < 1.0 and held == 0.0
    zoom, out, held = grid.zoom_at(4.0 + ZOOM + 1.0)
    assert zoom is grid.zooms[0] and out == 1.0 and held == pytest.approx(1.0)
    zoom, out, held = grid.zoom_at(4.0 + ZOOM + 2.0 + ZOOM / 2)
    assert zoom is grid.zooms[0] and 0.0 < out < 1.0
    zoom, out, held = grid.zoom_at(4.0 + grid.zooms[0].lasts + ZOOM + 0.5)
    assert zoom is grid.zooms[1] and out == 1.0
    tile = grid.tiles[0][2]
    grid.picture_at(4.0 + ZOOM + 1.0)
    assert tile.asked[-1] == pytest.approx(20.0 + 1.0 * 3.0)


def test_the_zoomed_tile_grows_to_the_front_and_the_rest_dim() -> None:
    grid = sequence()
    layout = grid.layout
    front = layout.front
    assert front.width / front.height == pytest.approx(16 / 9, rel=1e-3)
    assert front.bottom <= VIDEO_RESOLUTION.stage_height
    other = layout.tile(1, 0)
    playing = grid.picture_at(2.0)
    # halfway out, the growing tile has not yet covered the lower left tile's left edge
    growing = grid.picture_at(4.0 + ZOOM / 2)
    inside = (int(other.centre[1]), int(other.x + 12))
    assert growing[inside].mean() > playing[inside].mean() == 128.0
    zoomed = grid.picture_at(4.0 + ZOOM + 1.0)
    at_front = (int(front.centre[1]), int(front.centre[0]))
    assert tuple(zoomed[at_front]) == (128, 128, 128)


def test_the_question_comes_once_the_grid_plays_on_and_its_answer_outlines_the_tiles_it_names() -> None:
    grid = sequence()
    assert grid.question_progress(grid.asked_at - 0.1) is None
    assert grid.question_progress(grid.asked_at + 3.0) == pytest.approx(0.5)
    named, unnamed = grid.layout.tile(0, 1), grid.layout.tile(0, 0)
    answered = grid.picture_at(grid.asked_at + 6.0 * 0.95)
    before = grid.picture_at(grid.resumes_at)
    edge = answered[int(named.y) - 1, int(named.centre[0])]
    assert tuple(edge) == Ink.ANSWER.rgb
    inside_unnamed = (int(unnamed.centre[1]) + 20, int(unnamed.centre[0]))
    assert answered[inside_unnamed].mean() > before[inside_unnamed].mean()
    inside_named = (int(named.centre[1]) + 20, int(named.centre[0]))
    assert tuple(answered[inside_named]) == tuple(before[inside_named])


def test_the_tiles_lie_under_the_band_above_the_captions() -> None:
    layout = GridLayout(VIDEO_RESOLUTION, rows=2, columns=3)
    assert layout.tile(0, 0).y >= layout.band.bottom
    assert layout.tile(1, 2).bottom <= VIDEO_RESOLUTION.stage_height
    assert layout.tile(1, 2).right <= VIDEO_RESOLUTION.width
    assert layout.tile(0, 0).width == pytest.approx(layout.tile(0, 0).height * 16 / 9)


def test_the_labels_tag_a_tile_by_its_column_and_row() -> None:
    assert GridLabels().tag(0, 2) == "board moved · scene stands still"
