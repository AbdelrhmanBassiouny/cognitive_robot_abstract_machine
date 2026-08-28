"""
Tell whether Tracy's gripper is actually holding a shape, from the finger joint alone.

The physical Montessori demo has no perception: nothing watches the shape once the
gripper closes on it. But the gripper's own knuckle joint is published on
``/{side}_gripper/joint_states`` (Giskard already subscribes to it), and how far the
fingers managed to close is enough to answer two questions without a camera:

* right after a grasp -- did the fingers stop short on the shape
  (:attr:`GraspVerdict.OBJECT_HELD`), or close all the way to nothing between them
  (:attr:`GraspVerdict.GRIPPER_EMPTY`)?
* while carrying it -- re-commanding the same close every second, do the fingers hold
  station on the shape, or travel further in because it has gone
  (:attr:`GraspVerdict.OBJECT_SLIPPED`)?

:func:`classify_grasp` and :class:`SlipDetector` are the decision logic and take a plain
:class:`GripperClosure`; :class:`GripperJointStateListener` and :class:`LiveGraspGuard`
wire them to ROS.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from rclpy.node import Node
from sensor_msgs.msg import JointState
from typing_extensions import Callable, Optional

from coraplex.datastructures.enums import Arms
from experiments.tracy_experiments.robotiq_gripper import (
    FingerSetpoint,
    RobotiqGripperController,
)
from segmind.datastructures.events import EventWithTrackedObjects

OPEN_KNUCKLE_POSITION = 0.0
"""
Knuckle joint position, in radians, with the gripper fully open.
"""

FULLY_CLOSED_KNUCKLE_POSITION = 0.8
"""
Knuckle joint position, in radians, the fingers reach with nothing between them.

Matches the target
:meth:`~semantic_digital_twin.robots.tracy.TracyLeftGripper.setup_joint_states` gives
:attr:`~semantic_digital_twin.datastructures.definitions.GripperState.CLOSE`.
"""

EMPTY_CLOSE_TOLERANCE = 0.05
"""
How near :data:`FULLY_CLOSED_KNUCKLE_POSITION`, in radians, the knuckle has to settle
after a close for the grasp to count as having closed on nothing.

A starting point to tune against the physical gripper: widen it if a real grasp on the
thinnest piece still reads as empty, narrow it if an empty close reads as a grasp.
"""

SLIP_TRAVEL_TOLERANCE = 0.03
"""
Extra inward knuckle travel, in radians, past where a confirmed grasp settled that
counts as the shape having left the fingers.
"""

RECLOSE_MARGIN = 0.05
"""
How far, in the gripper controller's own command units, past
:attr:`~experiments.tracy_experiments.robotiq_gripper.FingerSetpoint.CLOSED` the slip
watch drives each re-close.

