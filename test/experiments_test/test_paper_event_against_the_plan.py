"""
The card that says why the answer is yes or no, not only what it is.

Two runs are drawn here, and they are the two the card exists for. Both are about the
same piece and both end with it somewhere else; what tells them apart is *when*.

In one the robot picked it up: a pick-up was reported while the item of the plan that
picks that piece up was running. In the other a person shoved it while the robot was
still idle -- the plan's pick-up of that same piece does not start until later -- so a
translation was reported at a moment nothing was running to account for it. The four
levels are what lets a reader see that difference.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from typing_extensions import Tuple

import imageio.v2 as imageio
import pytest
from coraplex.datastructures.enums import ExecutionType
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import PlanNode
from giskardpy.motion_statechart.data_types import LifeCycleValues
from segmind.datastructures.events import PickUpEvent, TranslationEvent

from experiments.episodes.episode import (
    Episode,
    InsertionAttempt,
    InsertionOutcome,
    RecordedQuery,
    RecordedTrial,
    Tick,
)
from experiments.paper.layered import Layer, LayeredFigure
from experiments.paper.panel import PanelKind
from experiments.paper.plan_timeline import PlanTimeline
from experiments.paper.query_card import (
    EventAgainstThePlanCard,
    QueryCardName,
    QueryCardSet,
)
from experiments.paper.run_plan import RunPlan
from experiments.questions.working_memory import PickedUpRecently
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import Connection6DoF
from semantic_digital_twin.world_description.world_entity import Body

from .offscreen_rendering import needs_a_renderer
from .test_paper_run_plan import ActsOnOneBody, item_ran
from .test_paper_scene_render import ANSWERED_NAME, OTHER_NAME, standing_box

# %% the run both cards are drawn from

TRIAL_BEGAN_AT = datetime(2026, 1, 1, 12, 0, 0)
"""
The instant the recorded trial's first plan item started.
"""

TRIAL_DURATION = 12.0
"""
How long each recorded trial ran, in seconds.
"""

SOMETHING_HAPPENED_AT = 3.0
"""
Seconds into the trial the monitor reported what the card is about.
"""

PICKING_WHILE_IT_HAPPENED = (2.0, 5.0)
"""
The seconds of the trial the plan's pick-up ran over in the run the robot did it, which
is a stretch the reported moment falls inside.
"""

PICKING_LONG_AFTERWARDS = (6.0, 9.0)
"""
The seconds of the trial the plan's pick-up ran over in the run a person did it.

