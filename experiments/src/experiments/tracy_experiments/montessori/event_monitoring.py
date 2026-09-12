"""
Live SegMind event monitoring for Tracy's MuJoCo Montessori demo: while the simulation
runs, tick a small SegMind statechart in a background thread so grasping, lifting, pick-
up, and insertion events are detected as they happen, rather than only inferred
afterwards from final shape positions.

A monitor tracks one shape at a time (see :func:`build_shape_monitor`), scoped to that
shape's own root body, its own matching hole, and the sorting arm's own gripper --
mirroring ``experiments.montessori.event_monitoring`` from the Franka Montessori demo
this was adapted from, but built against this repository's own ``segmind`` package,
which has since gained first-class support for ``Region``-rooted holes
(:class:`~segmind.detectors.spatial_relation_detector_nodes.HoleContactDetector`,
:class:`~segmind.detectors.spatial_relation_detector_nodes.LossOfHoleContactDetector`,
and ``additional_candidates`` on the containment detectors) rather than needing it added
here, and gripper-contact-based grasp/lift detection
(:mod:`segmind.detectors.grasp_detector_nodes`,
:class:`~segmind.detectors.atomic_event_detectors_nodes.LiftDetector`) that did not
exist for the Franka demo at all.

A "Released" event -- grasp contact lost while the object is now supported by something
else, distinguishing an intentional placement from simply dropping the object mid-air --
is deliberately not implemented yet; :class:`LossOfGraspEvent` alone (already detected
here) is the piece it would build on, not a replacement for it.

.. warning::
    :class:`~experiments.tracy_experiments.real_time_simulation.RealTimeSimulation`
    deliberately steps physics from the *calling* thread rather than a background one,
    specifically to avoid racing a caller's own reads of ``world.state`` against a
    background thread's writes (see that module's own docstring, and the
    ``ParkArmsAction`` bug it cites). Running SegMind's own tick loop on a background
    thread reintroduces exactly that race for whatever ``world`` state a detector reads
    (mainly body poses) -- accepted for now as a known trade-off while SegMind
    integration is still being verified, not a guarantee that a read is always
    consistent.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from typing_extensions import List, Optional

from coraplex.datastructures.enums import Arms
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from experiments.tracy_experiments.montessori.world import TracyMontessoriWorld
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.events import DetectionEvent
from segmind.detectors.atomic_event_detectors_nodes import (
    LiftDetector,
    StopLiftDetector,
    StopTranslationDetector,
    TranslationDetector,
)
from segmind.detectors.base import AbstractDetector, SegmindContext
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.detectors.grasp_detector_nodes import GraspDetector, LossOfGraspDetector
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
from semantic_digital_twin.robots.robot_parts import EndEffector
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body, Region

logger = logging.getLogger(__name__)

DEFAULT_TICK_RATE_HZ = 5.0
"""
Default rate the monitor's background thread ticks its statechart at.

