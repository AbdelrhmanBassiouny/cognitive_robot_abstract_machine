"""
The plan a trial recorded, read back as the items it ran and when each of them ran.

What the plan chart is drawn from and what the question "did the robot do this?" is
settled against: an event the plan accounts for is one the robot brought about, and an
event no item of the plan accounts for is one something else did.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from coraplex.datastructures.enums import ExecutionType
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import ActionNode, PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.mixins import ManipulatesBodies
from giskardpy.motion_statechart.data_types import LifeCycleValues
from segmind.datastructures.events import PickUpEvent, TranslationEvent
from typing_extensions import List, Optional

from experiments.episodes.episode import (
    Episode,
    InsertionAttempt,
    InsertionOutcome,
    RecordedTrial,
)
from experiments.paper.run_plan import (
    JUST_FINISHED,
    RunPlan,
    TrialClock,
    TrialRanNoPlanError,
)
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body

# %% the run these plans were recorded in

TRIAL_BEGAN_AT = datetime(2026, 1, 1, 12, 0, 0)
"""
The instant the recorded trial's first plan item started, which is where its own clock
starts from.
"""

TRIAL_DURATION = 12.0
"""
How long the recorded trial ran, in seconds.
"""

PICKING_STARTED_AT = 1.0
"""
Seconds into the trial the pick-up item of the plan started.
"""

PICKING_ENDED_AT = 4.0
"""
Seconds into the trial the pick-up item of the plan finished.
"""

CARRYING_STARTED_AT = 5.0
"""
Seconds into the trial the carrying item of the plan started, which never finished.
"""

# %% the actions these plans are built from


@dataclass
class ActsOnOneBody(ActionDescription, ManipulatesBodies):
    """
    An action that acts on a single named body, which is what an event about that body
    can be accounted for by.
    """

    subject: Optional[Body] = None
    """
    The body it acts on.
    """

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The one body this action acts on.
        """
        return [self.subject]

    def execute(self) -> None:
        """
        Never run: these plans are read back from a record rather than performed.
        """


@dataclass
class MovesOnlyTheRobot(ActionDescription):
    """
    An action that acts on no body of the scene, so nothing that happened to an object
    is accounted for by it.
    """

    def execute(self) -> None:
        """
        Never run: these plans are read back from a record rather than performed.
        """


# %% the scene the recorded run acted on


@pytest.fixture
def cube() -> Body:
    """
    The piece the robot picked up.
    """
    return Body(name=PrefixedName("cube"))


@pytest.fixture
def cylinder() -> Body:
    """
    The piece nothing in the plan ever names.
    """
    return Body(name=PrefixedName("cylinder"))


def item_ran(
    action: ActionDescription,
    start: float,
    end: Optional[float],
    status: LifeCycleValues,
) -> ActionNode:
    """
    One item of a recorded plan, having run over the given stretch of its trial.

    :param action: What the item did.
    :param start: Seconds into the trial it started.
    :param end: Seconds into the trial it finished, or None if it never did.
    :param status: Where the item was left when the trial ended.
    """
    node = ActionNode(designator=action)
    node.start_time = TRIAL_BEGAN_AT + timedelta(seconds=start)
    node.end_time = None if end is None else TRIAL_BEGAN_AT + timedelta(seconds=end)
    node.status = status
    return node


@pytest.fixture
def trial(cube: Body) -> RecordedTrial:
    """
    A trial that ran a plan of two items: a pick-up of the cube that finished, and a
    carry that was still running when the trial ended.
    """
    plan = Plan()
    root = PlanNode()
    root.start_time = TRIAL_BEGAN_AT
    plan.add_node(root)
    for node in (
        item_ran(
            ActsOnOneBody(subject=cube),
            PICKING_STARTED_AT,
            PICKING_ENDED_AT,
            LifeCycleValues.SUCCEEDED,
        ),
        item_ran(
            MovesOnlyTheRobot(), CARRYING_STARTED_AT, None, LifeCycleValues.RUNNING
        ),
    ):
        plan.add_node(node)
        root.add_child(node)
    return RecordedTrial(
        episode=Episode(
            scenario_name="shape_sorting", execution_type=ExecutionType.SIMULATED
        ),
        outcome=TrialOutcome.SUCCEEDED,
        duration=TRIAL_DURATION,
        insertion_attempts=[
            InsertionAttempt(
                shape_name="cube", plan=plan, outcome=InsertionOutcome.FELL_THROUGH
            )
        ],
    )


# %% the clock the plan and the events share


def test_the_clock_starts_where_the_first_thing_the_trial_recorded_happened(
    trial: RecordedTrial,
) -> None:
    """
    A plan is recorded against the wall clock and a tick against the seconds of its
    trial, so the two are only read against each other once the trial says where its own
    seconds start.
    """
    assert TrialClock.of(trial).origin == TRIAL_BEGAN_AT


def test_the_clock_turns_an_instant_into_seconds_into_the_trial(
    trial: RecordedTrial,
) -> None:
    """
    An instant of the wall clock is placed in the trial by how long after its start it
    happened.
    """
    clock = TrialClock.of(trial)
    assert (
        clock.seconds_of(TRIAL_BEGAN_AT + timedelta(seconds=PICKING_ENDED_AT))
        == PICKING_ENDED_AT
    )


