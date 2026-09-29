"""
Tests for :mod:`experiments.video.slides`: a results table and a text card, drawn in
greyscale on white and held as long as they are told.
"""

from __future__ import annotations

import numpy as np

from experiments.video.slides import ResultRow, ResultsTable, TextCard
from experiments.video.timeline import Frame, HeldScene

ROWS = (
    ResultRow("Trials that succeeded", "4 of 4"),
    ResultRow("Questions answered", "213 of 213"),
)


def coloured_pixels(frame: Frame) -> np.ndarray:
    """
    The pixels of a frame whose channels differ: any that are not grey.
    """
    return frame[(frame.max(axis=2) - frame.min(axis=2)) > 16]


def test_the_results_table_is_drawn_centred_on_white_with_hairlines_only() -> None:
    table = ResultsTable("On the real robot", ROWS, held_for=4.0)
    assert isinstance(table, HeldScene) and table.duration == 4.0
    frame = table.frame_at(1.0)
    assert frame.shape == table.resolution.shape
    assert coloured_pixels(frame).size == 0
    assert (frame[:, :120] == 255).all() and (frame[:, -120:] == 255).all()
    assert frame.min() < 128


def test_a_text_card_writes_its_heading_and_line_above_the_subtitle_band() -> None:
    card = TextCard("The code", "https://example.org/code", held_for=5.0)
    assert isinstance(card, HeldScene) and card.duration == 5.0
    frame = card.frame_at(1.0)
    assert frame.min() < 128
    assert (frame[int(card.resolution.stage_height) :] == 255).all()
    assert (frame[:200] == 255).all()


def test_a_text_card_writes_both_its_texts() -> None:
    both = TextCard("The code", "a line").frame_at(0.0)
    heading_alone = TextCard("The code", "").frame_at(0.0)
    assert not np.array_equal(both, heading_alone)


def test_slides_cut_in_rather_than_dissolving() -> None:
    assert not ResultsTable("t", ROWS).dissolves_in
    assert not TextCard("h", "l").dissolves_in