Not yet measured against Tracy's own scene (only carried over from the Franka Montessori
demo this was adapted from) -- tune down if a single tick takes noticeably longer than
this on Tracy's board.
"""

# %% shape monitor construction


def _picking_end_effector(robot: Tracy, arm: Arms) -> EndEffector:
    """
    :return: The end effector of ``robot``'s sorting ``arm``, whose finger tips and tool
        frame drive grasp and lift detection.
    """
    return (robot.left_arm if arm == Arms.LEFT else robot.right_arm).end_effector


def build_pick_monitor(
    *,
    world: World,
    tracked_body: Body,
    robot: Tracy,
    arm: Arms,
) -> MontessoriEventMonitor:
    """
    Build a :class:`MontessoriEventMonitor` covering the pick half of a sort only:
    support, translation, grasp, lift and pick-up of one loose shape.

    Unlike :func:`build_shape_monitor_in_world` this adds no hole-contact, containment
    or insertion detectors, so it needs only ``tracked_body`` and the picking gripper --
    not a :class:`~experiments.montessori.semantics.ShapeSortingBoard` or a landing
    region table. That suits a demo whose loose shapes are bare bodies with no board
    model, at the cost of not detecting insertion into the hole.

    :param world: The live world the detectors tick against.
    :param tracked_body: The loose shape's own root body.
    :param robot: The robot doing the sorting.
    :param arm: Which of ``robot``'s arms does the sorting.
    """
    end_effector = _picking_end_effector(robot, arm)
    finger_tips = [end_effector.thumb.tip, end_effector.finger.tip]

    # The body-and-gripper subset of build_shape_monitor_in_world's detectors; kept a
    # separate list rather than shared, since that statechart's detector order is not
    # known to be free of tick-cycle coupling between coarse detectors.
    detectors = [
        SupportDetector(tracked_object=tracked_body),
        LossOfSupportDetector(tracked_object=tracked_body),
        TranslationDetector(tracked_object=tracked_body),
        StopTranslationDetector(tracked_object=tracked_body),
        GraspDetector(
            tracked_object=tracked_body,
            finger_tips=finger_tips,
            tool_frame=end_effector.tool_frame,
        ),
        LossOfGraspDetector(
            tracked_object=tracked_body,
            finger_tips=finger_tips,
            tool_frame=end_effector.tool_frame,
        ),
        LiftDetector(tracked_object=tracked_body),
        StopLiftDetector(tracked_object=tracked_body),
        PickUpDetector(tracked_object=tracked_body),
        PlacingDetector(tracked_object=tracked_body),
    ]
    return MontessoriEventMonitor(world=world, detectors=detectors)


def build_shape_monitor(
    montessori: TracyMontessoriWorld,
    shape: MontessoriShape,
    robot: Tracy,
    arm: Arms,
) -> MontessoriEventMonitor:
    """
    Build a :class:`MontessoriEventMonitor` tracking a single loose shape's grasping,
    lifting, pick-up and insertion into its own matching hole.

    :param montessori: The Montessori scene the shape belongs to; used to look up the
        shape's own matching hole and that hole's landing region (see
        :attr:`~experiments.montessori.world.MontessoriWorld.landing_regions`) as the
        containment detectors' extra candidate. A hole's own root region is a thin
        marker flush with its opening; measured against a real, physically simulated
        drop, a shape can fall clean through it between one tick and the next without
        ever registering an overlap, and the landing region (spanning the opening's
        full depth) fixes that.
    :param shape: The loose shape to track.
    :param robot: The robot doing the sorting; used to look up ``arm``'s own gripper
        fingers and tool center point for grasp detection.
    :param arm: Which of ``robot``'s arms does the sorting.
    """
    return build_shape_monitor_in_world(
        world=montessori.world,
        board=montessori.board,
        landing_regions=montessori.landing_regions,
        shape=shape,
        robot=robot,
        arm=arm,
    )


def build_shape_monitor_in_world(
    *,
    world: World,
    board: ShapeSortingBoard,
    landing_regions: dict[str, Region],
    shape: MontessoriShape,
    robot: Tracy,
    arm: Arms,
) -> MontessoriEventMonitor:
    """
    Build a :class:`MontessoriEventMonitor` for one shape against an explicit world,
    board and landing-region table rather than a whole
    :class:`~experiments.tracy_experiments.montessori.world.TracyMontessoriWorld`.

    The physical demo merges its Montessori scene onto the live, fetched world, which
    empties the scratch :class:`~experiments.tracy_experiments.montessori.world.
    TracyMontessoriWorld` it built the scene in, so it has no intact
    :class:`~experiments.tracy_experiments.montessori.world.TracyMontessoriWorld` to hand
    :func:`build_shape_monitor`; it passes the merged pieces here instead.

    :param world: The live world the detectors tick against.
    :param board: The merged shape-sorting board, to look up ``shape``'s matching hole.
    :param landing_regions: Landing region per hole key (see
        :attr:`~experiments.montessori.world.MontessoriWorld.landing_regions`).
    :param shape: The loose shape to track.
    :param robot: The robot doing the sorting.
    :param arm: Which of ``robot``'s arms does the sorting.
    """
    hole = board.hole_for(shape)
    landing_region = landing_regions.get(hole.name.name)
    additional_candidates = {hole: landing_region} if landing_region is not None else {}

    end_effector = _picking_end_effector(robot, arm)
    finger_tips = [end_effector.thumb.tip, end_effector.finger.tip]

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
        TranslationDetector(tracked_object=shape.root),
        StopTranslationDetector(tracked_object=shape.root),
        GraspDetector(
            tracked_object=shape.root,
            finger_tips=finger_tips,
            tool_frame=end_effector.tool_frame,
        ),
        LossOfGraspDetector(
            tracked_object=shape.root,
            finger_tips=finger_tips,
            tool_frame=end_effector.tool_frame,
        ),
        LiftDetector(tracked_object=shape.root),
        StopLiftDetector(tracked_object=shape.root),
        PickUpDetector(tracked_object=shape.root),
        PlacingDetector(tracked_object=shape.root),
        InsertionDetector(tracked_object=shape.root),
    ]
    return MontessoriEventMonitor(world=world, detectors=detectors)


# %% background-threaded monitor


@dataclass
class MontessoriEventMonitor:
    """
    Ticks a SegMind statechart against a live world on a background thread, so pick-
    up/insertion events are detected as the simulation runs instead of only
    reconstructed afterwards.

    Reads whatever pose data is currently in :attr:`world` on each tick -- see this
    module's own docstring for the concurrency trade-off that implies while
    :class:`~experiments.tracy_experiments.real_time_simulation.RealTimeSimulation`
    steps physics from the calling thread.
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

    _stop_requested: threading.Event = field(
        init=False, default_factory=threading.Event
    )
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
