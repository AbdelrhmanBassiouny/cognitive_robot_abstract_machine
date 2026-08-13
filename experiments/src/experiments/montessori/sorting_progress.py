"""
The record a running sort keeps of itself, in the shape questions are asked of it.

Kept alongside :mod:`experiments.montessori.sorting_results`, not instead of it: those
are the dataclasses persisted once an iteration finishes, these are flat projections
that can be read *while* the iteration runs, from a thread that must not touch the
world.

Every entity here is plain data with a ``name``, so an entity query language variable can
range over it and an answer row renders without following any references.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import DesignatorNode, PlanNode
from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    DetectionEvent,
    EventWithTrackedObjects,
    InsertionEvent,
    PickUpEvent,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Dict, List, Optional

from experiments.montessori.insertion_diagnosis import (
    InsertionDiagnosis,
    InsertionEvidence,
    InsertionFailureReason,
)
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from experiments.montessori.sorting_results import InsertionOutcome

INSERTION_PHASE_ACTION_NAME = "PlaceAction"
"""
Name of the designator whose start marks the end of carrying and the start of lowering
the shape into its hole.
"""


@dataclass
class UntrackedShapeError(DataclassException):
    """
    Raised when an attempt is recorded for a shape no one started tracking.
    """

    shape_key: str
    """
    Key of the shape the attempt was made on.
    """

    def error_message(self) -> str:
        return "no shape '%s' is being tracked" % self.shape_key

    def suggest_correction(self) -> str:
        return "Call begin_shape before recording that shape's first attempt."


@dataclass
class ShapeUnderTest:
    """
    One shape the demo is sorting, and how it is doing.
    """

    name: str
    """
    What the piece is, e.g. ``"cube"`` (see
    :attr:`~experiments.montessori.semantics.MontessoriShape.object_name`).
    """

    shape_key: str
    """
    The key pairing this shape with its hole, e.g. ``"square_hole"``, and the key its
    results are recorded under.
    """

    shape_category: str
    """
    The shape's geometric category.
    """

    target_hole: str
    """
    Name of the hole this shape is aimed at.
    """

    target_pose: Optional[Pose] = None
    """
    The pose, in the world root frame, the shape is aimed to be released at.
    """

    is_inserted: bool = False
    """
    Whether the shape is in the box right now, as the world's geometry says.
    """

    outcome: Optional[InsertionOutcome] = None
    """
    How this shape's attempts ended, once they have.
    """

    attempt_count: int = 0
    """
    How many attempts have been made on this shape so far.
    """

    was_picked_up: bool = False
    """
    Whether segmind detected the shape being picked up in any attempt.
    """

    was_detected_inserted: bool = False
    """
    Whether segmind detected the shape entering its hole in any attempt.
    """

    failure_reason: Optional[InsertionFailureReason] = None
    """
    Why the most recent attempt did not put the shape in the box.
    """

    failure_detail: Optional[str] = None
    """
    What that reason was read from.
    """


@dataclass
class InsertionAttemptRecord:
    """
    One attempt at inserting one shape.
    """

    name: str
    """
    The attempt's label, e.g. ``"square_hole attempt 2"``.
    """

    shape_key: str
    """
    Key of the shape the attempt was made on.
    """

    attempt_number: int
    """
    The attempt's 1-based index among its shape's attempts.
    """

    succeeded: bool
    """
    Whether the shape fell through its hole on this attempt.
    """

    target_hole: str
    """
    Name of the hole this attempt aimed at.
    """

    started_at: datetime
    """
    When the attempt began.
    """

    ended_at: datetime
    """
    When the attempt finished, successfully or not.
    """

    target_pose: Optional[Pose] = None
    """
    The pose, in the world root frame, this attempt aimed to release the shape at.
    """

    insertion_phase_started_at: Optional[datetime] = None
    """
    When the attempt stopped carrying the shape and began lowering it into its hole.
    """

    failure_reason: Optional[InsertionFailureReason] = None
    """
    Why the attempt did not put the shape in the box, if it did not.
    """

    failure_detail: Optional[str] = None
    """
    What that reason was read from.
    """

    raised_exception: Optional[str] = None
    """
    The exception the attempt raised, as ``"Type: message"``, if it raised one.
    """


@dataclass
class PlanStep:
    """
    One node of an attempt's realized plan.
    """

    name: str
    """
    The step's label: its designator's type, or the node's own.
    """

    shape_key: str
    """
    Key of the shape whose attempt this step belongs to.
    """

    attempt_number: int
    """
    Index of the attempt this step belongs to.
    """

    kind: str
    """
    The plan node's own type.
    """

    status: str
    """
    The node's execution status.
    """

    reason: Optional[str] = None
    """
    Why the node failed, when it recorded one.
    """

    started_at: Optional[datetime] = None
    """
    When the node started performing.
    """

    duration: Optional[float] = None
    """
    How long the node took, in seconds.
    """

    target: Optional[str] = None
    """
    What the node's designator acts on, when it names something.
    """

    @classmethod
    def of_plan(
        cls, plan: Plan, shape: ShapeUnderTest, attempt_number: int
    ) -> List[PlanStep]:
        """
        Flatten one attempt's realized plan into its steps, in execution order.

        :param plan: The realized plan tree.
        :param shape: The shape whose attempt this plan is.
        :param attempt_number: Index of the attempt this plan is.
        """
        return [
            cls._of_node(node, shape.shape_key, attempt_number) for node in plan.nodes
        ]

    @classmethod
    def _of_node(cls, node: PlanNode, shape_key: str, attempt_number: int) -> PlanStep:
        """
        One plan node as a step.

        :param node: The plan node to flatten.
        :param shape_key: Key of the shape whose attempt this node belongs to.
        :param attempt_number: Index of the attempt this node belongs to.
        """
        designator = node.designator if isinstance(node, DesignatorNode) else None
        return cls(
            name=(
                type(designator).__name__
                if designator is not None
                else type(node).__name__
            ),
            shape_key=shape_key,
            attempt_number=attempt_number,
            kind=type(node).__name__,
            status=node.status.name,
            reason=str(node.reason) if node.reason is not None else None,
            started_at=node.start_time,
            duration=cls._duration_of(node),
            target=cls._target_of(designator),
        )

    @staticmethod
    def _duration_of(node: PlanNode) -> Optional[float]:
        """
        How long a node took in seconds, or None if it did not both start and finish.

        :param node: The plan node to measure.
        """
        if node.start_time is None or node.end_time is None:
            return None
        return (node.end_time - node.start_time).total_seconds()

    @staticmethod
    def _target_of(designator: Optional[object]) -> Optional[str]:
        """
        What a designator acts on, when its fields name something.

        :param designator: The node's designator, or None.
        """
        if designator is None:
            return None
        named = [
            str(value.name)
            for value in vars(designator).values()
            if isinstance(value, (Body, MontessoriShape))
        ]
        return named[0] if named else None


@dataclass
class SegmindEventRecord:
    """
    One event segmind detected, flattened to what a query asks about it.
    """

    name: str
    """
    The event's label, e.g. ``"square_hole PickUpEvent"``.
    """

    shape_key: str
    """
    Key of the shape the event was detected for.
    """

    attempt_number: int
    """
    Index of the attempt the event fell within.
    """

    event_type: str
    """
    The detected event's own type.
    """

    timestamp: datetime
    """
    When the event was detected.
    """

    with_object: Optional[str] = None
    """
    Name of the other body or region the event relates the shape to.
    """

    through_hole: Optional[str] = None
    """
    Name of the hole an insertion was detected through.
    """

    @classmethod
    def of_event(
        cls, event: DetectionEvent, shape: ShapeUnderTest, attempt_number: int
    ) -> SegmindEventRecord:
        """
        One detected event as a record.

        :param event: The detected event.
        :param shape: The shape whose attempt the event fell within.
        :param attempt_number: Index of that attempt.
        """
        event_type = type(event).__name__
        with_object = (
            event.with_object if isinstance(event, EventWithTrackedObjects) else None
        )
        through_hole = event.through_hole if isinstance(event, InsertionEvent) else None
        return cls(
            name="%s %s" % (shape.name, event_type),
            shape_key=shape.shape_key,
            attempt_number=attempt_number,
            event_type=event_type,
            timestamp=event.timestamp,
            with_object=str(with_object.name) if with_object is not None else None,
            through_hole=str(through_hole.name) if through_hole is not None else None,
        )


@dataclass
class CompletedAttempt:
    """
    Everything one finished attempt leaves behind, as the demo has it in hand.
    """

    shape_key: str
    """
    Key of the shape the attempt was made on.
    """

    attempt_number: int
    """
    The attempt's 1-based index among its shape's attempts.
    """

    started_at: datetime
    """
    When the attempt began.
    """

    ended_at: datetime
    """
    When the attempt finished.
    """

    events: List[DetectionEvent] = field(default_factory=list)
    """
    Segmind events whose timestamp fell within this attempt.
    """

    plan: Optional[Plan] = None
    """
    The attempt's realized plan tree, when it got far enough to have one.
    """

    fell_through: Optional[bool] = None
    """
    The ground-truth verdict, or None when the attempt raised before reaching it.
    """

    raised_exception: Optional[BaseException] = None
    """
    The exception the attempt raised, if it raised one.
    """

    gripper_bodies: List[Body] = field(default_factory=list)
    """
    Bodies of the robot that hold the shape, so releasing it can be recognized.
    """

    def insertion_phase_started_at(self) -> Optional[datetime]:
        """
        When this attempt stopped carrying the shape and began lowering it.
        """
        if self.plan is None:
            return None
        starts = [
            node.start_time
            for node in self.plan.nodes
            if isinstance(node, DesignatorNode)
            and type(node.designator).__name__ == INSERTION_PHASE_ACTION_NAME
            and node.start_time is not None
        ]
        return min(starts, default=None)

    def evidence(self) -> InsertionEvidence:
        """
        This attempt's evidence, for judging why it did not put the shape in the box.
        """
        return InsertionEvidence(
            events=self.events,
            gripper_bodies=self.gripper_bodies,
            raised_exception=self.raised_exception,
            insertion_phase_started_at=self.insertion_phase_started_at(),
        )


@dataclass
class SortingProgress:
    """
    What the demo has done so far, readable while it is still doing it.

    Written by the thread running the sort and read by the thread answering queries, so
    every list is copied out under :attr:`_lock` rather than handed out directly.
    """

    _shapes: List[ShapeUnderTest] = field(default_factory=list)
    """
    One entry per shape the demo has started on.
    """

    _attempts: List[InsertionAttemptRecord] = field(default_factory=list)
    """
    One entry per finished attempt, in the order they finished.
    """

    _plan_steps: List[PlanStep] = field(default_factory=list)
    """
    Every finished attempt's plan, flattened.
    """

    _events: List[SegmindEventRecord] = field(default_factory=list)
    """
    Every segmind event recorded against the attempt it fell within.
    """

    _tracked_shapes: Dict[str, MontessoriShape] = field(default_factory=dict)
    """
    The live shapes behind :attr:`_shapes`, so the world can be re-read for them.

    Kept apart from the records themselves, which stay free of world references so that
    answering a query never reaches into the world.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards every list, which the querying thread reads while the demo writes.
    """

    @property
    def shapes(self) -> List[ShapeUnderTest]:
        """
        The shapes the demo has started on.
        """
        with self._lock:
            return list(self._shapes)

    @property
    def attempts(self) -> List[InsertionAttemptRecord]:
        """
        The attempts finished so far.
        """
        with self._lock:
            return list(self._attempts)

    @property
    def plan_steps(self) -> List[PlanStep]:
        """
        The plan steps of every finished attempt.
        """
        with self._lock:
            return list(self._plan_steps)

    @property
    def events(self) -> List[SegmindEventRecord]:
        """
        The segmind events recorded so far.
        """
        with self._lock:
            return list(self._events)

    def begin_shape(
        self, shape: MontessoriShape, board: ShapeSortingBoard, world: World
    ) -> None:
        """
        Start tracking one shape, recording the hole and pose it is aimed at.

        :param shape: The shape the demo is about to attempt.
        :param board: The board the shape is being sorted into.
        :param world: The world both live in.
        """
        tracked = ShapeUnderTest(
            name=shape.object_name,
            shape_key=shape.shape_key,
            shape_category=str(shape.shape_category),
            target_hole=board.hole_for(shape).name.name,
            target_pose=board.insertion_target_for(shape, world),
            is_inserted=board.has_fallen_through(shape, world),
        )
        with self._lock:
            self._tracked_shapes[shape.shape_key] = shape
            self._shapes.append(tracked)

    def record_attempt(self, completed: CompletedAttempt) -> None:
        """
        Record one finished attempt, its plan, its events and why it failed.

        :param completed: What the attempt left behind.
        """
        succeeded = completed.fell_through is True
        diagnosis = None if succeeded else InsertionDiagnosis.of(completed.evidence())
        tracked = self._tracked_record(completed.shape_key)
        record = InsertionAttemptRecord(
            name="%s attempt %d" % (tracked.name, completed.attempt_number),
            shape_key=tracked.shape_key,
            attempt_number=completed.attempt_number,
            succeeded=succeeded,
            target_hole=tracked.target_hole,
            target_pose=tracked.target_pose,
            started_at=completed.started_at,
            ended_at=completed.ended_at,
            insertion_phase_started_at=completed.insertion_phase_started_at(),
            failure_reason=diagnosis.reason if diagnosis else None,
            failure_detail=diagnosis.detail if diagnosis else None,
            raised_exception=completed.evidence().named_exception(),
        )
        events = [
            SegmindEventRecord.of_event(event, tracked, completed.attempt_number)
            for event in completed.events
        ]
        steps = (
            PlanStep.of_plan(completed.plan, tracked, completed.attempt_number)
            if completed.plan is not None
            else []
        )
        with self._lock:
            self._attempts.append(record)
            self._events.extend(events)
            self._plan_steps.extend(steps)
        self._update_shape(completed, record)

    def finish_shape(self, shape_key: str, outcome: InsertionOutcome) -> None:
        """
        Record how one shape's attempts ended.

        :param shape_key: Key of the shape that is done.
        :param outcome: How its attempts ended.
        """
        with self._lock:
            for tracked in self._shapes:
                if tracked.shape_key == shape_key:
                    tracked.outcome = outcome

    def refresh_world_state(self, board: ShapeSortingBoard, world: World) -> None:
        """
        Re-read whether each tracked shape is in the box right now.

        Reads the world, so it must be called from the thread that runs the demo, never
        from the one answering queries.

        :param board: The board the shapes are being sorted into.
        :param world: The world the shapes live in.
        """
        with self._lock:
            tracked_shapes = dict(self._tracked_shapes)
        verdicts = {
            shape_key: board.has_fallen_through(shape, world)
            for shape_key, shape in tracked_shapes.items()
        }
        with self._lock:
            for tracked in self._shapes:
                if tracked.shape_key in verdicts:
                    tracked.is_inserted = verdicts[tracked.shape_key]

    def _tracked_record(self, shape_key: str) -> ShapeUnderTest:
        """
        The tracked record of one shape.

        :param shape_key: Key of the shape to look up.
        :raises UntrackedShapeError: When that shape was never begun.
        """
        with self._lock:
            tracked = next(
                (tracked for tracked in self._shapes if tracked.shape_key == shape_key),
                None,
            )
        if tracked is None:
            raise UntrackedShapeError(shape_key=shape_key)
        return tracked

    def _update_shape(
        self, completed: CompletedAttempt, record: InsertionAttemptRecord
    ) -> None:
        """
        Fold one finished attempt into its shape's own summary.

        :param completed: What the attempt left behind.
        :param record: The attempt as it was recorded.
        """
        picked_up = any(isinstance(event, PickUpEvent) for event in completed.events)
        inserted = any(isinstance(event, InsertionEvent) for event in completed.events)
        with self._lock:
            for tracked in self._shapes:
                if tracked.shape_key != completed.shape_key:
                    continue
                tracked.attempt_count += 1
                tracked.was_picked_up = tracked.was_picked_up or picked_up
                tracked.was_detected_inserted = (
                    tracked.was_detected_inserted or inserted
                )
                tracked.failure_reason = record.failure_reason
                tracked.failure_detail = record.failure_detail
