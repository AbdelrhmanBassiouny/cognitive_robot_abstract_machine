"""
The card of what a run's motions asked the controller for, drawn as the plan the robot
ran with the moment the question was kept at marked on it.
"""

from __future__ import annotations

from pathlib import Path

from experiments.episodes.episode import RecordedQuery, RecordedTrial
from experiments.paper.panel import PanelKind
from experiments.paper.query_card import (
    MotionsRequestedCard,
    QueryCardName,
    QueryCardSet,
)
from experiments.questions.long_term_memory import MotionsRequestedInTheEpisode

from .test_paper_run_plan import cube, trial

ASKED_AT = 6.0
"""
Seconds into the trial the question about its motions was kept at.
"""


def asked_what_its_motions_requested(trial: RecordedTrial) -> RecordedTrial:
    """
    The given trial, keeping the question of what its motions asked the controller for.

    :param trial: A trial that ran a plan.
    """
    trial.queries.append(
        RecordedQuery(
            role_taker=MotionsRequestedInTheEpisode(
                episode_identifier=trial.episode.identifier
            ),
            answer="[]",
            latency=0.01,
            moment=ASKED_AT,
        )
    )
    return trial


def test_the_card_of_what_the_motions_requested_shows_the_plan_the_robot_ran(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    What a motion asked the controller for is read against the actions it was part of,
    so the card is the plan the run performed.
    """
    [written] = MotionsRequestedCard().write(
        asked_what_its_motions_requested(trial), tmp_path
    )
    assert set(written.panel_paths) == {PanelKind.PLAN_TIMELINE}


def test_the_paper_draws_the_card_of_what_the_motions_requested(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    written = QueryCardSet.for_the_paper().write(
        asked_what_its_motions_requested(trial), tmp_path
    )
    assert [card.card for card in written] == [QueryCardName.MOTIONS_REQUESTED]