At the plain ``CLOSED`` command the fingers only just pinch a held piece, so a poll
would barely move the knuckle whether or not the piece is still there. Commanding
slightly past it forces measurable inward travel the instant the piece is gone.
"""

RECLOSE_SETPOINT = float(FingerSetpoint.CLOSED) + RECLOSE_MARGIN
"""
Finger setpoint the slip watch re-commands on every poll: the fully-closed command plus
:data:`RECLOSE_MARGIN`.
"""


class GraspVerdict(StrEnum):
    """
    What the finger joint says about whether a shape is between the pads.
    """

    OBJECT_HELD = "object_held"
    """
    The fingers stopped short of closing, i.e. on something.
    """

    GRIPPER_EMPTY = "gripper_empty"
    """
    The fingers closed all the way: the grasp missed the shape.
    """

    OBJECT_SLIPPED = "object_slipped"
    """
    The fingers were holding a shape and have since closed further: it is gone.
    """


@dataclass(unsafe_hash=True)
class GripperSlipEvent(EventWithTrackedObjects):
    """
    A carried shape has left the gripper: a re-close drove the fingers past where the
    grasp first settled (:attr:`GraspVerdict.OBJECT_SLIPPED`).

    Distinct from :class:`~segmind.datastructures.events.LossOfGraspEvent`, which is
    read from the contact model rather than the knuckle joint.
    """


class NoGripperJointStateError(RuntimeError):
    """
    Raised when a gripper's knuckle position is asked for before any joint state for it
    has arrived.
    """

    def __init__(self, arm: Arms):
        super().__init__(f"No gripper joint state received yet for {arm}.")
        self.arm = arm
        """
        The arm whose gripper joint state was missing.
        """


@dataclass(frozen=True)
class GripperClosure:
    """
    One reading of how far a gripper's fingers have closed.
    """

    knuckle_position: float
    """
    Measured knuckle joint position, in radians.
    """

    fully_closed_position: float = FULLY_CLOSED_KNUCKLE_POSITION
    """
    See :data:`FULLY_CLOSED_KNUCKLE_POSITION`.
    """

    open_position: float = OPEN_KNUCKLE_POSITION
    """
    See :data:`OPEN_KNUCKLE_POSITION`.
    """

    @property
    def fraction_closed(self) -> float:
        """
        How far shut the fingers are, ``0`` fully open, ``1`` fully closed.
        """
        span = self.fully_closed_position - self.open_position
        return (self.knuckle_position - self.open_position) / span

    def closed_on_nothing(self, tolerance: float = EMPTY_CLOSE_TOLERANCE) -> bool:
        """
        Whether the fingers have settled within ``tolerance`` of fully closed.

        :param tolerance: See :data:`EMPTY_CLOSE_TOLERANCE`.
        """
        return self.fully_closed_position - self.knuckle_position <= tolerance


def classify_grasp(
    closure: GripperClosure, empty_close_tolerance: float = EMPTY_CLOSE_TOLERANCE
) -> GraspVerdict:
    """
    Read a just-settled close as either a hold or a miss.

    :param closure: The knuckle reading taken once the close has settled.
    :param empty_close_tolerance: See :data:`EMPTY_CLOSE_TOLERANCE`.
    :return: :attr:`GraspVerdict.GRIPPER_EMPTY` if the fingers reached fully closed,
        :attr:`GraspVerdict.OBJECT_HELD` otherwise.
    """
    if closure.closed_on_nothing(empty_close_tolerance):
        return GraspVerdict.GRIPPER_EMPTY
    return GraspVerdict.OBJECT_HELD


@dataclass
class SlipDetector:
    """
    Compares each fresh close against where a confirmed grasp first settled, to catch a
    shape that has since slipped out.
    """

    held_position: float
    """
    Knuckle position, in radians, when the grasp was confirmed.
    """

    slip_travel_tolerance: float = SLIP_TRAVEL_TOLERANCE
    """
    See :data:`SLIP_TRAVEL_TOLERANCE`.
    """

    empty_close_tolerance: float = EMPTY_CLOSE_TOLERANCE
    """
    See :data:`EMPTY_CLOSE_TOLERANCE`.
    """

    fully_closed_position: float = FULLY_CLOSED_KNUCKLE_POSITION
    """
    See :data:`FULLY_CLOSED_KNUCKLE_POSITION`.
    """

    def check(self, closure: GripperClosure) -> GraspVerdict:
        """
        Classify one fresh close taken while carrying the shape.

        :param closure: The knuckle reading after re-commanding the close.
        :return: :attr:`GraspVerdict.OBJECT_SLIPPED` if the fingers have closed past
            where the grasp settled or all the way, :attr:`GraspVerdict.OBJECT_HELD`
            otherwise.
        """
        if closure.closed_on_nothing(self.empty_close_tolerance):
            return GraspVerdict.OBJECT_SLIPPED
        if closure.knuckle_position - self.held_position >= self.slip_travel_tolerance:
            return GraspVerdict.OBJECT_SLIPPED
        return GraspVerdict.OBJECT_HELD


@dataclass
class GraspConfirmation:
    """
    The outcome of reading the fingers right after a grasp.
    """

    verdict: GraspVerdict
    """
    :attr:`GraspVerdict.OBJECT_HELD` or :attr:`GraspVerdict.GRIPPER_EMPTY`.
    """

    slip_detector: Optional[SlipDetector]
    """
    A detector seeded with where the grasp settled, or ``None`` if the grasp missed.
    """


def confirm_grasp(
    closure: GripperClosure, empty_close_tolerance: float = EMPTY_CLOSE_TOLERANCE
) -> GraspConfirmation:
    """
    Classify a settled close and, if it held, seed a :class:`SlipDetector` from it.

    :param closure: The knuckle reading once the grasp's close has settled.
    :param empty_close_tolerance: See :data:`EMPTY_CLOSE_TOLERANCE`.
    """
    verdict = classify_grasp(closure, empty_close_tolerance)
    slip_detector = (
        SlipDetector(
            held_position=closure.knuckle_position,
            empty_close_tolerance=empty_close_tolerance,
        )
        if verdict is GraspVerdict.OBJECT_HELD
        else None
    )
    return GraspConfirmation(verdict=verdict, slip_detector=slip_detector)


_KNUCKLE_JOINT_TEMPLATE = "{side}_robotiq_85_left_knuckle_joint"
"""
Name of the knuckle joint whose position :class:`GripperJointStateListener` reads,
parameterised by body side.
"""

_GRIPPER_JOINT_STATE_TOPIC_TEMPLATE = "/{side}_gripper/joint_states"
"""
Topic the Robotiq driver publishes each gripper's joint state on, parameterised by body
side.
"""

_ARM_SIDES = {Arms.LEFT: "left", Arms.RIGHT: "right"}
"""
Body-side token for each single-arm :class:`~coraplex.datastructures.enums.Arms` member.
"""


@dataclass
class GripperJointStateListener:
    """
    Keeps the latest :class:`GripperClosure` for one arm from its gripper joint-state
    topic.

    ..note:: The node must be spun by an executor for readings to arrive.
    """

    node: Node
    """
    ROS node the subscription is created on.
    """

    arm: Arms
    """
    Which arm's gripper to listen to; must be :attr:`Arms.LEFT` or :attr:`Arms.RIGHT`.
    """

    _knuckle_joint_name: str = field(init=False)
    """
    Name of the knuckle joint read out of each joint-state message.
    """

    _latest_closure: Optional[GripperClosure] = field(init=False, default=None)
    """
    The most recent reading, or ``None`` until the first message arrives.
    """

    def __post_init__(self) -> None:
        side = _ARM_SIDES[self.arm]
        self._knuckle_joint_name = _KNUCKLE_JOINT_TEMPLATE.format(side=side)
        self.node.create_subscription(
            JointState,
            _GRIPPER_JOINT_STATE_TOPIC_TEMPLATE.format(side=side),
            self._on_joint_state,
            10,
        )

    def _on_joint_state(self, message: JointState) -> None:
        if self._knuckle_joint_name not in message.name:
            return
        index = message.name.index(self._knuckle_joint_name)
        self._latest_closure = GripperClosure(
            knuckle_position=abs(message.position[index])
        )

    @property
    def has_reading(self) -> bool:
        """
        Whether at least one gripper joint state has arrived.
        """
        return self._latest_closure is not None

    @property
    def latest_closure(self) -> GripperClosure:
        """
        The most recent reading.

        :raises NoGripperJointStateError: If no joint state has arrived yet.
        """
        if self._latest_closure is None:
            raise NoGripperJointStateError(self.arm)
        return self._latest_closure


@dataclass
class LiveGraspGuard:
    """
    Re-commands the grasp close on a fixed period and reports whether the shape is still
    there each time.
    """

    controller: RobotiqGripperController
    """
    Drives the re-close.
    """

    listener: GripperJointStateListener
    """
    Reads the knuckle back after each re-close.
    """

    arm: Arms
    """
    Which arm's gripper is guarded.
    """

    slip_detector: SlipDetector
    """
    Seeded from the confirmed grasp; classifies each re-close.
    """

    period: float = 1.0
    """
    Seconds between re-closes.
    """

    reclose_setpoint: float = RECLOSE_SETPOINT
    """
    See :data:`RECLOSE_SETPOINT`.
    """

    def poll(self) -> GraspVerdict:
        """
        Re-command the close and classify the resulting knuckle position once.
        """
        self.controller.close_to(self.arm, self.reclose_setpoint)
        return self.slip_detector.check(self.listener.latest_closure)

    def watch(
        self,
        should_continue: Callable[[], bool],
        on_verdict: Callable[[GraspVerdict], None],
    ) -> None:
        """
        Poll every :attr:`period` seconds until ``should_continue`` returns ``False``.

        :param should_continue: Checked before each poll; the loop ends when it is
            ``False``.
        :param on_verdict: Called with every poll's verdict.
        """
        while should_continue():
            on_verdict(self.poll())
            time.sleep(self.period)
