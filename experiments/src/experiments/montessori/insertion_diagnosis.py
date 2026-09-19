"""
Working out why one insertion attempt did not put its shape in the box.

The plan's own failure answers this whenever it names a cause. It often does not: a
solver or collision error leaves no reason on any plan node at all, and
:class:`~coraplex.plans.failures.AllChildrenFailed` swallows the reasons of the children
that failed. The segmind events detected while the attempt ran cover those cases -- what
was seen to happen is evidence even when nothing was recorded about why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from coraplex.plans.failures import AllChildrenFailed, EmptyUnderspecified, PlanFailure
from segmind.datastructures.events import (
    DetectionEvent,
    InsertionEvent,
    LossOfContactEvent,
    PickUpEvent,
)
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List, Optional, Tuple, Type

UNINFORMATIVE_PLAN_FAILURES: Tuple[Type[PlanFailure], ...] = (
    AllChildrenFailed,
    EmptyUnderspecified,
)
"""
Plan failures that report only that something failed, never what.

Both aggregate over candidates or children and discard each one's own reason, so the
detected events are the only remaining evidence.
"""


class InsertionFailureReason(StrEnum):
    """
    Why a shape is not in the box.
    """

    PLAN_FAILED = "plan_failed"
    """
    The plan itself failed and named what went wrong.
    """

    NOT_PICKED_UP = "not_picked_up"
    """
    The shape was never picked up, so nothing was ever carried to the hole.
    """

    DROPPED_BEFORE_INSERTION = "dropped_before_insertion"
    """
    The shape left the gripper while it was still being carried.
    """

    RELEASED_OFF_TARGET = "released_off_target"
    """
    The shape was carried and let go, but never entered its hole.
    """

    WEDGED_IN_HOLE = "wedged_in_hole"
    """
    The shape entered its hole but did not pass through it.
    """

    UNDIAGNOSED = "undiagnosed"
    """
    Nothing was observed and nothing was reported.
    """


@dataclass
class InsertionEvidence:
    """
    Everything one attempt left behind to be judged on.
    """

    events: List[DetectionEvent]
    """
    Segmind events detected while the attempt ran.
    """

    gripper_bodies: List[Body] = field(default_factory=list)
    """
    Bodies of the robot that hold the shape, so releasing it can be recognized.
    """

    raised_exception: Optional[BaseException] = None
    """
    The exception the attempt raised, if it raised one.
    """

    insertion_phase_started_at: Optional[datetime] = None
    """
    When the attempt stopped carrying the shape and began lowering it into its hole.

    Letting go before this is a drop; letting go after it is the intended release. When
    unknown, every release after the pick-up counts as a drop rather than being excused.
    """

    def picked_up_at(self) -> Optional[datetime]:
        """
        When the shape was first detected being picked up, or None if it never was.
        """
        pick_ups = [event for event in self.events if isinstance(event, PickUpEvent)]
        return min((event.timestamp for event in pick_ups), default=None)

    def was_detected_inserted(self) -> bool:
        """
        Whether the shape was detected entering its hole.
        """
        return any(isinstance(event, InsertionEvent) for event in self.events)

    def dropped_at(self) -> Optional[datetime]:
        """
        When the shape was detected leaving the gripper mid-transport, if it was.
        """
        picked_up_at = self.picked_up_at()
        if picked_up_at is None:
            return None
        releases = [
            event.timestamp
            for event in self.events
            if isinstance(event, LossOfContactEvent)
            and event.with_object in self.gripper_bodies
            and event.timestamp > picked_up_at
            and (
                self.insertion_phase_started_at is None
                or event.timestamp < self.insertion_phase_started_at
            )
        ]
        return min(releases, default=None)

    def released_body_names(self) -> List[str]:
        """
        Names of the gripper bodies the shape was detected leaving.
        """
        return [
            str(event.with_object.name)
            for event in self.events
            if isinstance(event, LossOfContactEvent)
            and event.with_object in self.gripper_bodies
        ]

    def named_exception(self) -> Optional[str]:
        """
        The raised exception as ``"Type: message"``, or None if none was raised.
        """
        if self.raised_exception is None:
            return None
        return "%s: %s" % (
            type(self.raised_exception).__name__,
            self.raised_exception,
        )

    def has_informative_plan_failure(self) -> bool:
        """
        Whether the raised exception names what actually went wrong.
        """
        return isinstance(self.raised_exception, PlanFailure) and not isinstance(
            self.raised_exception, UNINFORMATIVE_PLAN_FAILURES
        )


@dataclass(frozen=True)
class InsertionDiagnosis:
    """
    Why one attempt left its shape out of the box, and what that was read from.
    """

    reason: InsertionFailureReason
    """
    The single reason the attempt is described by.
    """

    detail: str
    """
    What the reason was read from, including the raised exception when there was one.
    """

    @classmethod
    def of(cls, evidence: InsertionEvidence) -> InsertionDiagnosis:
        """
        Judge one attempt, preferring what the plan reported over what was observed.

        Ranked, first match wins: an informative plan failure, then no pick-up, then a
        drop while carrying, then a shape wedged in its hole, then a release off target.

        :param evidence: What the attempt left behind.
        """
        if evidence.has_informative_plan_failure():
            return cls(InsertionFailureReason.PLAN_FAILED, evidence.named_exception())
        if not evidence.events:
            return cls(
                InsertionFailureReason.UNDIAGNOSED,
                cls._explain("nothing was observed", evidence),
            )
        if evidence.picked_up_at() is None:
            return cls(
                InsertionFailureReason.NOT_PICKED_UP,
                cls._explain("no pick-up was detected", evidence),
            )
        if evidence.dropped_at() is not None:
            return cls(
                InsertionFailureReason.DROPPED_BEFORE_INSERTION,
                cls._explain(
                    "the shape left %s before the insertion phase"
                    % ", ".join(evidence.released_body_names()),
                    evidence,
                ),
            )
        if evidence.was_detected_inserted():
            return cls(
                InsertionFailureReason.WEDGED_IN_HOLE,
                cls._explain(
                    "the shape entered its hole but did not pass through", evidence
                ),
            )
        return cls(
            InsertionFailureReason.RELEASED_OFF_TARGET,
            cls._explain("the shape was carried but never entered its hole", evidence),
        )

    @staticmethod
    def _explain(observation: str, evidence: InsertionEvidence) -> str:
        """
        One observation, prefixed by the raised exception when there was one.

        :param observation: What the events showed.
        :param evidence: What the attempt left behind.
        """
        named_exception = evidence.named_exception()
        if named_exception is None:
            return observation
        return "%s; %s" % (named_exception, observation)
