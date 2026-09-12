"""
Tests for :mod:`experiments.tracy_experiments.pickup.pickup_demo_real`: a perceived
piece is grasped with the target lifted back to where the pick aimed before the spawn
was lowered, and while a piece is carried the gripper is re-closed and watched for the
piece slipping out.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import pytest
from coraplex.datastructures.enums import Arms
from segmind.datastructures.events import PickUpEvent

from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.scenarios.trial import TrialOutcome
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    RECLOSE_MARGIN,
    RECLOSE_SETPOINT,
    GripperClosure,
    GripperSlipEvent,
)
from experiments.tracy_experiments.montessori.grasp_widths import (
    RECTANGULAR_PRISM_CLOSE_SETPOINT,
)
from experiments.tracy_experiments.pickup.pickup_demo_real import (
    GRASP_HEIGHT_OFFSET,
    POST_LIFT_SETTLE_SECONDS,
    PieceNotSeenError,
    _grasp_target_pose,
    _SortingRig,
    outcome_of,
    piece_asked_about,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body

# %% the grasp offset


def test_grasp_target_pose_sits_the_offset_above_the_body_origin():
    body = Body(name=PrefixedName("shape"))

    pose = _grasp_target_pose(body, GRASP_HEIGHT_OFFSET)

    translation = pose.to_homogeneous_matrix()[:3, 3]
    assert [float(component) for component in translation] == [
        0.0,
        0.0,
        GRASP_HEIGHT_OFFSET,
    ]
    assert pose.reference_frame is body


# %% slip watch while carrying


@dataclass
class RecordingGripper:
    """
    Records every re-close instead of driving the real action server.
    """

    close_to_setpoints: list[float] = field(default_factory=list)
    """
    Setpoint of every :meth:`close_to` call, in order.
    """

    def close_to(self, arm: Arms, setpoint: float) -> None:
        self.close_to_setpoints.append(setpoint)


@dataclass
class SequencedClosureListener:
    """
    Serves a fixed sequence of knuckle readings, holding the last one.
    """

    readings: list[GripperClosure]
    """
    Readings handed out on successive accesses.
    """

    _next: int = 0
    """
    Index of the next reading to serve.
    """

    @property
    def latest_closure(self) -> GripperClosure:
        reading = self.readings[min(self._next, len(self.readings) - 1)]
        self._next += 1
        return reading


@dataclass
class PublishedEvent:
    """
    One event handed to the dashboard feed.
    """

    shape_name: str
    """
    Name the event was published under.
    """

    event: object
    """
    The event object.
    """


@dataclass
class RecordingFeed:
    """
    Records what the slip watch streams to the dashboard.
    """

    published: list[PublishedEvent] = field(default_factory=list)
    """
    Every :meth:`publish` call, in order.
    """

    def publish(self, shape_name: str, event: object) -> None:
        self.published.append(PublishedEvent(shape_name=shape_name, event=event))


def _slip_watch_rig(
    gripper: RecordingGripper,
    listener: SequencedClosureListener,
    feed: RecordingFeed | None = None,
) -> _SortingRig:
    """
    A rig with only the fields :meth:`_SortingRig._carry_watching_for_slip` reads.
    """
    return _SortingRig(
        context=None,
        world=None,
        robot=None,
        feed=feed,
        gripper=gripper,
        gripper_listener=listener,
        grasp_description=None,
        tool_frame=None,
        slip_watch_interval=0.01,
        post_lift_settle=0.0,
    )


def _held(*extra: float) -> SequencedClosureListener:
    """
    A listener whose grasp confirms as held, then serves ``extra`` poll readings.
    """
    return SequencedClosureListener(
        [GripperClosure(knuckle_position=position) for position in (0.45, *extra)]
    )


def _no_slip_watch_thread_left_running() -> bool:
    return not any(
        thread.name.startswith("slip-watch") and thread.is_alive()
        for thread in threading.enumerate()
    )


def _wait_until(predicate) -> None:
    deadline = time.monotonic() + 2.0
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.005)


def test_a_missed_grasp_skips_the_slip_watch_but_still_carries():
    gripper = RecordingGripper()
    listener = SequencedClosureListener(
        [GripperClosure(knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION)]
    )
    rig = _slip_watch_rig(gripper, listener)
    carried: list[bool] = []

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("cube")), 0.5, lambda: carried.append(True)
    )

    assert carried == [True]
    assert gripper.close_to_setpoints == [0.5]
    assert _no_slip_watch_thread_left_running()


def test_a_held_grasp_re_closes_past_fully_closed_while_the_shape_is_carried():
    gripper = RecordingGripper()
    rig = _slip_watch_rig(gripper, _held())

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("cube")),
        0.5,
        lambda: _wait_until(lambda: len(gripper.close_to_setpoints) > 1),
    )

    assert gripper.close_to_setpoints[0] == 0.5
    assert RECLOSE_SETPOINT in gripper.close_to_setpoints[1:]
    assert _no_slip_watch_thread_left_running()


def test_the_slip_watch_re_closes_past_a_shapes_own_firmer_close_setpoint():
    """
    A shape closed to more than ``FingerSetpoint.CLOSED`` must be re-closed past *its*
    setpoint, not past ``CLOSED``.

    The rectangular prism grasps at ``0.6``. Re-commanding the ``CLOSED``-derived
    ``0.55`` would ease the fingers open on every poll and drop the piece.
    """
    gripper = RecordingGripper()
    rig = _slip_watch_rig(gripper, _held())

    rig._carry_watching_for_slip(
        Body(name=PrefixedName("rectangular_prism")),
        RECTANGULAR_PRISM_CLOSE_SETPOINT,
        lambda: _wait_until(lambda: len(gripper.close_to_setpoints) > 1),
    )

    assert gripper.close_to_setpoints[0] == RECTANGULAR_PRISM_CLOSE_SETPOINT
    re_closes = gripper.close_to_setpoints[1:]
    assert re_closes
    assert all(
        setpoint == RECTANGULAR_PRISM_CLOSE_SETPOINT + RECLOSE_MARGIN
        for setpoint in re_closes
    )
    assert all(setpoint > RECTANGULAR_PRISM_CLOSE_SETPOINT for setpoint in re_closes)
    assert _no_slip_watch_thread_left_running()


def test_the_grasp_is_left_to_settle_after_the_lift_before_it_is_read():
    """
    The knuckle is still moving as the fingers take up the lifted shape's weight, so the
    reading that seeds the slip detector must wait :attr:`_SortingRig.post_lift_settle`.
    """
    gripper = RecordingGripper()
    rig = _slip_watch_rig(gripper, _held())
    rig.post_lift_settle = 0.2

    started = time.monotonic()
    rig._carry_watching_for_slip(Body(name=PrefixedName("cube")), 0.5, lambda: None)

    assert time.monotonic() - started >= 0.2
    assert gripper.close_to_setpoints[0] == 0.5
    assert _no_slip_watch_thread_left_running()


def test_the_post_lift_settle_defaults_to_five_seconds():
    assert POST_LIFT_SETTLE_SECONDS == 5.0


def test_a_slip_streams_a_gripper_slip_event_to_the_feed():
    gripper = RecordingGripper()
    feed = RecordingFeed()
    rig = _slip_watch_rig(gripper, _held(0.5), feed)
    body = Body(name=PrefixedName("cube"))

    rig._carry_watching_for_slip(
        body, 0.5, lambda: _wait_until(lambda: bool(feed.published))
    )

    assert feed.published
    assert all(entry.shape_name == "cube" for entry in feed.published)
    first_event = feed.published[0].event
    assert isinstance(first_event, GripperSlipEvent)
    assert first_event.tracked_object is body
    assert _no_slip_watch_thread_left_running()


# %% what the run records of itself


def test_an_event_a_monitor_reports_reaches_the_dashboard_and_the_episode():
    """
    An event goes to the live dashboard as before, and is kept as a tick of the trial
    the run records, stamped with the moment it arrived.
    """
    feed = RecordingFeed()
    rig = _slip_watch_rig(RecordingGripper(), _held(), feed)
    piece = Body(name=PrefixedName("shape"))
    picked_up = PickUpEvent(tracked_object=piece)

    rig.note_event(piece.name.name, picked_up)

    assert [published.event for published in feed.published] == [picked_up]
    [tick] = rig.observer.ticks
    assert tick.events == [picked_up]
    assert 0.0 <= tick.moment <= rig.observer.elapsed_seconds


def test_a_plan_the_rig_performed_is_kept_for_the_episode():
    rig = _slip_watch_rig(RecordingGripper(), _held())
    plan = PerformedNothing()

    rig.perform_and_record(plan)

    assert plan.performed
    assert [performed.plan for performed in rig.observer.plans] == [plan]


@dataclass
class PerformedNothing:
    """
    Stands in for a plan, remembering that it was performed.
    """

    performed: bool = False
    """
    Whether :meth:`perform` was called.
    """

    def perform(self) -> None:
        self.performed = True


def test_the_run_succeeded_when_its_monitors_saw_the_asked_piece_picked_up():
    piece = Body(name=PrefixedName("shape"))
    another = Body(name=PrefixedName("another"))

    assert outcome_of([PickUpEvent(tracked_object=piece)], piece) is (
        TrialOutcome.SUCCEEDED
    )
    assert outcome_of([PickUpEvent(tracked_object=another)], piece) is (
        TrialOutcome.FAILED
    )


def test_asking_about_a_piece_the_look_did_not_find_says_so():
    with pytest.raises(PieceNotSeenError) as raised:
        piece_asked_about(LookedAndFound(pieces=[]), MontessoriShapeCategory.CUBE)
    assert raised.value.category is MontessoriShapeCategory.CUBE


@dataclass
class LookedAndFound:
    """
    Stands in for a run that has looked, holding the pieces the look found.
    """

    pieces: list
    """
    The pieces, as the world holds them.
    """
