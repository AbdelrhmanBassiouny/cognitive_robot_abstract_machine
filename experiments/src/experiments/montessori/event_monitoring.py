"""
Live segmind event monitoring for the Franka Montessori demo: while a simulation is
running, tick a small segmind statechart so pick-up and insertion events are detected as
they happen, rather than only checked for after the fact via :meth:`~experiments.montess
ori.insert_shape_action.InsertMontessoriShapeAction.has_fallen_through_hole`.

A monitor tracks one shape at a time (see :func:`build_shape_monitor`), which measures a
tick at about 12 ms on this scene, inside a single control period. Tracking every loose
shape on the table at once needs the broader collision-broad-phase optimization tracked
separately, not yet done.

Ticking happens on the thread running the motion being watched, never on one of its own
-- see :class:`ControlCycleTicking` for what a second thread costs here, and
:class:`WatchesNothing` for the run that would rather not pay for detection at all.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from typing_extensions import Any, Callable, List, Optional, Protocol

from cramera.monkey_patch import MethodPatch

from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import MontessoriWorld
from giskardpy.executor import Executor
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.events import DetectionEvent
from segmind.detectors.atomic_event_detectors_nodes import (
    ContactDetector,
    LossOfContactDetector,
    StopTranslationDetector,
    TranslationDetector,
)
from segmind.detectors.base import AbstractDetector, SegmindContext
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.detectors.spatial_relation_detector_nodes import (
    ContainmentDetector,
    HoleContactDetector,
    InsertionDetector,
    LossOfContainmentDetector,
    LossOfHoleContactDetector,
    LossOfSupportDetector,
    SupportDetector,
)
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from segmind.statecharts.segmind_statechart import SegmindStatechart
from semantic_digital_twin.world import World

logger = logging.getLogger(__name__)

DEFAULT_TICK_RATE_HZ = 5.0
"""
Default rate the monitor's statechart is ticked at, as a gap between ticks.

