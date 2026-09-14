"""
The physical Tracy's left arm sorts the loose Montessori pieces into the shape-sorting
board by looking -- wired the way :mod:`coraplex_real_tracy.demo` wires the physical
robot: a Giskard standalone node is launched, the live world is fetched and kept in step
through :class:`~experiments.tracy_experiments.live_tracy.LiveTracy`, and the plan runs
under :attr:`~coraplex.datastructures.enums.ExecutionType.REAL`.

Nothing on the table is placed by hand. The camera looks for the board by its
description (:func:`~experiments.montessori.perception.recorded_setup.lab_board`) and
the board found is stood in the live world with one
:class:`~experiments.montessori.semantics.ShapeSortingHole` per hole; one look then
stands every loose piece resting on the bare table where it was seen, as the piece the
set on the table says it is (see
:class:`~experiments.tracy_experiments.pickup.perceived_sorting.PerceivedSorting`).
Board and pieces are visible in the same rviz the physical robot renders in (via
``WorldSynchronizer``), so they can be checked against the real table before the
sorting runs -- the script pauses for that check after looking. Each piece is picked
from where it was seen and released above the hole of the perceived board it fits
through.

Each pick is watched by a SegMind :func:`~experiments.tracy_experiments.montessori.
event_monitoring.build_pick_monitor` monitor -- support, grasp, lift and pick-up, but
no hole-contact or insertion, since the pieces here are bare bodies with no board model.
Its events stream to the live dashboard at ``http://127.0.0.1:5000`` while the demo
runs, and a per-piece yes/no verdict is logged after each pick.

While a piece is carried to its hole, the left gripper's knuckle joint is watched for
slip: the close is re-commanded a little past fully closed on a fixed period and, if the
fingers then travel past where the grasp first settled, the piece has left the pads (see
:mod:`~experiments.tracy_experiments.montessori.gripper_feedback`). Each poll's verdict
is logged, and a slip also shows on the dashboard as a ``GripperSlipEvent``.

The run is recorded as one trial of one episode, the way a simulated run is: every
plan the rig performs, every motion state chart those plans run, every event its
monitors report and the working-memory question set asked about one piece at the end go
onto the trial, and where every joint stood along the run is kept beside the episode's
other artifacts -- with the bag, when one is recorded -- so the paper's cards can be
drawn from the run on the robot exactly as from a run in MuJoCo. The questions are
scored against what the person at the table says they put on it, since the twin is what
the camera made of the table and so the very thing an answer could be wrong about.

A perturbation can be asked for (``--perturbation``, aimed at ``--piece``): the person
at the table is told what to do before the sort, the camera looks at the table again
once they have done it, and the trial keeps what they were told and the episode which
perturbation it ran under.

Run with (the camera, ``iai_tracy_description`` and the Giskard/world-fetcher ROS stack
must be running)::

    python -m experiments.tracy_experiments.pickup.pickup_demo_real

Pass ``--record`` to capture a rosbag of the camera, depth camera and joint states for
the duration of the sorting. Bags are written to
:data:`~experiments.tracy_experiments.rosbag_recording.DEFAULT_BAG_DIRECTORY` and keep
one camera frame in
:data:`~experiments.tracy_experiments.rosbag_recording.DEFAULT_KEEP_EVERY_NTH_FRAME`;
both are overridable, see
``--bag-directory`` and ``--keep-every-nth-frame``. Pass ``--no-episode`` for a run that
keeps no episode: nothing is recorded to a database or beside it, and a bag asked for
stays where it was written.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from krrood.exceptions import DataclassException
from typing_extensions import Iterator, Optional, Sequence

logging.basicConfig(level=logging.INFO, format="%(message)s")

import rclpy

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import (
    ApproachDirection,
    Arms,
    ExecutionType,
    MovementType,
    VerticalAlignment,
)
from coraplex.datastructures.grasp import GraspDescription
from coraplex.execution_environment import ExecutionEnvironment
from coraplex.plans.attachment_nodes import ReAttachNode
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.pick_up import ReachAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.robot_plans.motions.gripper import MoveToolCenterPointMotion
from coraplex.view_manager import ViewManager
from experiments.episodes.artifacts import (
    ArtifactDirectory,
    EpisodeArtifacts,
    Transcript,
)
from experiments.episodes.episode import Episode, RecordedTrial
from experiments.episodes.observer import EpisodeObserver, ObserverMotionListener
from experiments.episodes.recording import open_recording
from experiments.episodes.trace import JointTrace, JointTraceRecorder
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_publishing import (
    LOOKS_FOR_THE_BOARD,
    PerceivedScene,
)
from experiments.montessori.record_episode import DEFAULT_PIECE, PerturbationChoice
from experiments.montessori.results_database import (
    ResultsDatabase,
    resolve_lasting_database,
)
from experiments.montessori.scenarios import (
    SortingPerturbation,
    SortingScene,
    SortingStep,
)
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.montessori.watched_run import SceneThePersonSetUp
from experiments.questions.question import QuestionedThings, SceneAsSetUp
from experiments.questions.after_the_move import QuestionAfterTheMove
from experiments.questions.question_set import QuestionSet
from experiments.scenarios.scenario import Person, PersonAtTheConsole
from experiments.scenarios.trial import TrialOutcome
from experiments.tracy_experiments.live_tracy import LiveTracy
from experiments.tracy_experiments.montessori.event_dashboard import (
    EventFeed,
    run_dashboard,
)
from experiments.tracy_experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_pick_monitor,
    build_translation_monitor,
)
from experiments.tracy_experiments.montessori.grasp_widths import GraspCloseTable
from experiments.tracy_experiments.montessori.gripper_feedback import (
    GraspVerdict,
    GripperJointStateListener,
    GripperSlipEvent,
    LiveGraspGuard,
    confirm_grasp,
    reclose_setpoint_for,
)
from experiments.tracy_experiments.pickup.perceived_sorting import (
    Insertion,
    PerceivedSorting,
    ShapeSorter,
)
from experiments.tracy_experiments.robotiq_gripper import RobotiqGripperController
from experiments.tracy_experiments.rosbag_recording import (
    DECIMATED_TOPICS,
    DEFAULT_BAG_DIRECTORY,
    DEFAULT_KEEP_EVERY_NTH_FRAME,
    RosbagRecorder,
    RosbagRecordingProcess,
)
from segmind.datastructures.events import (
    DetectionEvent,
    GraspEvent,
    LiftEvent,
    LossOfGraspEvent,
    LossOfSupportEvent,
    PickUpEvent,
    SupportEvent,
)
from segmind.detectors.base import SegmindContext
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

NODE_NAME = "tracy_pickup_demo_real"
"""
The name this demo's node registers under.
"""

PICK_ARM = Arms.LEFT
"""
Which arm sorts every piece.
"""

GRASP_HEIGHT_OFFSET = 0.04
"""
Height, in metres, the reach, grasp and lift are aimed above a loose piece's own centre.

