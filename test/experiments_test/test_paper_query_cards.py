"""
One query of the paper shown beside a picture of what its answer means.

Which queries a card claims, which things in the twin it picks out and which events it
marks are all read off the trial and need no graphics; only writing the pictures
themselves does, so those tests are skipped where the run named no offscreen backend.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest
from coraplex.datastructures.enums import ExecutionType
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from typing_extensions import List

from experiments.episodes.episode import Episode, RecordedQuery, RecordedTrial, Tick
from experiments.paper.figure import FigureFile
from experiments.paper.panel import PanelKind
from experiments.paper.query_card import (
    TRIAL_DIRECTORY,
    EpisodeKeptNoWorldError,
    PickedUpRecentlyCard,
    QueryCardName,
    QueryCardSet,
    SideOfAnotherObjectCard,
    UnknownQueryCardError,
)
from experiments.questions.working_memory import (
    ObjectsSeen,
    PickedUpRecently,
    Side,
    SideOfAnotherObject,
)
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from .offscreen_rendering import needs_a_renderer

# %% the run the cards are drawn from

SUBJECT_NAME = "square_piece"
"""
The object the questions about one object are about.
"""

OTHER_NAME = "round_piece"
"""
The object it is placed against.
"""

PIECE_COLOR = Color(0.2, 0.4, 0.9, 1.0)
"""
The colour both pieces state in the twin.
"""

TRIAL_DURATION = 10.0
"""
How long the recorded trial ran, in seconds.
"""

PICKED_UP_AT = 2.0
"""
The moment the trial's pick-up was reported at, in seconds from its start.
"""

INSERTED_AT = 5.0
"""
The moment the trial's insertion was reported at, in seconds from its start.
"""

ASKED_AT = 6.0
"""
The moment every query of the trial was asked at, in seconds from its start.
"""

IMAGE_IN_TYPST = re.compile(r'image\("([^"]+)"\)')
"""
How a Typst figure names the picture it shows, which is what a card's markup is checked
against.
"""


def piece(name: str) -> Body:
    """
    One of the two pieces standing on the table.

    :param name: What the piece is called.
    """
    body = Body(name=PrefixedName(name))
    box = Box(scale=Scale(0.1, 0.1, 0.1), color=PIECE_COLOR)
    body.visual = ShapeCollection([box], reference_frame=body)
    body.collision = ShapeCollection([box], reference_frame=body)
    return body


@pytest.fixture
def scene() -> World:
    """
    A world holding the two pieces the questions are about.
    """
    world = World()
    subject = piece(SUBJECT_NAME)
    other = piece(OTHER_NAME)
    with world.modify_world():
        world.add_body(subject)
        world.add_connection(
            FixedConnection(
                parent=subject,
                child=other,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    y=0.4
                ),
            )
        )
    return world


def asked(question, answer: str) -> RecordedQuery:
    """
    One query of the trial, asked at the moment every one of them was.

    :param question: The question that was asked.
    :param answer: The answer as it was rendered for a reader.
    """
    return RecordedQuery(
        role_taker=question, answer=answer, latency=0.01, moment=ASKED_AT
    )


@pytest.fixture
def trial(scene: World) -> RecordedTrial:
    """
    One recorded trial that asked a spatial question and a question about a pick-up.
    """
    subject = scene.get_body_by_name(SUBJECT_NAME)
    other = scene.get_body_by_name(OTHER_NAME)
    episode = Episode(
        scenario_name="shape_sorting",
        execution_type=ExecutionType.SIMULATED,
        world=scene,
    )
    return RecordedTrial(
        episode=episode,
        outcome=TrialOutcome.SUCCEEDED,
        duration=TRIAL_DURATION,
        ticks=[
            Tick(moment=PICKED_UP_AT, events=[PickUpEvent(tracked_object=subject)]),
            Tick(moment=INSERTED_AT, events=[InsertionEvent(tracked_object=subject)]),
        ],
        queries=[
            asked(
                SideOfAnotherObject(
                    subject=subject,
                    other=other,
                    side=side,
                    point_of_view=HomogeneousTransformationMatrix.from_xyz_rpy(x=-1.0),
                ),
                answer="yes" if side is Side.LEFT else "no",
            )
            for side in Side
        ]
        + [asked(PickedUpRecently(subject=subject), answer="yes")],
    )


def written_images(card_markup: Path) -> List[str]:
    """
    Every picture one card's markup names, in the order it names them.

    :param card_markup: The Typst the card wrote.
    """
    return IMAGE_IN_TYPST.findall(card_markup.read_text())


# %% which queries a card shows


def test_a_card_shows_every_asking_of_its_own_question(
    trial: RecordedTrial,
) -> None:
    """
    A question asked twice in one trial is two cards, so the card claims both askings.
    """
    assert SideOfAnotherObjectCard().queries_in(trial) == trial.queries[:2]


def test_a_card_claims_no_query_of_another_question(trial: RecordedTrial) -> None:
    """
    Cards do not overlap: each claims only the askings of the question it shows.
    """
    assert [
        query.question.side for query in SideOfAnotherObjectCard().queries_in(trial)
    ] == list(Side)
    assert PickedUpRecentlyCard().queries_in(trial) == trial.queries[2:]


def test_a_card_whose_question_the_trial_never_asked_shows_nothing(
    trial: RecordedTrial,
) -> None:
    """
    A trial that never asked a question has no card for it rather than an empty one.
    """
    assert (
        QueryCardSet.for_the_paper()
        .card_named(QueryCardName.OBJECTS_SEEN)
        .queries_in(trial)
        == []
    )


# %% what a card picks out


def test_a_spatial_card_picks_out_both_objects_it_relates(
    trial: RecordedTrial, scene: World
) -> None:
    """
    What a yes or no about one object being left of another means is where the two
    stand, so both are picked out.
    """
    question = trial.queries[0].question
    assert SideOfAnotherObjectCard().answers(question, scene) == [
        question.subject,
        question.other,
    ]


def test_a_spatial_card_is_drawn_from_where_the_question_was_asked(
    trial: RecordedTrial, scene: World
) -> None:
    """
    Left and right are only left and right from somewhere, so the camera stands where
    the question says it was looked at from.
    """
    question = trial.queries[0].question
    camera = SideOfAnotherObjectCard().point_of_view(question, scene)
    assert camera.position == pytest.approx(
        question.point_of_view.to_position().to_np()[:3].tolist()
    )


def test_a_card_about_what_happened_picks_out_the_object_it_asks_about(
    trial: RecordedTrial, scene: World
) -> None:
    """
    A question about one object being picked up is about that object.
    """
    question = trial.queries[2].question
    assert PickedUpRecentlyCard().answers(question, scene) == [question.subject]


def test_a_card_about_a_pick_up_marks_the_pick_ups_that_were_reported(
    trial: RecordedTrial,
) -> None:
    """
    The events a query answered are what the timeline picks out, so the card hands it
    the monitor's own reports of them.
    """
    reported = PickedUpRecentlyCard().emphasise(trial.queries[2].question, trial)
    assert reported == [trial.ticks[0].events[0]]


def test_a_card_marks_no_event_of_another_object(
    trial: RecordedTrial, scene: World
) -> None:
    """
    A pick-up of something else is not what this question answered.
    """
    question = PickedUpRecently(subject=scene.get_body_by_name(OTHER_NAME))
    assert PickedUpRecentlyCard().emphasise(question, trial) == []


def test_a_card_not_about_anything_that_happened_marks_no_event(
    trial: RecordedTrial,
) -> None:
    """
    A spatial question is about where things are, not about anything the monitor saw.
    """
    assert SideOfAnotherObjectCard().emphasise(trial.queries[0].question, trial) == []


# %% which cards the paper shows


def test_the_paper_shows_a_card_for_each_of_the_working_memory_questions() -> None:
    """
    The four questions the paper shows pictures of each have a card, in the order they
    are printed.
    """
    assert [card.name for card in QueryCardSet.for_the_paper().cards] == list(
        QueryCardName
    )


def test_each_card_shows_the_question_it_is_named_after() -> None:
    """
    A card is named by the question it shows, so the two agree.
    """
    cards = QueryCardSet.for_the_paper()
    assert cards.card_named(QueryCardName.OBJECTS_SEEN).question is ObjectsSeen
    assert (
        cards.card_named(QueryCardName.SIDE_OF_ANOTHER_OBJECT).question
        is SideOfAnotherObject
    )
    assert (
        cards.card_named(QueryCardName.PICKED_UP_RECENTLY).question is PickedUpRecently
    )


def test_asking_the_set_for_a_card_it_does_not_hold_says_so() -> None:
    """
    A card the set does not hold is said to be missing rather than answered with none.
    """
    with pytest.raises(UnknownQueryCardError):
        QueryCardSet(cards=[]).card_named(QueryCardName.OBJECTS_SEEN)


# %% what a card is called


def test_every_asking_of_a_question_is_written_under_its_own_name() -> None:
    """
    Two askings of one question in a trial must not write over each other, so each
    carries its own number.
    """
    card = SideOfAnotherObjectCard()
    assert card.stem(1) != card.stem(2)
    assert card.markup_file_name(1).endswith(FigureFile.TYPST_TABLE.value)
    assert card.panel_file_name(1, PanelKind.SCENE).endswith(FigureFile.IMAGE.value)


# %% an episode that kept nothing to draw


def test_a_card_of_an_episode_that_kept_no_world_says_so(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    A scene cannot be drawn of a run whose world was not kept, which is said rather than
    left to fail wherever the twin would have been read.
    """
    trial.episode.world = None
    with pytest.raises(EpisodeKeptNoWorldError):
        PickedUpRecentlyCard().write(trial, tmp_path)