One tick measures about 12 ms for a single tracked shape on this scene, and it runs on
the thread that is trying to plan (see :class:`ControlCycleTicking`), so this leaves the
monitor a twentieth of that thread. Raise it when the events matter more than the wait
-- a shorter gap resolves the brief finger contact and loss-of-contact transitions that
:mod:`experiments.montessori.insertion_diagnosis` reads to tell a dropped shape from one
that was never picked up.
"""


def build_shape_monitor(
    montessori: MontessoriWorld,
    shape: MontessoriShape,
    listener: Optional[ReceivesDetectedEvents] = None,
) -> MontessoriEventMonitor:
    """
    Build a :class:`MontessoriEventMonitor` tracking a single loose shape's pick-up and
    insertion into its own matching hole.

    :param montessori: The Montessori scene the shape belongs to; used to look up the
        shape's own matching hole's landing region (see
        :attr:`~experiments.montessori.world.MontessoriWorld.landing_regions`) as an
        extra contact/containment candidate. The hole's own root region is a thin
        marker flush with its opening; measured against a real, physically simulated
        drop, a shape can fall clean through it between one tick and the next without
        ever registering an overlap, and the board's overall bounding box cannot tell
        "still crossing the hole" from "now resting past it" apart either -- the
        landing region (spanning the opening's full depth) fixes both.
    :param shape: The loose shape to track.
    :param listener: Told what each tick detected, for a run that wants the events as
        they happen rather than once the attempt they fell within has finished.
    """
    hole = montessori.board.hole_for(shape)
    landing_region = montessori.landing_regions.get(hole.name.name)
    additional_candidates = {hole: landing_region} if landing_region is not None else {}
    detectors = [
        HoleContactDetector(
            tracked_object=shape.root, additional_candidates=additional_candidates
        ),
        LossOfHoleContactDetector(
            tracked_object=shape.root, additional_candidates=additional_candidates
        ),
        SupportDetector(tracked_object=shape.root),
        LossOfSupportDetector(tracked_object=shape.root),
        ContainmentDetector(
            tracked_object=shape.root,
            additional_candidates=(
                [landing_region] if landing_region is not None else []
            ),
        ),
        LossOfContainmentDetector(
            tracked_object=shape.root,
            additional_candidates=(
                [landing_region] if landing_region is not None else []
            ),
        ),
        # plain contact with whatever body is touching the shape, the gripper's fingers
        # included: a shape that slips out of them mid-transport is why an insertion
        # failed, and the hole-specific detectors above never see the robot at all (see
        # experiments.montessori.insertion_diagnosis)
        ContactDetector(tracked_object=shape.root),
        LossOfContactDetector(tracked_object=shape.root),
        TranslationDetector(tracked_object=shape.root),
        StopTranslationDetector(tracked_object=shape.root),
        PickUpDetector(tracked_object=shape.root),
        PlacingDetector(tracked_object=shape.root),
        InsertionDetector(tracked_object=shape.root),
    ]
    return MontessoriEventMonitor(
        world=montessori.world, detectors=detectors, listener=listener
    )


class TicksDetectors(Protocol):
    """
    Something whose detectors run one cycle at a time.
    """

    def tick(self) -> None:
        """
        Run one detection cycle.
        """


class ReceivesDetectedEvents(Protocol):
    """
    Something a monitor tells what it has just noticed.
    """

    def receive(self, events: List[DetectionEvent]) -> None:
        """
        Take what was detected since this was last called, oldest first.

        :param events: The newly detected events.
        """


class WatchesForEvents(Protocol):
    """
    Something a run can start watching a shape with, and afterwards ask what it saw.
    """

    def start(self) -> None:
        """
        Start watching.
        """

    def stop(self) -> None:
        """
        Stop watching.
        """

    def tick(self) -> None:
        """
        Run one detection cycle.
        """

    @property
    def events(self) -> List[DetectionEvent]:
        """
        Every event detected so far.
        """


@dataclass
class WatchesNothing:
    """
    A monitor that detects nothing, for a run that would rather move smoothly.

    A detector tick blocks the thread running the motion for about 12 ms and cannot be
    moved off that thread without racing CasADi (see :class:`ControlCycleTicking`), so a
    run that wants none of that cost can trade the event stream away. The sorting
    verdict itself is unaffected: it is read from the world's own geometry, not from
    these events.
    """

    def start(self) -> None:
        """
        Do no watching.
        """

    def stop(self) -> None:
        """
        Do no watching.
        """

    def tick(self) -> None:
        """
        Do no watching.
        """

    @property
    def events(self) -> List[DetectionEvent]:
        """
        Nothing, having watched for nothing.
        """
        return []


@dataclass
class ControlCycleTicking:
    """
    Ticks a monitor from the control cycle of whatever motion is executing, so its
    detectors read the world on the thread that plans the motion.

    A tick is a whole :class:`~giskardpy.executor.Executor` cycle, not only the detector
    reads: the collision computation it drives builds CasADi objects, and under cramera
    the patched cycle also snapshots every body's forward kinematics. CasADi releases the
    GIL for the duration of a call and counts its expression-node references without
    atomics, so a monitor ticking on a thread of its own frees nodes the planning thread
    is still dereferencing and the process dies inside CasADi.

    ..note:: The detectors themselves no longer build or read any symbolic value; they
       read geometry out as plain numbers. It is the cycle around them that keeps this
       on the planning thread.

    ..warning:: Drives ticking by replacing a method on a class, so at most one of these
       may run at a time.
    """

    tick_rate_hz: float = DEFAULT_TICK_RATE_HZ
    """
    Rate the monitor's ticks are limited to, however often control cycles run.
    """

    patched_method: MethodPatch = field(
        default_factory=lambda: MethodPatch(owner=Executor, name="tick")
    )
    """
    The control cycle ticking is driven from.
    """

    clock: Callable[[], float] = time.monotonic
    """
    Reads the monotonic time the gap between ticks is measured against.
    """

    _uninstall: Optional[Callable[[], None]] = field(init=False, default=None)
    """
    Restores :attr:`patched_method`, once ticking has been started.
    """

    _monitor: Optional[TicksDetectors] = field(init=False, default=None)
    """
    The monitor being ticked, once ticking has been started.
    """

    _is_ticking: bool = field(init=False, default=False)
    """
    Whether a tick of the monitor is already in progress.
    """

    _last_tick_time: Optional[float] = field(init=False, default=None)
    """
    When the monitor last finished a tick, or None while it has yet to tick at all.
    """

    def drive(self, monitor: TicksDetectors) -> None:
        """
        Start ticking ``monitor`` from every control cycle.

        :param monitor: The monitor to tick.
        """
        self._monitor = monitor
        self._last_tick_time = None
        self._uninstall = self.patched_method.install(self._tick_after_control_cycle)

    def stop(self) -> None:
        """
        Stop ticking, leaving the patched method as it was found.
        """
        if self._uninstall is None:
            return
        self._uninstall()
        self._uninstall = None
        self._monitor = None

    def _tick_after_control_cycle(
        self, original: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """
        Run the real control cycle, then tick the monitor if it is due one.

        :param original: The real, unpatched method being stood in for.
        :param args: Positional arguments forwarded to the wrapped call.
        :param kwargs: Keyword arguments forwarded to the wrapped call.
        """
        result = original(*args, **kwargs)
        if self._monitor is None or self._is_ticking or not self._is_tick_due():
            return result
        # the monitor drives an EpisodeSegmenterExecutor, whose own control cycle goes
        # through this same method: without this it would tick itself forever
        self._is_ticking = True
        try:
            self._monitor.tick()
        finally:
            # stamped after the tick, so the rate is the gap between ticks: a tick costs
            # several control cycles, and timing from its start would let one that
            # overran its interval be followed straight away by the next
            self._last_tick_time = self.clock()
            self._is_ticking = False
        return result

    def _is_tick_due(self) -> bool:
        """
        Whether enough time has passed since the monitor last ticked.

        A control cycle runs far more often than a detector tick can afford to, so a
        tick per cycle would spend the run detecting rather than sorting.
        """
        if self._last_tick_time is None:
            return True
        return self.clock() - self._last_tick_time >= 1.0 / self.tick_rate_hz


@dataclass
class MontessoriEventMonitor:
    """
    Ticks a segmind statechart against a live world, so pick-up/insertion events are
    detected as the simulation runs instead of only reconstructed afterwards.

    Reads whatever pose data is currently in :attr:`world` on each tick, from the thread
    that runs the motion being watched -- see :class:`ControlCycleTicking` for why no
    other thread may do the reading.
    """

    world: World
    """
    The live simulation world to tick detectors against; typically
    :attr:`~experiments.montessori.world.MontessoriWorld.world`.
    """

    detectors: List[AbstractDetector]
    """
    The detectors to run every tick; see :func:`build_shape_monitor` for the set this
    module builds for tracking one shape's pick-up and insertion.
    """

    ticking: ControlCycleTicking = field(default_factory=ControlCycleTicking)
    """
    Decides when :meth:`tick` is called between :meth:`start` and :meth:`stop`.
    """

    listener: Optional[ReceivesDetectedEvents] = None
    """
    Told what each tick detected, so a run can act on an event before the attempt it
    fell within has finished.
    """

    context: MotionStatechartContext = field(init=False)
    """
    The motion statechart context detectors run against, holding the shared
    :class:`~segmind.detectors.base.SegmindContext` extension.
    """

    _executor: EpisodeSegmenterExecutor = field(init=False)
    """
    Drives compilation and ticking of the detector statechart.
    """

    _handed_over_event_count: int = field(init=False, default=0)
    """
    How much of :attr:`events` :attr:`listener` has already been told about.
    """

    def __post_init__(self) -> None:
        self.context = MotionStatechartContext(world=self.world)
        self._executor = EpisodeSegmenterExecutor(context=self.context)
        statechart = SegmindStatechart().build_statechart(self.detectors)
        self._executor.compile(statechart)

    @property
    def events(self) -> List[DetectionEvent]:
        """
        Every event detected so far.
        """
        return self.context.require_extension(SegmindContext).logger.get_events()

    def tick(self) -> None:
        """
        Run one detection cycle against the current state of :attr:`world`.

        Exposed directly (not only through :attr:`ticking`) so the phases of a run that
        no motion executes in -- a shape settling under gravity -- can be watched too,
        and so a deterministic test can drive the statechart tick-by-tick against a
        manually posed world.
        """
        self._executor.tick()
        self._hand_over_new_events()

    def _hand_over_new_events(self) -> None:
        """
        Tell :attr:`listener` about whatever the tick just added, and nothing else.
        """
        if self.listener is None:
            return
        detected = self.events
        if len(detected) == self._handed_over_event_count:
            return
        self.listener.receive(detected[self._handed_over_event_count :])
        self._handed_over_event_count = len(detected)

    def start(self) -> None:
        """
        Start watching, ticking whenever :attr:`ticking` says to.
        """
        self._read_geometry_out()
        self.ticking.drive(self)

    def _read_geometry_out(self) -> None:
        """
        Read every collidable shape's placement out into numbers before watching starts.

        A shape's own placement is model data, read out once and reused, so paying for
        it here rather than inside the first tick keeps that one-time cost out of the
        motion it would otherwise interrupt.
        """
        for entity in self.world.kinematic_structure_entities:
            entity.combined_mesh

    def stop(self) -> None:
        """
        Stop watching.

        Detected events stay readable through :attr:`events`.
        """
        self.ticking.stop()
