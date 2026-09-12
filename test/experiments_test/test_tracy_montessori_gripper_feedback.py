"""
Tests for :mod:`experiments.tracy_experiments.montessori.gripper_feedback`: reading a
grasp as held or empty, and reading a live re-close as still-held or slipped, from the
knuckle joint position alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from coraplex.datastructures.enums import Arms
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    RECLOSE_SETPOINT,
    GraspVerdict,
    GripperClosure,
    GripperSlipEvent,
    LiveGraspGuard,
    SlipDetector,
    classify_grasp,
    confirm_grasp,
)
from segmind.datastructures.events import DetectionEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body

# %% closure geometry


def test_fraction_closed_spans_open_to_fully_closed():
    assert GripperClosure(knuckle_position=0.0).fraction_closed == 0.0
    assert (
        GripperClosure(knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION).fraction_closed
        == 1.0
    )
    assert (
        GripperClosure(
            knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION / 2
        ).fraction_closed
        == 0.5
    )


# %% grasp vs miss


def test_fingers_stopping_short_read_as_a_held_object():
    closure = GripperClosure(knuckle_position=0.45)

    assert classify_grasp(closure) is GraspVerdict.OBJECT_HELD


def test_fingers_reaching_fully_closed_read_as_an_empty_gripper():
    closure = GripperClosure(knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION - 0.01)

    assert classify_grasp(closure) is GraspVerdict.GRIPPER_EMPTY


def test_confirm_grasp_seeds_a_slip_detector_only_when_something_is_held():
    held = confirm_grasp(GripperClosure(knuckle_position=0.45))
    empty = confirm_grasp(
        GripperClosure(knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION)
    )

    assert held.verdict is GraspVerdict.OBJECT_HELD
    assert held.slip_detector is not None
    assert held.slip_detector.held_position == 0.45
    assert empty.verdict is GraspVerdict.GRIPPER_EMPTY
    assert empty.slip_detector is None


# %% slip while carrying


def test_a_re_close_that_holds_station_reads_as_still_held():
    detector = SlipDetector(held_position=0.45)

    verdict = detector.check(GripperClosure(knuckle_position=0.46))

    assert verdict is GraspVerdict.OBJECT_HELD


def test_a_re_close_that_travels_well_past_the_grasp_reads_as_slipped():
    detector = SlipDetector(held_position=0.45, slip_travel_tolerance=0.03)

    verdict = detector.check(GripperClosure(knuckle_position=0.5))

    assert verdict is GraspVerdict.OBJECT_SLIPPED


def test_a_re_close_that_reaches_fully_closed_reads_as_slipped():
    detector = SlipDetector(held_position=0.7)

    verdict = detector.check(
        GripperClosure(knuckle_position=FULLY_CLOSED_KNUCKLE_POSITION)
    )

    assert verdict is GraspVerdict.OBJECT_SLIPPED


# %% live re-close


@dataclass
class ReCloseCommand:
    """
    One re-close the guard sent to the gripper controller.
    """

    arm: Arms
    """
    Arm the re-close addressed.
    """

    setpoint: float
    """
    Finger setpoint commanded.
    """


@dataclass
class RecordingGripperController:
    """
    Records each re-close command instead of driving the real action server.
    """

    commands: list[ReCloseCommand] = field(default_factory=list)
    """
    Every :meth:`close_to` call, in order.
    """

    def close_to(self, arm: Arms, setpoint: float) -> None:
        self.commands.append(ReCloseCommand(arm=arm, setpoint=setpoint))


@dataclass
class FixedClosureListener:
    """
    Serves one fixed knuckle reading back after a re-close.
    """

    latest_closure: GripperClosure
    """
    The reading returned on every access.
    """


def _guard(
    listener: FixedClosureListener,
) -> tuple[LiveGraspGuard, RecordingGripperController]:
    controller = RecordingGripperController()
    guard = LiveGraspGuard(
        controller=controller,
        listener=listener,
        arm=Arms.LEFT,
        slip_detector=SlipDetector(held_position=0.45),
    )
    return guard, controller


def test_poll_re_closes_past_fully_closed():
    guard, controller = _guard(
        FixedClosureListener(GripperClosure(knuckle_position=0.45))
    )

    guard.poll()

    assert controller.commands == [
        ReCloseCommand(arm=Arms.LEFT, setpoint=RECLOSE_SETPOINT)
    ]


def test_poll_returns_held_when_the_fingers_hold_station():
    guard, _ = _guard(FixedClosureListener(GripperClosure(knuckle_position=0.45)))

    assert guard.poll() is GraspVerdict.OBJECT_HELD


def test_poll_returns_slipped_when_the_fingers_travel_past_the_grasp():
    guard, _ = _guard(FixedClosureListener(GripperClosure(knuckle_position=0.5)))

    assert guard.poll() is GraspVerdict.OBJECT_SLIPPED


# %% slip event


def test_gripper_slip_event_is_a_detection_event_for_the_carried_body():
    body = Body(name=PrefixedName("cube"))

    event = GripperSlipEvent(tracked_object=body)

    assert isinstance(event, DetectionEvent)
    assert event.tracked_object is body
    assert event.with_object is None
    assert event.timestamp.isoformat()