# %% writing the card out


@needs_a_renderer
def test_a_card_writes_one_picture_per_panel_it_shows(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    A run that kept no camera recording has no camera frame, so the card is drawn with
    the panels there is something to draw and no file is left for the one there is not.
    """
    [written] = PickedUpRecentlyCard().write(trial, tmp_path)
    assert set(written.panel_paths) == {PanelKind.SCENE, PanelKind.TIMELINE}
    assert all(path.is_file() for path in written.panel_paths.values())


@needs_a_renderer
def test_a_cards_markup_names_exactly_the_pictures_it_wrote(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    The markup the paper includes is what makes the pictures reachable, so it names
    every one the card left and nothing it did not.
    """
    [written] = PickedUpRecentlyCard().write(trial, tmp_path)
    assert written_images(written.markup_path) == [
        path.name for path in written.panel_paths.values()
    ]


@needs_a_renderer
def test_a_cards_markup_says_what_was_asked_and_what_was_answered(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    A picture on its own says nothing without the query it answers, so the markup
    carries both.
    """
    [written] = PickedUpRecentlyCard().write(trial, tmp_path)
    markup = written.markup_path.read_text()
    assert written.query.text in markup
    assert written.query.answer in markup


@needs_a_renderer
def test_the_set_writes_a_card_for_every_query_each_of_its_cards_shows(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    Every asking of a question the paper shows becomes a card of its own, and a question
    the paper shows in two ways becomes one card of each -- so what the set writes is
    every pairing of one of its cards with a query that card shows.
    """
    cards = QueryCardSet.for_the_paper()

    written = cards.write(trial, tmp_path)

    assert [(card.card, card.query) for card in written] == [
        (card.name, query) for card in cards.cards for query in card.queries_in(trial)
    ]


# %% a whole corpus of runs


@needs_a_renderer
def test_every_episode_is_written_under_its_own_identifier(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    A corpus is written in one pass, so each episode's cards go under what addresses
    that episode outside the database.
    """
    written = QueryCardSet.for_the_paper().write_every_episode([trial], tmp_path)
    assert {card.markup_path.parent.parent.name for card in written} == {
        trial.episode.identifier
    }


@needs_a_renderer
def test_two_trials_of_one_episode_do_not_write_over_each_other(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    Every trial of an episode asks the same questions, so each is given a directory of
    its own inside the episode's.
    """
    second = replace(trial)
    written = QueryCardSet.for_the_paper().write_every_episode(
        [trial, second], tmp_path
    )
    assert {card.markup_path.parent.name for card in written} == {
        TRIAL_DIRECTORY % 1,
        TRIAL_DIRECTORY % 2,
    }