A perceived piece stands resting on the table where the look saw it, so the model sits
where the real object does and SegMind's own model-based support and contact detectors
see it on the table. This offset then lifts the grasp target back up by the same
distance the pieces used to be spawned hovering, so the arm still reaches where it did
before the spawn was lowered. A starting point to tune on hardware, not a measured
value.
"""

SLIP_WATCH_INTERVAL_SECONDS = 1.0
"""
Seconds between the slip watch's re-closes while a piece is carried to its hole (see
:class:`~experiments.tracy_experiments.montessori.gripper_feedback.LiveGraspGuard`).
"""

SCENARIO_NAME = "the robot sorts the pieces it saw"
"""
What the episode a run records calls its scenario, the same as its simulated twin.
"""

DEFAULT_PIECE_ASKED_ABOUT = MontessoriShapeCategory.CUBE
"""
The piece the question set is asked about at the end of the run unless told otherwise.
"""

BAG_NAME_PREFIX = "tracy_pickup_demo"
"""
Leading part of the recorded bag's directory name, completed with a timestamp so
consecutive runs do not collide.
"""

PERTURBATIONS_A_PERSON_BRINGS_ABOUT = (
    PerturbationChoice.PIECE_SHOVED,
    PerturbationChoice.TARGET_HOLE_MOVED,
)
"""
The perturbations this demo offers: the ones that are events of the scene, which the
person at the table brings about.

