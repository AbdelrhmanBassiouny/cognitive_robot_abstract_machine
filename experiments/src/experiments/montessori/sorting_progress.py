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

from coraplex.datastructures.enums import TaskStatus
from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import ActionNode, DesignatorNode, PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from cramera.body_geometry import NumericPose
from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    AbstractContactEvent,
    DetectionEvent,
    EventWithTrackedObjects,
    InsertionEvent,
    MotionEvent,
    PickUpEvent,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Dict, Iterable, List, Optional, Tuple, Type, TypeVar

from experiments.montessori.insertion_diagnosis import (
    InsertionDiagnosis,
    InsertionEvidence,
    InsertionFailureReason,
)
from experiments.montessori.semantics import (
    MontessoriShape,
    SHAPE_NAME_SUFFIX,
    ShapeSortingBoard,
)
from experiments.montessori.sorting_results import InsertionOutcome

Recorded = TypeVar("Recorded")


def instantiable_subclasses(base: Type[Recorded]) -> List[Type[Recorded]]:
    """
    Every subclass of ``base`` that is not itself subclassed, which for a tree of record
    types is the set an actual record can be an instance of.

    Only the subclasses this process has imported are found, which for a running demo is
    every type its own plans and detectors can produce.

    :param base: The root of the class tree to walk.
    """
    found: List[Type[Recorded]] = []
    for subclass in base.__subclasses__():
        if subclass.__subclasses__():
            found.extend(instantiable_subclasses(subclass))
        else:
            found.append(subclass)
    return found


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

    target_pose: Optional[NumericPose] = None
    """
    The pose, in the world root frame, the shape is aimed to be released at.
    """

    is_inserted: bool = False
    """
    Whether the shape is in the box right now, as the world's geometry says.
    """

    is_current: bool = False
    """
    Whether this is the shape the demo is sorting right now, which is what it is trying
    to achieve and so what a question about its goal is answered with.
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

    def related_highlight_ids(self) -> List[str]:
        """
        The piece's published body, so an answer row for this shape lights the piece
        itself up: the record is named after what the piece is (``"cube"``) while the
        viewer shows its body under the name it was built with
        (``"square_hole_shape"``).
        """
        return [self.shape_key + SHAPE_NAME_SUFFIX]


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

    target_pose: Optional[NumericPose] = None
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

    is_action: bool
    """
    Whether the node carries an action the robot performs, rather than sequencing other
    nodes.
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
            is_action=isinstance(node, ActionNode),
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
class PerformedAction:
    """
    One action of an attempt's plan, as the robot carrying it out.

    A plan step is any node of the tree; an action is the part of it a question about
    what the robot did or is doing means.
    """

    name: str
    """
    The action's label, e.g. ``"square_hole PickUpAction"``.
    """

    shape_key: str
    """
    Key of the shape whose attempt this action belongs to.
    """

    attempt_number: int
    """
    Index of the attempt this action belongs to.
    """

    action_type: str
    """
    The action's own type, e.g. ``"PickUpAction"``.
    """

    status: str
    """
    The action's execution status.
    """

    is_current: bool = False
    """
    Whether the robot is carrying this action out right now.
    """

    started_at: Optional[datetime] = None
    """
    When the action started performing.
    """

    duration: Optional[float] = None
    """
    How long the action took, in seconds.
    """

    target: Optional[str] = None
    """
    What the action acts on, when it names something.
    """

    reason: Optional[str] = None
    """
    Why the action failed, when it recorded one.
    """

    @classmethod
    def of_plan(
        cls, plan: Plan, shape: ShapeUnderTest, attempt_number: int
    ) -> List[PerformedAction]:
        """
        The actions of one attempt's plan, in execution order.

        :param plan: The realized plan tree.
        :param shape: The shape whose attempt this plan is.
        :param attempt_number: Index of the attempt this plan is.
        """
        return [
            cls.of_step(step)
            for step in PlanStep.of_plan(plan, shape, attempt_number)
            if step.is_action
        ]

    @classmethod
    def of_step(cls, step: PlanStep) -> PerformedAction:
        """
        One plan step that carries an action, as that action.

        :param step: The step to read.
        """
        return cls(
            name="%s %s" % (step.shape_key, step.name),
            shape_key=step.shape_key,
            attempt_number=step.attempt_number,
            action_type=step.name,
            status=step.status,
            started_at=step.started_at,
            duration=step.duration,
            target=step.target,
            reason=step.reason,
        )

    @classmethod
    def performable_action_types(cls) -> Tuple[str, ...]:
        """
        The type of every action the robot can be asked for by name, in alphabetical
        order.
        """
        return tuple(
            sorted(
                action_type.__name__
                for action_type in instantiable_subclasses(ActionDescription)
            )
        )


