"""
Live segmind event monitoring for the Franka Montessori demo: while a simulation is
running, tick a small segmind statechart in the background so pick-up and insertion
events are detected as they happen, rather than only checked for after the fact via
:meth:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction.has_fallen_through_hole`.

A monitor tracks one shape at a time (see :func:`build_shape_monitor`), which keeps a
tick around 0.2s on this scene, fast enough to run live in the background without
slowing the demo down. Tracking every loose shape on the table at once needs the
broader collision-broad-phase optimization tracked separately, not yet done.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from typing_extensions import List, Optional

from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import MontessoriWorld
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.events import DetectionEvent
from segmind.detectors.atomic_event_detectors_nodes import (
    StopTranslationDetector,
    TranslationDetector,
)
from segmind.detectors.base import AbstractDetector, SegmindContext
from segmind.detectors.coarse_event_detector_nodes import PickUpDetector, PlacingDetector
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
Default rate the monitor's background thread ticks its statechart at; measured
comfortably achievable for a single tracked shape on the Montessori scene (see this
module's own docstring).
"""


def build_shape_monitor(
    montessori: MontessoriWorld, shape: MontessoriShape
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
    """
    hole = montessori.board.hole_for(shape)
    landing_region = montessori.landing_regions.get(hole.name.name)
    additional_candidates = {hole: landing_region} if landing_region is not None else {}
    detectors = [
        HoleContactDetector(tracked_object=shape.root, additional_candidates=additional_candidates),
        LossOfHoleContactDetector(tracked_object=shape.root, additional_candidates=additional_candidates),
        SupportDetector(tracked_object=shape.root),
        LossOfSupportDetector(tracked_object=shape.root),
        ContainmentDetector(
            tracked_object=shape.root,
            additional_candidates=[landing_region] if landing_region is not None else [],
        ),
        LossOfContainmentDetector(
            tracked_object=shape.root,
            additional_candidates=[landing_region] if landing_region is not None else [],
        ),
        TranslationDetector(tracked_object=shape.root),
        StopTranslationDetector(tracked_object=shape.root),
        PickUpDetector(tracked_object=shape.root),
        PlacingDetector(tracked_object=shape.root),
        InsertionDetector(tracked_object=shape.root),
    ]
    return MontessoriEventMonitor(world=montessori.world, detectors=detectors)


@dataclass
class MontessoriEventMonitor:
    """
    Ticks a segmind statechart against a live world on a background thread, so
    pick-up/insertion events are detected as the simulation runs instead of only
    reconstructed afterwards.

    Reads whatever pose data is currently in :attr:`world` on each tick, the same way
    :class:`~semantic_digital_twin.adapters.ros.tf_publisher.TFPublisher` and
    :class:`~semantic_digital_twin.adapters.ros.visualization.viz_marker.VizMarkerPublisher`
    already do from their own threads while a :class:`~semantic_digital_twin.adapters.multi_sim.MujocoSim`
    writes into it concurrently.
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

    tick_rate_hz: float = DEFAULT_TICK_RATE_HZ
    """
    How often the background thread ticks the statechart.
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

    _thread: Optional[threading.Thread] = field(init=False, default=None)
    """
    The background thread ticking the statechart, once :meth:`start` has been called.
    """

    _stop_requested: threading.Event = field(init=False, default_factory=threading.Event)
    """
    Set by :meth:`stop` to end the background thread's tick loop.
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

        Exposed directly (not just via :meth:`start`'s background thread) so a
        deterministic test can drive the statechart tick-by-tick against a manually
        posed world.
        """
        self._executor.tick()

    def start(self) -> None:
        """
        Start ticking the statechart on a background thread at :attr:`tick_rate_hz`.
        """
        self._stop_requested.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="segmind-event-monitor"
        )
        self._thread.start()

    def _run(self) -> None:
        tick_interval = 1.0 / self.tick_rate_hz
        while not self._stop_requested.is_set():
            tick_start = time.monotonic()
            self.tick()
            elapsed = time.monotonic() - tick_start
            remaining = tick_interval - elapsed
            if remaining > 0:
                self._stop_requested.wait(remaining)

    def stop(self) -> None:
        """
        Stop the background thread started by :meth:`start`, waiting for its current
        tick to finish.
        """
        self._stop_requested.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