def test_a_trial_that_recorded_no_plan_says_so(trial: RecordedTrial) -> None:
    """
    Without a plan there is no clock to place anything on, which is a state to report
    rather than a zero to carry on from.
    """
    trial.insertion_attempts = []
    with pytest.raises(TrialRanNoPlanError):
        TrialClock.of(trial)


# %% the items the plan ran


def test_the_plan_holds_one_item_per_action_it_ran(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    A plan's nodes include the bare ones holding it together; what the robot did is the
    actions among them.
    """
    assert [item.label for item in RunPlan.of(trial).items] == [
        "%s (%s)" % (ActsOnOneBody.__name__, cube.name.name),
        MovesOnlyTheRobot.__name__,
    ]


def test_an_item_runs_over_the_stretch_of_the_trial_it_ran_in(
    trial: RecordedTrial,
) -> None:
    """
    An item that started and finished covers exactly the seconds between the two.
    """
    [picking, _] = RunPlan.of(trial).items
    assert (picking.start, picking.duration) == (
        PICKING_STARTED_AT,
        PICKING_ENDED_AT - PICKING_STARTED_AT,
    )


def test_an_item_that_never_finished_runs_to_the_end_of_the_trial(
    trial: RecordedTrial,
) -> None:
    """
    An item the trial ended in the middle of was still running when it ended, so it is
    drawn as running that far and no further.
    """
    [_, carrying] = RunPlan.of(trial).items
    assert (carrying.start, carrying.duration) == (
        CARRYING_STARTED_AT,
        TRIAL_DURATION - CARRYING_STARTED_AT,
    )


def test_an_item_keeps_the_state_it_was_left_in(trial: RecordedTrial) -> None:
    """
    Whether an item succeeded is what the chart colours it by, so the item carries the
    state the run left it in rather than the chart guessing at it.
    """
    [picking, carrying] = RunPlan.of(trial).items
    assert (picking.status, carrying.status) == (
        LifeCycleValues.SUCCEEDED,
        LifeCycleValues.RUNNING,
    )


# %% what the plan accounts for


def event_at(event_type, subject: Body, moment: float):
    """
    One event of the given kind, seen at the given second of the trial.

    :param event_type: The kind of event that was seen.
    :param subject: The object it is about.
    :param moment: Seconds into the trial it happened at.
    """
    return event_type(
        tracked_object=subject,
        timestamp=TRIAL_BEGAN_AT + timedelta(seconds=moment),
    )


def test_an_event_is_placed_in_the_trial_by_when_it_happened(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    An event carries the instant it happened at, which the trial's own clock turns into
    a moment of the run the charts can be drawn against.
    """
    picked_up = event_at(PickUpEvent, cube, PICKING_ENDED_AT)
    assert RunPlan.of(trial).moment_of(picked_up) == PICKING_ENDED_AT


def test_the_item_acting_on_the_object_accounts_for_what_happened_to_it(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    An event about an object, seen while the robot was running an item that acts on that
    object, is one the robot brought about.
    """
    plan = RunPlan.of(trial)
    picked_up = event_at(PickUpEvent, cube, PICKING_STARTED_AT + 1.0)
    assert plan.accounts_for(picked_up) is plan.items[0]


def test_an_item_that_has_just_finished_still_accounts_for_what_happened(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    A pick-up is reported once the object is already up, which is a moment after the
    item that lifted it has finished.
    """
    plan = RunPlan.of(trial)
    picked_up = event_at(PickUpEvent, cube, PICKING_ENDED_AT + JUST_FINISHED / 2.0)
    assert plan.accounts_for(picked_up) is plan.items[0]


def test_the_object_is_matched_by_name_rather_than_by_identity(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    A recalled episode reads its plan and its events back as separate objects, so the
    two name the same piece rather than being the same piece.
    """
    plan = RunPlan.of(trial)
    read_back = Body(name=PrefixedName(cube.name.name))
    picked_up = event_at(PickUpEvent, read_back, PICKING_STARTED_AT + 1.0)
    assert plan.accounts_for(picked_up) is plan.items[0]


def test_nothing_accounts_for_an_object_moving_that_no_item_ever_touched(
    trial: RecordedTrial, cylinder: Body
) -> None:
    """
    The object a person pushed is one no item of the plan names, so the plan accounts
    for its moving at no moment of the run at all -- which is what makes the answer no.
    """
    shoved = event_at(TranslationEvent, cylinder, PICKING_STARTED_AT + 1.0)
    assert RunPlan.of(trial).accounts_for(shoved) is None


def test_nothing_accounts_for_what_happened_while_no_item_was_running(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    An object moving long after the item that acted on it had finished is not that
    item's doing.
    """
    shoved = event_at(TranslationEvent, cube, PICKING_ENDED_AT + JUST_FINISHED * 2.0)
    assert RunPlan.of(trial).accounts_for(shoved) is None