The robot has not reached the piece yet when the piece moves, so nothing at all is
running at the reported moment -- which is what makes the answer no.
"""

ASKED_AT = 8.0
"""
Seconds into the trial the query was asked.
"""

STOOD_AT = 0.5
"""
Where along the world's x-axis the piece stood before it moved, in metres.
"""

ENDED_AT = -0.5
"""
Where along the world's x-axis the piece ended up, in metres.
"""


@pytest.fixture
def scene() -> World:
    """
    A world holding a fixed box and a loose piece hanging from it, which is a scene a
    render can stand the piece somewhere else in.
    """
    world = World()
    stands = standing_box(ANSWERED_NAME)
    loose = standing_box(OTHER_NAME)
    with world.modify_world():
        world.add_body(stands)
        world.add_connection(
            Connection6DoF.create_with_dofs(world=world, parent=stands, child=loose)
        )
    return world


@pytest.fixture
def piece(scene: World) -> Body:
    """
    The loose piece both runs are about.
    """
    return scene.get_body_by_name(OTHER_NAME)


def moved(subject: Body, moment: float) -> TranslationEvent:
    """
    The translation the monitor reported of a piece.

    :param subject: The piece that moved.
    :param moment: Seconds into the trial it was reported at.
    """
    return TranslationEvent(
        tracked_object=subject,
        start_pose=Pose.from_xyz_rpy(x=STOOD_AT),
        current_pose=Pose.from_xyz_rpy(x=ENDED_AT),
        timestamp=TRIAL_BEGAN_AT + timedelta(seconds=moment),
    )


def ran_a_plan_picking_up(piece: Body, over: Tuple[float, float]) -> InsertionAttempt:
    """
    One attempt whose plan picks the given piece up over the given stretch of the trial.

    :param piece: The piece the plan's item acts on.
    :param over: The seconds of the trial it ran between.
    """
    plan = Plan()
    root = PlanNode()
    root.start_time = TRIAL_BEGAN_AT
    plan.add_node(root)
    item = item_ran(
        ActsOnOneBody(subject=piece), over[0], over[1], LifeCycleValues.SUCCEEDED
    )
    plan.add_node(item)
    root.add_child(item)
    return InsertionAttempt(
        shape_name=piece.name.name, plan=plan, outcome=InsertionOutcome.FELL_THROUGH
    )


def run_that(
    scene: World,
    piece: Body,
    saw,
    picking_up_over: Tuple[float, float],
    answer: str,
):
    """
    One recorded trial of the shape-sorting scenario.

    :param scene: The world it ran in.
    :param piece: The piece the query is about, which its plan also picks up.
    :param saw: The events its monitor reported, in one tick.
    :param picking_up_over: The seconds of the trial its plan's pick-up ran between.
    :param answer: What the query answered.
    """
    return RecordedTrial(
        episode=Episode(
            scenario_name="shape_sorting",
            execution_type=ExecutionType.SIMULATED,
            world=scene,
        ),
        outcome=TrialOutcome.SUCCEEDED,
        duration=TRIAL_DURATION,
        ticks=[Tick(moment=SOMETHING_HAPPENED_AT, events=list(saw))],
        insertion_attempts=[ran_a_plan_picking_up(piece, picking_up_over)],
        queries=[
            RecordedQuery(
                role_taker=PickedUpRecently(subject=piece),
                answer=answer,
                latency=0.02,
                moment=ASKED_AT,
            )
        ],
    )


@pytest.fixture
def the_robot_picked_it_up(scene: World, piece: Body) -> RecordedTrial:
    """
    The run the answer is yes in: a pick-up of the piece was reported while the plan's
    own pick-up of it was running.
    """
    picked_up = PickUpEvent(
        tracked_object=piece,
        timestamp=TRIAL_BEGAN_AT + timedelta(seconds=SOMETHING_HAPPENED_AT),
    )
    return run_that(
        scene,
        piece,
        [picked_up, moved(piece, SOMETHING_HAPPENED_AT)],
        PICKING_WHILE_IT_HAPPENED,
        "yes",
    )


@pytest.fixture
def a_person_shoved_it(scene: World, piece: Body) -> RecordedTrial:
    """
    The run the answer is no in: the same piece moved, but the robot was still idle --
    its plan does not reach that piece until seconds later -- and no pick-up of it was
    ever reported.
    """
    return run_that(
        scene,
        piece,
        [moved(piece, SOMETHING_HAPPENED_AT)],
        PICKING_LONG_AFTERWARDS,
        "no",
    )


# %% what the card reads off each run


def test_the_card_shows_the_four_levels_in_order() -> None:
    """
    The levels are read one under the other -- what was seen, what was being run, what
    the camera saw, where the object went -- so they are drawn in that order.
    """
    assert EventAgainstThePlanCard().panels == (
        PanelKind.TIMELINE,
        PanelKind.PLAN_TIMELINE,
        PanelKind.CAMERA_BEFORE_AND_AFTER,
        PanelKind.POSE_CHANGE,
    )


def test_a_run_the_robot_acted_in_is_read_by_what_the_robot_did(
    the_robot_picked_it_up: RecordedTrial, piece: Body
) -> None:
    """
    An agency question is about what was done to the object, so where the run saw the
    robot act on it that is what the card is about.
    """
    asked = the_robot_picked_it_up.queries[0].question
    [shown] = EventAgainstThePlanCard().emphasise(asked, the_robot_picked_it_up)
    assert isinstance(shown, PickUpEvent)


def test_a_run_nothing_acted_in_is_read_by_the_object_moving(
    a_person_shoved_it: RecordedTrial,
) -> None:
    """
    Where the run saw nothing done to the object, what is left is the object moving on
    its own -- which is the case the answer is no in, and the one the card has to show
    for that answer to mean anything.
    """
    asked = a_person_shoved_it.queries[0].question
    [shown] = EventAgainstThePlanCard().emphasise(asked, a_person_shoved_it)
    assert isinstance(shown, TranslationEvent)


# %% the agreement the card is drawn to show


def test_the_plan_accounts_for_what_the_robot_itself_did(
    the_robot_picked_it_up: RecordedTrial,
) -> None:
    """
    The pick-up was reported while an item acting on that piece was running, so the plan
    accounts for it and the chart picks that item out.
    """
    asked = the_robot_picked_it_up.queries[0].question
    shown = EventAgainstThePlanCard().emphasise(asked, the_robot_picked_it_up)
    drawn = PlanTimeline().of(the_robot_picked_it_up, emphasise=shown)
    assert [row.accounts_for_the_event for row in drawn.rows] == [True]


def test_nothing_in_the_plan_accounts_for_what_a_person_did(
    a_person_shoved_it: RecordedTrial,
) -> None:
    """
    The piece moved while the robot was handling something else, so no item accounts for
    it -- and a plan chart with nothing picked out is the picture of an answer of no.
    """
    asked = a_person_shoved_it.queries[0].question
    shown = EventAgainstThePlanCard().emphasise(asked, a_person_shoved_it)
    drawn = PlanTimeline().of(a_person_shoved_it, emphasise=shown)
    assert not any(row.accounts_for_the_event for row in drawn.rows)


def test_the_two_runs_disagree_only_about_when(
    the_robot_picked_it_up: RecordedTrial, a_person_shoved_it: RecordedTrial
) -> None:
    """
    Both runs saw the same piece end up somewhere else, and in both the plan picks that
    same piece up; what tells them apart is whether the robot was doing it at the time.
    """
    card = EventAgainstThePlanCard()
    acted = card.emphasise(
        the_robot_picked_it_up.queries[0].question, the_robot_picked_it_up
    )
    shoved = card.emphasise(a_person_shoved_it.queries[0].question, a_person_shoved_it)
    assert RunPlan.of(the_robot_picked_it_up).accounts_for(acted[0]) is not None
    assert RunPlan.of(a_person_shoved_it).accounts_for(shoved[0]) is None


def test_the_plan_of_the_shoved_run_acts_on_that_very_piece(
    a_person_shoved_it: RecordedTrial, piece: Body
) -> None:
    """
    The answer is not no because the robot never touches this piece -- it does, seconds
    later. It is no because the piece moved while the robot was still idle, which is the
    only thing the card has to show.
    """
    [picking_up] = RunPlan.of(a_person_shoved_it).items
    assert picking_up.acts_on(piece)


def test_the_robot_was_running_nothing_when_the_piece_was_shoved(
    a_person_shoved_it: RecordedTrial,
) -> None:
    """
    Idle is the point: at the moment the piece moved, no item of the plan was running at
    all, so the plan chart under that event is empty.
    """
    plan = RunPlan.of(a_person_shoved_it)
    assert not any(
        item.covers(SOMETHING_HAPPENED_AT, plan.just_finished) for item in plan.items
    )


# %% where the event falls in the run


def test_the_camera_is_asked_for_the_moment_the_event_was_reported(
    the_robot_picked_it_up: RecordedTrial,
) -> None:
    """
    The two camera frames are taken either side of what happened rather than either side
    of the query, which was asked well after it.
    """
    asked = the_robot_picked_it_up.queries[0].question
    [shown] = EventAgainstThePlanCard().emphasise(asked, the_robot_picked_it_up)
    assert (
        EventAgainstThePlanCard().reported_at(
            shown, the_robot_picked_it_up, otherwise=ASKED_AT
        )
        == SOMETHING_HAPPENED_AT
    )


# %% the card written out


@needs_a_renderer
def test_both_runs_are_drawn_as_cards(
    the_robot_picked_it_up: RecordedTrial,
    a_person_shoved_it: RecordedTrial,
    tmp_path: Path,
) -> None:
    """
    Both situations the card exists for are drawn from what was recorded of them, without
    either being special-cased.
    """
    for number, trial in enumerate((the_robot_picked_it_up, a_person_shoved_it)):
        [written] = EventAgainstThePlanCard().write(trial, tmp_path / str(number))
        assert written.card is QueryCardName.EVENT_AGAINST_THE_PLAN
        assert all(path.is_file() for path in written.panel_paths.values())


@needs_a_renderer
def test_a_simulated_run_is_drawn_without_the_camera(
    the_robot_picked_it_up: RecordedTrial, tmp_path: Path
) -> None:
    """
    Only a run on the robot records a camera, so a simulated one is drawn with the three
    levels it does have rather than failing on the one it does not.
    """
    [written] = EventAgainstThePlanCard().write(the_robot_picked_it_up, tmp_path)
    assert set(written.panel_paths) == {
        PanelKind.TIMELINE,
        PanelKind.PLAN_TIMELINE,
        PanelKind.POSE_CHANGE,
    }


@needs_a_renderer
def test_the_markup_names_exactly_the_one_stacked_figure(
    a_person_shoved_it: RecordedTrial, tmp_path: Path
) -> None:
    """
    The levels of this card are read against each other, which only holds if the paper is
    given them as one picture -- so its markup names the stacked figure and nothing else.
    """
    [written] = EventAgainstThePlanCard().write(a_person_shoved_it, tmp_path)
    markup = written.markup_path.read_text()
    assert written.layered_path.is_file()
    assert {line.split('"')[1] for line in markup.splitlines() if "image(" in line} == {
        written.layered_path.name
    }


@needs_a_renderer
def test_every_level_is_written_beside_the_stacked_figure(
    a_person_shoved_it: RecordedTrial, tmp_path: Path
) -> None:
    """
    The stacked figure is what the paper includes, but each level is left beside it as
    well, so one of them can be shown on its own without drawing the card again.
    """
    [written] = EventAgainstThePlanCard().write(a_person_shoved_it, tmp_path)
    assert all(path.is_file() for path in written.panel_paths.values())


@needs_a_renderer
def test_a_level_the_run_recorded_nothing_for_keeps_its_place(
    a_person_shoved_it: RecordedTrial, tmp_path: Path
) -> None:
    """
    A simulated run records no camera, so that level has no picture -- and it is still
    stacked in its own place, because a reader shown three levels of four cannot tell
    whether the fourth was left out or never existed.
    """
    card = EventAgainstThePlanCard()

    [written] = card.write(a_person_shoved_it, tmp_path)

    assert PanelKind.CAMERA_BEFORE_AND_AFTER not in written.panel_paths
    assert written.layered_path.is_file()
    stacked = imageio.imread(written.layered_path)
    drawn_alone = LayeredFigure().of(
        [
            Layer(name=panel.level, picture=written.panel_paths[panel])
            for panel in card.panels
            if panel in written.panel_paths
        ]
    )
    assert stacked.shape[0] > drawn_alone.shape[0]


@needs_a_renderer
def test_the_paper_draws_this_card_beside_the_others(
    the_robot_picked_it_up: RecordedTrial, tmp_path: Path
) -> None:
    """
    The card is one of the paper's own, so the set writes it for the same trial that its
    plainer card about the same question is written from.
    """
    written = QueryCardSet.for_the_paper().write(the_robot_picked_it_up, tmp_path)
    assert QueryCardName.EVENT_AGAINST_THE_PLAN in {card.card for card in written}
    assert QueryCardName.PICKED_UP_RECENTLY in {card.card for card in written}