A perturbation of what the camera reports is the recorder's, in simulation.
"""

PERTURBATION_STEP = SortingStep.PICK_UP
"""
The step a perturbation of this demo strikes before: the person acts once the arm is
parked and before the first piece is picked up.
"""


class DemoOption(StrEnum):
    """
    The command line options, as they are spelled.
    """

    ASK_ABOUT = "--ask-about"
    PERTURBATION = "--perturbation"
    PIECE = "--piece"
    RECORD = "--record"
    BAG_DIRECTORY = "--bag-directory"
    KEEP_EVERY_NTH_FRAME = "--keep-every-nth-frame"
    DATABASE_URI = "--database-uri"
    NO_EPISODE = "--no-episode"


def _grasp_target_pose(body: Body, grasp_height_offset: float, world: World) -> Pose:
    """
    :return: The pose the reach, grasp and lift are aimed at: ``body``'s own position in
        the world, raised by ``grasp_height_offset`` (see :data:`GRASP_HEIGHT_OFFSET`),
        held at the identity orientation.

    A perceived piece can land turned any way it happens to rest, and the reach is not
    aimed at that turn: every piece is reached the same way round, whatever the look
    found its own orientation to be, and
    :class:`~coraplex.datastructures.grasp.GraspDescription` alone decides how the
    gripper is turned to it.
    """
    position = body.global_transform.to_position()
    return Pose.from_xyz_rpy(
        float(position.x),
        float(position.y),
        float(position.z) + grasp_height_offset,
        reference_frame=world.root,
    )


def _reach_action_for(
    piece: MontessoriShape, target_pose: Pose, grasp_description: GraspDescription
) -> ReachAction:
    """
    :return: The reach that aims :data:`PICK_ARM` at ``target_pose`` to grasp ``piece``.
    """
    return ReachAction(
        target_pose=target_pose,
        object_designator=piece,
        arm=PICK_ARM,
        grasp_description=grasp_description,
    )


REPORTED_PICK_EVENT_TYPES: tuple[type, ...] = (
    SupportEvent,
    LossOfSupportEvent,
    GraspEvent,
    LossOfGraspEvent,
    LiftEvent,
    PickUpEvent,
)
"""
Event types :func:`_log_pick_events` reports a yes/no on after each piece's pick.
"""


def _log_pick_events(body: Body, monitor: MontessoriEventMonitor) -> None:
    """
    Log which of :data:`REPORTED_PICK_EVENT_TYPES` SegMind detected for ``body``.

    :param body: The piece's body the monitor tracked.
    :param monitor: The stopped monitor that tracked it.
    """
    events = monitor.events

    def detected(event_type: type) -> bool:
        return any(
            isinstance(event, event_type) and event.tracked_object is body
            for event in events
        )

    verdicts = ", ".join(
        f"{event_type.__name__}={detected(event_type)}"
        for event_type in REPORTED_PICK_EVENT_TYPES
    )
    logger.info("segmind for %s: %s", body.name, verdicts)


@dataclass
class _SortingRig(ShapeSorter):
    """
    The fixed parts every pick-and-place in this demo shares, so one piece can be
    sorted with a single call: Giskard drives the arm and the Robotiq action server the
    gripper.
    """

    context: Context
    """
    Plan context bound to the live world and robot.
    """

    world: World
    """
    The live, fetched world.
    """

    robot: Tracy
    """
    The robot doing the sorting, for the SegMind grasp and lift detectors.
    """

    feed: EventFeed
    """
    Sink the per-piece SegMind events are streamed to for the live dashboard.
    """

    gripper: RobotiqGripperController
    """
    Direct Robotiq gripper control, bypassing Giskard.
    """

    gripper_listener: GripperJointStateListener
    """
    Live knuckle-position feed for the pick arm, read by the slip watch.
    """

    grasp_description: GraspDescription
    """
    Grasp used for every piece.
    """

    tool_frame: Body
    """
    The picking arm's tool frame, the parent a grasped piece is attached to.
    """

    close_table: GraspCloseTable = field(default_factory=GraspCloseTable)
    """
    Per-piece close setpoint the grasp is sized to.
    """

    grasp_height_offset: float = GRASP_HEIGHT_OFFSET
    """
    Height the reach, grasp and lift are aimed above a piece's own centre.
    """

    slip_watch_interval: float = SLIP_WATCH_INTERVAL_SECONDS
    """
    Seconds between the slip watch's re-closes while carrying a piece.
    """

    observer: EpisodeObserver = field(default_factory=EpisodeObserver)
    """
    What keeps, for the episode the run records, every plan this rig performs and every
    event its monitors report.
    """

    asks: Optional[QuestionAfterTheMove] = None
    """
    What asks the question set once the piece asked about has come to rest, or None for
    a run that asks it some other way.
    """

    def __post_init__(self) -> None:
        """
        Have every plan this rig performs hand the motion state charts it runs to the
        observer, so the trial keeps them as its motions.
        """
        self.context.motion_listener = ObserverMotionListener(observer=self.observer)

    def sort(self, piece: MontessoriShape, insertion: Insertion) -> None:
        """
        Pick ``piece`` off the table and let it go over the hole it belongs in.

        The gripper is opened and closed through :attr:`gripper` rather than a plan
        node, since Giskard cannot command Tracy's real fingers, and the close is sized
        to the piece's kind via :attr:`close_table`. The reach and lift are aimed
        :attr:`grasp_height_offset` above the piece's own centre, since the piece stands
        resting on the table.

        :param piece: The piece to sort, standing on the table where the look saw it.
        :param insertion: The hole it goes through and how far above it it is let go.
        """
        body = piece.root
        release_pose = insertion.release_pose(self.world)
        grasp_target = _grasp_target_pose(body, self.grasp_height_offset, self.world)
        reach = _reach_action_for(piece, grasp_target, self.grasp_description)
        _, _, lift_to_pose = self.grasp_description.pose_sequence(grasp_target, body)
        transport_pose, placing_pose, retract_pose = (
            self.grasp_description.pose_sequence(release_pose, body, reverse=True)
        )

        reach_plan = sequential([reach], context=self.context).plan
        lift = sequential(
            [
                ReAttachNode(body=body, new_parent=self.tool_frame),
                MoveToolCenterPointMotion(
                    lift_to_pose,
                    PICK_ARM,
                    allow_gripper_collision=True,
                    movement_type=MovementType.TRANSLATION,
                ),
            ],
            context=self.context,
        ).plan
        place = sequential(
            [
                MoveToolCenterPointMotion(
                    transport_pose, PICK_ARM, allow_gripper_collision=False
                ),
                MoveToolCenterPointMotion(
                    placing_pose,
                    PICK_ARM,
                    allow_gripper_collision=True,
                    movement_type=MovementType.CARTESIAN,
                ),
            ],
            context=self.context,
        ).plan
        retract_and_park = sequential(
            [
                ReAttachNode(body=body, new_parent=self.world.root),
                MoveToolCenterPointMotion(
                    retract_pose,
                    PICK_ARM,
                    allow_gripper_collision=True,
                    movement_type=MovementType.TRANSLATION,
                ),
                # Park before the next piece so the arm clears the board on its way
                # back to the table instead of dragging the gripper across it.
                ParkArmsAction(PICK_ARM),
            ],
            context=self.context,
        ).plan

        monitor = build_pick_monitor(
            world=self.world, tracked_body=body, robot=self.robot, arm=PICK_ARM
        )
        piece_name = body.name.name
        monitor.context.require_extension(SegmindContext).logger.add_callback(
            DetectionEvent,
            lambda event, name=piece_name: self.note_event(name, event),
        )
        close_setpoint = self.close_table.setpoint_for(piece.shape_category)
        monitor.start()
        try:
            self.gripper.move(PICK_ARM, GripperState.OPEN)
            self.perform_and_record(reach_plan)
            self.gripper.close_to(PICK_ARM, close_setpoint)
            self.perform_and_record(lift)
            self._carry_watching_for_slip(
                body, close_setpoint, lambda: self.perform_and_record(place)
            )
            self.gripper.move(PICK_ARM, GripperState.OPEN)
            self.perform_and_record(retract_and_park)
        finally:
            monitor.stop()
        _log_pick_events(body, monitor)

    def perform_and_record(self, plan) -> None:
        """
        Perform one plan and keep it for the episode, its nodes carrying when they ran.

        :param plan: The plan to perform.
        """
        plan.perform()
        self.observer.performed(plan)

    def note_event(self, piece_name: str, event: DetectionEvent) -> None:
        """
        Pass one event a monitor reported on to the dashboard, and keep it as a tick of
        the episode's trial stamped with the moment it arrived.

        :param piece_name: The piece the event is about, as the dashboard names it.
        :param event: The event.
        """
        self.feed.publish(piece_name, event)
        self.observer.tick(self.observer.elapsed_seconds, [event])
        if self.asks is not None:
            self.asks.receive([event])

    @contextlib.contextmanager
    def watching(self, things: Sequence[PrefixedName]) -> Iterator[None]:
        """
        Watch the named things for the length of the block, seen where they rest before
        it and again after it, so what someone moves while nothing of the robot moves is
        reported as a translation of what they moved.

        :param things: What is watched, named as the scene names it.
        """
        monitor = build_translation_monitor(
            world=self.world,
            tracked_bodies=[
                self.world.get_kinematic_structure_entity_by_name(name)
                for name in things
            ],
        )
        monitor.context.require_extension(SegmindContext).logger.add_callback(
            DetectionEvent,
            lambda event: self.note_event(event.tracked_object.name.name, event),
        )
        monitor.tick()
        yield
        monitor.tick()

    def _carry_watching_for_slip(
        self, body: Body, close_setpoint: float, carry: Callable[[], None]
    ) -> None:
        """
        Run ``carry`` -- the transport and release -- while watching the left gripper's
        knuckle joint for ``body`` slipping out.

        The knuckle is read as soon as the lift finishes: an empty gripper (the grasp
        missed) skips the watch. Otherwise a re-close just past ``close_setpoint`` is
        commanded every :attr:`slip_watch_interval` seconds for as long as ``carry``
        runs; each poll's verdict is logged, and a slip also streams a
        :class:`~experiments.tracy_experiments.montessori.gripper_feedback.
        GripperSlipEvent` to the dashboard.

        :param body: The piece being carried.
        :param close_setpoint: The piece's own close setpoint, used to size the slip
            watch's periodic re-close.
        :param carry: Runs the transport-and-place motion.
        """
        piece_name = body.name.name
        confirmation = confirm_grasp(self.gripper_listener.latest_closure)
        logger.info("%s: grasp check -> %s.", piece_name, confirmation.verdict)
        if confirmation.slip_detector is None:
            carry()
            return

        guard = LiveGraspGuard(
            controller=self.gripper,
            listener=self.gripper_listener,
            arm=PICK_ARM,
            slip_detector=confirmation.slip_detector,
            period=self.slip_watch_interval,
            reclose_setpoint=reclose_setpoint_for(close_setpoint),
        )
        carry_done = threading.Event()
        watcher = threading.Thread(
            target=guard.watch,
            args=(
                lambda: not carry_done.is_set(),
                lambda verdict: self._report_slip_verdict(body, verdict),
            ),
            daemon=True,
            name=f"slip-watch-{piece_name}",
        )
        watcher.start()
        try:
            carry()
        finally:
            carry_done.set()
            watcher.join(timeout=2.0)

    def _report_slip_verdict(self, body: Body, verdict: GraspVerdict) -> None:
        """
        Log one slip-watch poll and, if ``body`` has slipped, stream a
        :class:`~experiments.tracy_experiments.montessori.gripper_feedback.
        GripperSlipEvent` for it to the dashboard.

        :param body: The piece being carried.
        :param verdict: The poll's held-or-slipped verdict.
        """
        logger.info("%s: slip watch -> %s.", body.name.name, verdict)
        if verdict is GraspVerdict.OBJECT_SLIPPED:
            self.feed.publish(body.name.name, GripperSlipEvent(tracked_object=body))


def piece_asked_about(
    sorting: PerceivedSorting, category: MontessoriShapeCategory
) -> MontessoriShape:
    """
    The piece the look found of the given kind, which the run is asked about.

    :param sorting: The run, once it has looked.
    :param category: The kind of piece.
    :raises PieceNotSeenError: If the look found no piece of that kind.
    """
    for piece in sorting.pieces:
        if piece.shape_category is category:
            return piece
    raise PieceNotSeenError(category=category)


def question_set_about(
    sorting: PerceivedSorting,
    piece: MontessoriShape,
    robot: Tracy,
    scene: Optional[SceneAsSetUp],
) -> QuestionSet:
    """
    The working-memory question set, asked about one of the pieces the look found,
    placed against the next one, from where the robot stands, and scored against the
    scene as whoever set it up states it.

    :param sorting: The run, once it has looked.
    :param piece: The piece the questions single out.
    :param robot: The robot the questions are put to.
    :param scene: The scene as the person at the table states it, or None where nobody
        can, which leaves out every question scored against it.
    """
    others = [other for other in sorting.pieces if other is not piece]
    compared_against = others[0] if others else sorting.board
    return QuestionSet.over_working_memory(
        QuestionedThings(
            object_asked_about=piece.root,
            object_compared_against=compared_against.root,
            object_in_the_hand=piece.root,
            own_body_asked_about=ViewManager.get_end_effector_view(
                PICK_ARM, robot
            ).tool_frame.name,
            point_of_view=HomogeneousTransformationMatrix(
                robot.root.global_transform.to_np()
            ),
            scene=scene,
        )
    )


@dataclass
class PieceNotSeenError(DataclassException):
    """
    Raised when the run is asked about a kind of piece the look did not find.
    """

    category: MontessoriShapeCategory
    """
    The kind of piece asked about.
    """

    def error_message(self) -> str:
        return "The look found no %s to ask about." % self.category.value

    def suggest_correction(self) -> str:
        return (
            "Ask about a piece standing on the table, or put one of that kind there "
            "before the look."
        )


def outcome_of(trial_events, asked_about: Body) -> TrialOutcome:
    """
    Whether the run picked the piece it was asked about up, as its monitors saw it.

    :param trial_events: Every event the run's monitors reported.
    :param asked_about: The piece the run is asked about.
    """
    picked_up = any(
        isinstance(event, PickUpEvent) and event.tracked_object is asked_about
        for event in trial_events
    )
    return TrialOutcome.SUCCEEDED if picked_up else TrialOutcome.FAILED


def perturbation_asked_for(
    choice: Optional[PerturbationChoice], piece: MontessoriShapeCategory
) -> Optional[SortingPerturbation]:
    """
    The perturbation the command line asked for, aimed at the piece it named and due
    before the sort, or None for an unperturbed run.

    :param choice: The perturbation asked for, or None.
    :param piece: The piece it is aimed at.
    """
    if choice is None:
        return None
    return choice.aimed_at(piece, PERTURBATION_STEP)


@dataclass
class SortingTrial:
    """
    The one trial a run of this demo records: the account of the table the person at it
    gives, the perturbation they bring about, the sorting itself, and the question set
    asked once the piece asked about has come to rest.
    """

    rig: _SortingRig
    """
    What sorts each piece, and observes everything the trial records.
    """

    sorting: PerceivedSorting
    """
    The run, once it has looked: the board and the pieces as the camera found them.
    """

    person: Person
    """
    The person at the table, who says what they placed and brings the perturbation
    about.
    """

    asked_about: MontessoriShapeCategory
    """
    The kind of piece the question set is asked about.
    """

    perturbation: Optional[SortingPerturbation] = None
    """
    What someone other than the robot does to the table before the sort, or None for an
    unperturbed run.
    """

    stated_scene: Optional[SceneAsSetUp] = field(init=False, default=None)
    """
    The table as the person at it states it, once asked, or None where nobody can say.
    """

    joints: Optional[JointTraceRecorder] = field(init=False, default=None)
    """
    What traces where every joint stands while the trial runs, once it has begun.
    """

    def episode(self) -> Episode:
        """
        The episode this trial is the one trial of, naming the perturbation it runs
        under and keeping the world it runs in.
        """
        perturbations = [] if self.perturbation is None else [self.perturbation]
        return Episode(
            scenario_name=SCENARIO_NAME,
            execution_type=ExecutionType.REAL,
            perturbation_names=[
                type(perturbation).__name__ for perturbation in perturbations
            ],
            world=self.rig.world,
        )

    def begin(self) -> None:
        """
        Start the trial's clock and trace the joints against it.

        Every moment the trial records -- a tick, a query, a motion, a joint sample --
        is seconds from now, and the trial says when now was on the wall clock, which is
        the clock the bag stamps its messages on.
        """
        self.rig.observer.restart()
        self.joints = JointTraceRecorder(
            _world=self.rig.world, clock=lambda: self.rig.observer.elapsed_seconds
        )
        # A still robot changes no joint, so where the joints stand is read once here
        # or a trial that moves nothing would keep no trace at all.
        self.joints.trace.sample(self.rig.world, self.rig.observer.elapsed_seconds)

    def state_the_scene(self) -> None:
        """
        Ask the person at the table which pieces they placed, and keep the table as they
        state it.
        """
        self.stated_scene = SceneThePersonSetUp(self.person).stated_over(
            SortingScene(self.rig.world)
        )

    def bring_about_the_perturbation(self) -> None:
        """
        Have the person bring the perturbation about, if there is one: the account stops
        saying where what they are to move stands, the trial keeps what they were told
        with what it moves and when, they are told what to do, and the camera looks at
        the table again to learn what they did.

        What they move is watched from before they act until the camera has found it
        again, since nothing of the robot moves meanwhile to watch it otherwise. It is
        named off the table as it stood before they acted, since what the look then
        finds of it is the look's to say.
        """
        if self.perturbation is None:
            return
        instruction = self.perturbation.instruction_for_a_person()
        things_moved = self.perturbation.things_moved(SortingScene(self.rig.world))
        if self.stated_scene is not None:
            for moved in things_moved:
                self.stated_scene.forget_where(moved)
        self.rig.observer.carried_out(
            instruction, self.rig.observer.elapsed_seconds, things_moved
        )
        with self.rig.watching(things_moved):
            self.person.carry_out(instruction)
            self.sorting.perceive()

    @property
    def piece_asked_about(self) -> MontessoriShape:
        """
        The piece the question set is asked about, as the latest look found it.

        :raises PieceNotSeenError: If the look found no piece of the kind asked about.
        """
        return piece_asked_about(self.sorting, self.asked_about)

    def question_set(self) -> QuestionSet:
        """
        The working-memory question set about the piece asked about, scored against the
        table as the person states it.

        :raises PieceNotSeenError: If the look found no piece of the kind asked about.
        """
        return question_set_about(
            self.sorting, self.piece_asked_about, self.rig.robot, self.stated_scene
        )

    def perform(self) -> None:
        """
        Run the trial: take the person's account, have them bring the perturbation
        about, sort every piece and ask the question set once the piece asked about has
        come to rest -- or at the end, if it never does.

        :raises PieceNotSeenError: If the look found no piece of the kind asked about.
        """
        self.state_the_scene()
        self.bring_about_the_perturbation()
        self.rig.asks = QuestionAfterTheMove(
            observer=self.rig.observer,
            asked_about=self.piece_asked_about.root,
            question_set=self.question_set,
            robot=self.rig.robot,
        )
        self.sorting.sort_every_piece()
        self.rig.asks.ask_if_not_yet()

    @property
    def outcome(self) -> TrialOutcome:
        """
        Whether the run picked the piece it was asked about up, as its monitors saw it.
        """
        return outcome_of(
            [event for tick in self.rig.observer.ticks for event in tick.events],
            self.piece_asked_about.root,
        )

    def finish(self, episode: Episode) -> RecordedTrial:
        """
        Stop tracing the joints and record the trial with everything observed in it.

        :param episode: The episode the trial belongs to.
        :return: The trial, carrying when it began, its ticks, queries, plans, motions
            and the instruction carried out on its table.
        """
        self.joints.stop()
        return self.rig.observer.into(
            RecordedTrial(
                episode=episode,
                outcome=self.outcome,
                duration=self.rig.observer.elapsed_seconds,
            )
        )


def _parse_arguments(argument_list: Optional[Sequence[str]]) -> argparse.Namespace:
    """
    :param argument_list: Arguments to read; the process's own when None.
    :return: The demo's own command line arguments.
    """
    return argument_parser().parse_args(argument_list)


def argument_parser(add_help: bool = True) -> argparse.ArgumentParser:
    """
    The demo's own command line.

    :param add_help: Whether the parser answers ``--help`` itself; not when it is the
        parent of another command line.
    """
    parser = argparse.ArgumentParser(
        description="Sort the Montessori pieces with the physical Tracy by looking.",
        add_help=add_help,
    )
    parser.add_argument(
        DemoOption.ASK_ABOUT,
        type=MontessoriShapeCategory,
        choices=list(MontessoriShapeCategory),
        default=DEFAULT_PIECE_ASKED_ABOUT,
        help="the piece the question set is asked about once the sorting is done",
    )
    parser.add_argument(
        DemoOption.PERTURBATION,
        type=PerturbationChoice,
        choices=list(PERTURBATIONS_A_PERSON_BRINGS_ABOUT),
        default=None,
        help=(
            "what the person at the table is asked to do before the sort; the trial "
            "keeps what they were told and the episode names it"
        ),
    )
    parser.add_argument(
        DemoOption.PIECE,
        type=MontessoriShapeCategory,
        choices=list(MontessoriShapeCategory),
        default=DEFAULT_PIECE,
        help="the piece the perturbation is aimed at",
    )
    parser.add_argument(
        DemoOption.RECORD,
        action="store_true",
        help=(
            "Record a rosbag of the camera, depth camera, joint states and transforms "
            "for the duration of the sorting."
        ),
    )
    parser.add_argument(
        DemoOption.BAG_DIRECTORY,
        default=DEFAULT_BAG_DIRECTORY,
        help=(
            f"Directory the recorded bag is placed in. Default: "
            f"{DEFAULT_BAG_DIRECTORY}."
        ),
    )
    parser.add_argument(
        DemoOption.KEEP_EVERY_NTH_FRAME,
        type=int,
        default=DEFAULT_KEEP_EVERY_NTH_FRAME,
        metavar="N",
        help=(
            f"Record only one in every N frames of the heavy camera streams "
            f"({', '.join(DECIMATED_TOPICS)}). Joint states and transforms are always "
            f"recorded whole. Pass 1 to record every frame. Default: "
            f"{DEFAULT_KEEP_EVERY_NTH_FRAME}."
        ),
    )
    parser.add_argument(
        DemoOption.DATABASE_URI,
        default=None,
        help=(
            "Database the episode is recorded to; the MONTESSORI_SORTING_DATABASE_URI "
            "environment variable or the built-in default otherwise. A database that "
            "cannot be reached or would live only in memory is refused before the "
            "robot moves."
        ),
    )
    parser.add_argument(
        DemoOption.NO_EPISODE,
        action="store_true",
        help=(
            "Keep no episode: nothing is written to a database or beside it, and no "
            "database is checked. A bag asked for with --record is still recorded and "
            "stays in its bag directory."
        ),
    )
    return parser


CHECK_THE_SCENE = (
    "Board and %d perceived piece(s) in rviz. Check they line up with the real objects "
    "before the sorting runs."
)
"""
What the person at the console is asked to do once the camera has stood the scene, with
how many pieces it found.
"""


@dataclass
class PickupDemo:
    """
    The run of this demo over a connected Tracy: look, have the scene checked, sort
    every piece the look found as one recorded trial, and keep the episode.

    What the run reaches the robot through -- the connection, the grippers' drivers, the
    camera -- is the robot's own; how the arm's motions are run is
    :attr:`motion_execution`'s.
    """

    tracy: LiveTracy
    """
    The robot, connected.
    """

    person: Person
    """
    The person at the console and the table: checks the scene, says what they placed and
    brings the perturbation about.
    """

    database: Optional[ResultsDatabase]
    """
    The database the episode is recorded to, or None for a run that keeps no episode.
    """

    asked_about: MontessoriShapeCategory = DEFAULT_PIECE_ASKED_ABOUT
    """
    The kind of piece the question set is asked about.
    """

    perturbation: Optional[SortingPerturbation] = None
    """
    What the person at the table is asked to do before the sort, or None for an
    unperturbed run.
    """

    bag: Optional[RosbagRecorder] = None
    """
    The bag the run records for as long as the sorting runs, or None to record none.
    """

    motion_execution: ExecutionType = ExecutionType.REAL
    """
    How the arm's motions are run: on the robot through Giskard's node, or ticked in
    this process against the world's own joints.
    """

    artifact_directory: ArtifactDirectory = field(default_factory=ArtifactDirectory)
    """
    Where the episode's artifacts are kept.
    """

    feed: EventFeed = field(default_factory=EventFeed)
    """
    Where the events the rig's monitors report are streamed to.
    """

    def run(self) -> Optional[EpisodeArtifacts]:
        """
        Sort the pieces the camera finds, recording the episode.

        The bag opens before the trial's clock starts and closes after it has stopped,
        so the recording spans the whole trial; the trial's clock runs on the same wall
        clock the bag stamps its messages on, so the two are read against one another
        through the trial's start.

        :return: The artifacts the episode kept, or None for a run that keeps no
            episode.
        :raises PieceNotSeenError: If the look found no piece of the kind asked about.
        """
        tracy = self.tracy
        context = Context(
            world=tracy.world,
            robot=tracy.robot,
            ros_node=tracy.node,
            evaluate_conditions=False,
        )
        grasp_description = GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.TOP,
            ViewManager.get_end_effector_view(PICK_ARM, tracy.robot),
            rotate_gripper=True,
        )

        # Giskard's Tracy interface has no command channel for the gripper fingers, so
        # a plan's own MoveGripperMotion blocks forever on the real robot. The arm
        # motion still runs through the plan; the gripper is driven straight through
        # its Robotiq action server instead.
        gripper = RobotiqGripperController(tracy.node)
        gripper_listener = GripperJointStateListener(node=tracy.node, arm=PICK_ARM)
        tool_frame = ViewManager.get_end_effector_view(PICK_ARM, tracy.robot).tool_frame
        rig = _SortingRig(
            context,
            tracy.world,
            tracy.robot,
            self.feed,
            gripper,
            gripper_listener,
            grasp_description,
            tool_frame,
        )
        sorting = PerceivedSorting(
            scene=PerceivedScene(
                world=tracy.world,
                look=tracy.look,
                described_board=lab_board(),
                looks_for_board=LOOKS_FOR_THE_BOARD,
            ),
            sorter=rig,
        )
        sorting.perceive()

        park = sequential([ParkArmsAction(PICK_ARM)], context=context).plan

        self.person.carry_out(CHECK_THE_SCENE % len(sorting.pieces))
        logger.info("Sorting %d piece(s).", len(sorting.pieces))
        trial = SortingTrial(
            rig=rig,
            sorting=sorting,
            person=self.person,
            asked_about=self.asked_about,
            perturbation=self.perturbation,
        )
        episode = trial.episode()
        recorder = (
            contextlib.nullcontext()
            if self.bag is None
            else RosbagRecordingProcess(self.bag)
        )
        with (
            recorder as bag,
            ExecutionEnvironment(
                execution_type=self.motion_execution, collision_avoidance=False
            ),
        ):
            trial.begin()
            rig.perform_and_record(park)
            trial.perform()
            recorded = trial.finish(episode)
        logger.info("Sorting finished.")
        # Keeping the episode rewrites where the world's meshes are read from, which a
        # look still copying the world would read half-written.
        tracy.look.stop_looking()
        return self.keep(
            recorded,
            trial.joints.trace,
            None if bag is None else Path(bag.output_directory),
        )

    def keep(
        self,
        trial: RecordedTrial,
        joints: JointTrace,
        bag_directory: Optional[Path],
    ) -> Optional[EpisodeArtifacts]:
        """
        Keep the episode of the finished trial, unless this run keeps none.

        :param trial: The trial the run recorded.
        :param joints: The trace of where every joint stood along it.
        :param bag_directory: The bag the run recorded, or None for a run that recorded
            none.
        :return: The artifacts that were kept, or None for a run that keeps no episode.
        """
        if self.database is None:
            logger.info("No episode kept, as asked.")
            return None
        return keep_the_episode(
            trial, joints, bag_directory, self.database, self.artifact_directory
        )


def main(argument_list: Optional[Sequence[str]] = None) -> None:
    """
    Sort the pieces the camera finds with the physical Tracy, recording the episode.

    :param argument_list: Arguments to read; the process's own when omitted.
    :raises InMemoryDatabaseRefused: If the episode would be recorded to a database that
        dies with the run, before anything on the robot is touched.
    """
    arguments = _parse_arguments(argument_list)
    database = database_asked_for(arguments)
    perturbation = perturbation_asked_for(arguments.perturbation, arguments.piece)
    bag = bag_asked_for(arguments)

    feed = EventFeed()
    run_dashboard(feed)

    rclpy.init()
    with LiveTracy.connected(NODE_NAME) as tracy:
        PickupDemo(
            tracy=tracy,
            person=PersonAtTheConsole(),
            database=database,
            asked_about=arguments.ask_about,
            perturbation=perturbation,
            bag=bag,
            feed=feed,
        ).run()


def database_asked_for(arguments: argparse.Namespace) -> Optional[ResultsDatabase]:
    """
    The database the command line asked the episode to be recorded to, or None for a run
    that keeps no episode.

    :param arguments: The command line as read.
    :raises InMemoryDatabaseRefused: If the episode would be recorded to a database that
        dies with the run.
    """
    if arguments.no_episode:
        return None
    return resolve_lasting_database(arguments.database_uri)


def bag_asked_for(arguments: argparse.Namespace) -> Optional[RosbagRecorder]:
    """
    The bag the command line asked the run to record, or None for a run that records
    none.

    :param arguments: The command line as read.
    """
    if not arguments.record:
        return None
    return RosbagRecorder.timestamped(
        BAG_NAME_PREFIX,
        arguments.bag_directory,
        keep_every_nth_frame=arguments.keep_every_nth_frame,
    )


def keep_the_episode(
    trial: RecordedTrial,
    joints: JointTrace,
    bag_directory: Optional[Path],
    database: ResultsDatabase,
    artifact_directory: Optional[ArtifactDirectory] = None,
) -> EpisodeArtifacts:
    """
    Record the trial to the database the run was checked against and keep the run's
    artifacts beside it: the transcript, the trace of the joints, and the bag if one
    was recorded.

    :param trial: The trial the run recorded.
    :param joints: The trace of where every joint stood along it.
    :param bag_directory: The bag the run recorded, or None for a run that recorded
        none.
    :param database: The database the trial is recorded to.
    :param artifact_directory: Where the artifacts are kept; the configured directory
        when None.
    :return: The artifacts that were kept.
    """
    recording = open_recording(database)
    try:
        recording.record(trial)
    finally:
        recording.close()
    if artifact_directory is None:
        artifact_directory = ArtifactDirectory()
    artifacts = artifact_directory.open_for(trial.episode)
    artifacts.keep_transcript(Transcript(episode=trial.episode, trials=[trial]))
    artifacts.trial(trial.number).keep_joint_trace(joints)
    if bag_directory is not None:
        artifacts.keep_camera_recording(bag_directory)
    logger.info(
        "Episode %s recorded; artifacts in %s",
        trial.episode.identifier,
        artifacts.directory,
    )
    return artifacts


if __name__ == "__main__":
    main()
