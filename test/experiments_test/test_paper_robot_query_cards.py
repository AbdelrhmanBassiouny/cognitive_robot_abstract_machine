"""
The two cards whose answers are about the robot rather than about one object of the
scene: what it says it can see, and what it says it is made of.

Both read the robot off the world the episode kept, so unlike the cards about a named
object they need a world with a robot standing in it. The scene the frozen set is asked
of is exactly that, so it is the scene these are drawn from.
"""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest
from coraplex.datastructures.enums import ExecutionType

from experiments.episodes.episode import Episode, RecordedQuery, RecordedTrial
from experiments.paper.panel import PanelKind
from experiments.paper.lettering import drawn
from experiments.paper.scene import LABEL_COLOR
from experiments.paper.query_card import (
    ObjectsSeenCard,
    OwnDegreesOfFreedomCard,
    QueryCardName,
    QueryCardSet,
    RobotNotFoundInTheWorldError,
)
from experiments.questions.working_memory import (
    NumberOfOwnDegreesOfFreedom,
    ObjectsSeen,
)
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.world import World

from .offscreen_rendering import needs_a_renderer
from .test_questions import QuestionedScene, scene, two_arm_robot_world

# %% the run these cards are drawn from

TRIAL_DURATION = 12.0
"""
How long the recorded trial ran, in seconds.
"""

ASKED_AT = 4.0
"""
The moment both queries were asked at, in seconds from the start of the trial.
"""


@pytest.fixture
def trial(scene: QuestionedScene) -> RecordedTrial:
    """
    One recorded trial of the robot's own scene, which asked what it sees and how many
    joints it has.
    """
    episode = Episode(
        scenario_name="shape_sorting",
        execution_type=ExecutionType.SIMULATED,
        world=scene.world,
    )
    return RecordedTrial(
        episode=episode,
        outcome=TrialOutcome.SUCCEEDED,
        duration=TRIAL_DURATION,
        queries=[
            RecordedQuery(
                role_taker=ObjectsSeen(scene=scene.as_set_up),
                answer="a table, a cube and a cylinder",
                latency=0.02,
                moment=ASKED_AT,
            ),
            RecordedQuery(
                role_taker=NumberOfOwnDegreesOfFreedom(),
                answer="6",
                latency=0.01,
                moment=ASKED_AT,
            ),
        ],
    )


# %% what the robot says it sees


def test_the_objects_seen_card_picks_out_the_objects_the_question_names(
    trial: RecordedTrial, scene: QuestionedScene
) -> None:
    """
    The card draws the twin the run happened in and the question is scored on what
    whoever set that scene up says they put there, so what the card picks out is what
    the question's true answer names.
    """
    question = trial.queries[0].question

    picked_out = ObjectsSeenCard().answers(question, scene.world)

    assert question.ground_truth(scene.robot).agrees_with(picked_out)


def test_the_objects_seen_card_picks_out_what_stands_in_the_scene(
    trial: RecordedTrial, scene: QuestionedScene
) -> None:
    """
    The objects the robot is asked about are the ones standing in front of it.
    """
    picked_out = ObjectsSeenCard().answers(trial.queries[0].question, scene.world)
    assert scene.table in picked_out
    assert scene.cube in picked_out
    assert scene.cylinder in picked_out


def test_the_objects_seen_card_leaves_the_robots_own_body_out(
    trial: RecordedTrial, scene: QuestionedScene
) -> None:
    """
    The robot's own links are not objects of the scene, so a picture of what it sees does
    not pick the robot out of itself.
    """
    picked_out = ObjectsSeenCard().answers(trial.queries[0].question, scene.world)
    assert not any(own in picked_out for own in scene.robot.bodies)


# %% what the robot says it is made of


def test_the_degrees_of_freedom_card_picks_out_the_robots_own_body(
    trial: RecordedTrial, scene: QuestionedScene
) -> None:
    """
    A count of joints is not a thing standing anywhere, so what its answer means is the
    body those joints hold together.
    """
    assert OwnDegreesOfFreedomCard().answers(
        trial.queries[1].question, scene.world
    ) == list(scene.robot.bodies)


def test_a_card_about_the_robot_needs_a_world_that_says_which_robot(
    trial: RecordedTrial,
) -> None:
    """
    A question about the robot's own body is about one robot, so a world holding none
    says so rather than drawing an empty picture.
    """
    with pytest.raises(RobotNotFoundInTheWorldError):
        OwnDegreesOfFreedomCard().answers(trial.queries[1].question, World())


# %% both cards drawn


@needs_a_renderer
def test_both_cards_of_the_robots_own_scene_are_drawn(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    The two questions the trial asked each become a card, drawn from the world the
    episode kept.
    """
    written = QueryCardSet.for_the_paper().write(trial, tmp_path)
    assert [card.card for card in written] == [
        QueryCardName.OBJECTS_SEEN,
        QueryCardName.OWN_DEGREES_OF_FREEDOM,
    ]
    assert all(path.is_file() for card in written for path in card.panel_paths.values())


@needs_a_renderer
def test_a_card_about_the_robot_itself_shows_only_the_scene(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    How many joints the robot has is not something that happened at a moment, so its
    card carries no timeline of the run.
    """
    [written] = OwnDegreesOfFreedomCard().write(trial, tmp_path)
    assert set(written.panel_paths) == {PanelKind.SCENE}


# %% naming what is picked out


def names_written_on(picture: Path) -> int:
    """
    How many pixels of a drawn scene were written on rather than rendered.

    :param picture: The scene panel that was written.
    """
    drawn_scene = imageio.imread(picture)
    return int(np.all(drawn_scene[:, :, :3] == drawn(LABEL_COLOR), axis=-1).sum())


@needs_a_renderer
def test_a_card_answering_with_named_objects_writes_their_names(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    A card whose answer is a handful of objects is read by their names, so each is
    written over the object it names.
    """
    [written] = ObjectsSeenCard().write(trial, tmp_path)
    assert names_written_on(written.panel_paths[PanelKind.SCENE]) > 0


@needs_a_renderer
def test_a_card_answering_with_a_whole_robot_names_none_of_its_links(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    A dozen link names written over each other say less than the shape they are drawn
    on, so the card that picks out a whole robot writes none of them.
    """
    [written] = OwnDegreesOfFreedomCard().write(trial, tmp_path)
    assert names_written_on(written.panel_paths[PanelKind.SCENE]) == 0
