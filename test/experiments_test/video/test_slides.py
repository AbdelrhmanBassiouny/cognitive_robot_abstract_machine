"""
Tests for :mod:`experiments.video.slides` and the script: the results table and the end
card carry the paper's words and numbers, and nothing that names anyone.
"""

from __future__ import annotations

import numpy as np

from experiments.video.canvas import Ink
from experiments.video.script import CHAPTERS, NarrationLines, ResultRow, VideoScript
from experiments.video.slides import EndCard, ResultsTable
from experiments.video.timeline import Resolution


def test_the_title_is_the_submitted_papers() -> None:
    assert VideoScript().title == (
        "A Unified Knowledge Representation and Reasoning Framework for "
        "Cognitive Architectures"
    )


def test_the_results_table_holds_the_papers_three_rows_with_their_units() -> None:
    script = VideoScript()
    assert script.results_title == "On the real robot: 13 trials in 7 episodes"
    assert [row.value for row in script.results] == ["4 of 4", "213 of 213", "0.10 s"]
    assert all(isinstance(row, ResultRow) for row in script.results)


def test_the_results_table_is_drawn_centred_on_white_with_hairlines_only() -> None:
    table = ResultsTable("On the real robot", VideoScript().results, held_for=4.0)
    assert table.duration == 4.0
    frame = table.frame_at(1.0)
    assert frame.shape == (720, 1280, 3)
    # nothing but the paper's grey and black: no fills in any hue
    coloured = frame[(frame.max(axis=2) - frame.min(axis=2)) > 16]
    assert coloured.size == 0
    # the margins are white
    assert (frame[:, :120] == 255).all() and (frame[:, -120:] == 255).all()


def test_the_end_card_lists_the_three_claims_and_the_link_and_no_numbers() -> None:
    script = VideoScript()
    card = EndCard(script, held_for=5.0)
    assert card.duration == 5.0
    assert [chapter.number for chapter in script.chapters] == [1, 2, 3]
    assert script.chapters == CHAPTERS
    for chapter in script.chapters:
        assert not any(character.isdigit() for character in chapter.claim)
    assert script.repository_link == "https://anonymous.4open.science/r/cognitive_robot_abstract_machine-48BD/"
    frame = card.frame_at(1.0)
    assert frame.min() < 128 and (frame[int(card.resolution.stage_height) :] == 255).all()


def test_the_script_names_no_robot_by_default() -> None:
    assert VideoScript().robot_name == "the robot"
    for line in NarrationLines().every:
        assert "Tracy" not in line.written


def test_the_narration_uses_the_papers_terms_and_none_it_forbids() -> None:
    said = " ".join(line.written for line in NarrationLines().every).lower()
    for forbidden in ("intended meaning", "grounding", "grounded meaning", "adapts", "recovers", "replans", "reacts", "many runs"):
        assert forbidden not in said
    assert "long term memory" in said and "long-term" not in said
    assert "ripple down rules" in said