@dataclass
class PerformingAttempt:
    """
    The attempt being performed right now, read from its plan as the plan grows.

    An attempt's actions are only recorded once it finishes, so this is what a question
    about what the robot is doing now is answered from.
    """

    plan: Plan
    """
    The plan being performed.
    """

    shape: ShapeUnderTest
    """
    The shape this attempt is being made on.
    """

    attempt_number: int
    """
    The attempt's 1-based index among its shape's attempts.
    """

    def actions(self) -> List[PerformedAction]:
        """
        This attempt's actions so far, with the one being carried out marked.
        """
        actions = PerformedAction.of_plan(self.plan, self.shape, self.attempt_number)
        running = [
            action for action in actions if action.status == TaskStatus.RUNNING.name
        ]
        if running:
            # an action expanding into further actions leaves every node on the way down
            # running, and the innermost of them is what the robot is actually doing
            running[-1].is_current = True
        return actions


ATOMIC_EVENT_TYPES: Tuple[Type[DetectionEvent], ...] = (
    AbstractContactEvent,
    MotionEvent,
)
"""
The event types too fine-grained to answer a question with: a contact appearing or
disappearing, and a motion starting or stopping.

Detecting them is what the coarser events are read from, and what
:mod:`experiments.montessori.insertion_diagnosis` tells a dropped shape from one that
was never picked up by, so they are detected and then left unrecorded rather than not
detected at all.
"""


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
    def recordable_event_types(cls) -> Tuple[str, ...]:
        """
        The type of every event a record can be written for, in alphabetical order.

        The atomic ones :data:`ATOMIC_EVENT_TYPES` names are detected and then left
        unrecorded, so no question can ask for them.
        """
        return tuple(
            sorted(
                event_type.__name__
                for event_type in instantiable_subclasses(DetectionEvent)
                if not issubclass(event_type, ATOMIC_EVENT_TYPES)
            )
        )

    @classmethod
    def of_attempt(
        cls,
        events: Iterable[DetectionEvent],
        shape: ShapeUnderTest,
        attempt_number: int,
    ) -> List[SegmindEventRecord]:
        """
        The events of one attempt worth answering a question with, as records.

        :param events: Every event detected while the attempt ran.
        :param shape: The shape the attempt was made on.
        :param attempt_number: Index of the attempt.
        """
        return [
            cls.of_event(event, shape, attempt_number)
            for event in events
            if not isinstance(event, ATOMIC_EVENT_TYPES)
        ]

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

    _actions: List[PerformedAction] = field(default_factory=list)
    """
    The actions of every finished attempt, as its plan left them.
    """

    _performing: Optional[PerformingAttempt] = None
    """
    The attempt being performed right now, or None between attempts.
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

    @property
    def actions(self) -> List[PerformedAction]:
        """
        Every action performed so far: the finished attempts' as their plans left them,
        then the attempt being performed read from its own plan, so the action being
        carried out is named while it is still running.
        """
        with self._lock:
            performed = list(self._actions)
            performing = self._performing
        if performing is None:
            return performed
        return performed + performing.actions()

    def follow_plan(self, plan: Plan, shape_key: str, attempt_number: int) -> None:
        """
        Watch one attempt's plan while it performs, so a question about what the robot
        is doing is answered from the plan rather than waiting for the attempt to end.

        :param plan: The plan about to be performed.
        :param shape_key: Key of the shape the attempt is being made on.
        :param attempt_number: The attempt's 1-based index.
        :raises UntrackedShapeError: When that shape was never begun.
        """
        tracked = self._tracked_record(shape_key)
        with self._lock:
            self._performing = PerformingAttempt(
                plan=plan, shape=tracked, attempt_number=attempt_number
            )

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
            target_pose=NumericPose.of_pose(board.insertion_target_for(shape, world)),
            is_inserted=board.has_fallen_through(shape, world),
        )
        tracked.is_current = True
        with self._lock:
            for sorted_earlier in self._shapes:
                sorted_earlier.is_current = False
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
        events = SegmindEventRecord.of_attempt(
            completed.events, tracked, completed.attempt_number
        )
        steps = (
            PlanStep.of_plan(completed.plan, tracked, completed.attempt_number)
            if completed.plan is not None
            else []
        )
        with self._lock:
            self._attempts.append(record)
            self._events.extend(events)
            self._plan_steps.extend(steps)
            # a plan abandoned mid-action leaves that node reading RUNNING for good, so
            # a finished attempt's actions are frozen with none of them current
            self._actions.extend(
                PerformedAction.of_step(step) for step in steps if step.is_action
            )
            self._performing = None
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
                    tracked.is_current = False

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
