"""
The physical Tracy's left arm sorts the loose Montessori pieces into the shape-sorting
board by looking -- wired the way :mod:`coraplex_real_tracy.demo` wires the physical
robot: a Giskard standalone node is launched, the live world is fetched from a running
``WorldFetcher`` service and kept in sync via
:class:`~semantic_digital_twin.adapters.ros. world_synchronizer.WorldSynchronizer`, and
the plan runs under :attr:`~coraplex.datastructures.enums.ExecutionType.REAL`.

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

Run with (the camera, ``iai_tracy_description`` and the Giskard/world-fetcher ROS stack
must be running)::

    python -m experiments.tracy_experiments.pickup.pickup_demo_real

Pass ``--record`` to capture a rosbag of the camera, depth camera and joint states for
the duration of the sorting. Bags are written to
:data:`~experiments.tracy_experiments.rosbag_recording.DEFAULT_BAG_DIRECTORY` and keep
one camera frame in :data:`KEEP_EVERY_NTH_FRAME`; both are overridable, see
``--bag-directory`` and ``--keep-every-nth-frame``.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format="%(message)s")

import rclpy
from rclpy.executors import MultiThreadedExecutor

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
from experiments.montessori.perception.node import build_node
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.semantics import MontessoriShape
from experiments.network_limits import check_large_messages_can_arrive
from experiments.tracy_experiments.montessori.event_dashboard import (
    EventFeed,
    run_dashboard,
)
from experiments.tracy_experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_pick_monitor,
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
    PerceivedSorting,
    ShapeSorter,
)
from experiments.tracy_experiments.robotiq_gripper import RobotiqGripperController
from experiments.tracy_experiments.rosbag_recording import (
    DECIMATED_TOPICS,
    DEFAULT_BAG_DIRECTORY,
    RosbagRecorder,
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
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
    VizMarkerPublisher,
)

logger = logging.getLogger(__name__)

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

LOOKS_FOR_THE_BOARD = 30
"""
How many looks the camera is given to show the board before the demo gives up.
"""

SLIP_WATCH_INTERVAL_SECONDS = 1.0
"""
Seconds between the slip watch's re-closes while a piece is carried to its hole (see
:class:`~experiments.tracy_experiments.montessori.gripper_feedback.LiveGraspGuard`).
"""

POST_LIFT_SETTLE_SECONDS = 5.0
"""
Seconds to hold still after the lift before the grasp is read and the slip watch starts.

The knuckle keeps moving for a moment after the piece leaves the table: the fingers take
up the piece's weight and it settles between the pads. Reading immediately catches that
transient, which both seeds
:class:`~experiments.tracy_experiments.montessori.gripper_feedback.SlipDetector` from a
position the grasp has not actually reached and risks a first poll that reads the
still-settling travel as a slip.
"""

BAG_NAME_PREFIX = "tracy_pickup_demo"
"""
Leading part of the recorded bag's directory name, completed with a timestamp so
consecutive runs do not collide.
"""

KEEP_EVERY_NTH_FRAME = 10
"""
How much of the camera streams a recorded run keeps, by default.

Recording every frame costs around 230 MB of disk per second of wall clock: a sorting
run fills tens of gigabytes, almost all of it registered depth and point cloud. One
frame in ten still shows what the arm did, at roughly a ninth of the size. Pass
``--keep-every-nth-frame 1`` for a run that genuinely needs every frame.
"""


def _grasp_target_pose(body: Body, grasp_height_offset: float) -> Pose:
    """
    :return: The pose the reach, grasp and lift are aimed at: ``body``'s own origin
        raised by ``grasp_height_offset`` (see :data:`GRASP_HEIGHT_OFFSET`).

    A perceived piece stands resting on the table, with no roll or pitch, so the offset
    along the body frame's own vertical is the offset along the world's.
    """
    return Pose.from_xyz_rpy(0.0, 0.0, grasp_height_offset, reference_frame=body)


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

    post_lift_settle: float = POST_LIFT_SETTLE_SECONDS
    """
    Seconds to let the grasp settle after the lift before it is read.
    """

    def sort(self, piece: MontessoriShape, release_pose: Pose) -> None:
        """
        Pick ``piece`` off the table and release it at ``release_pose``.

        The gripper is opened and closed through :attr:`gripper` rather than a plan
        node, since Giskard cannot command Tracy's real fingers, and the close is sized
        to the piece's kind via :attr:`close_table`. The reach and lift are aimed
        :attr:`grasp_height_offset` above the piece's own centre, since the piece stands
        resting on the table.

        :param piece: The piece to sort, standing on the table where the look saw it.
        :param release_pose: Where the piece's centre is let go, over its hole.
        """
        body = piece.root
        grasp_target = _grasp_target_pose(body, self.grasp_height_offset)
        reach = ReachAction(
            target_pose=grasp_target,
            object_designator=body,
            arm=PICK_ARM,
            grasp_description=self.grasp_description,
        )
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
            lambda event, name=piece_name: self.feed.publish(name, event),
        )
        close_setpoint = self.close_table.setpoint_for(piece.shape_category)
        monitor.start()
        try:
            self.gripper.move(PICK_ARM, GripperState.OPEN)
            reach_plan.perform()
            self.gripper.close_to(PICK_ARM, close_setpoint)
            lift.perform()
            self._carry_watching_for_slip(body, close_setpoint, place.perform)
            self.gripper.move(PICK_ARM, GripperState.OPEN)
            retract_and_park.perform()
        finally:
            monitor.stop()
        _log_pick_events(body, monitor)

    def _carry_watching_for_slip(
        self, body: Body, close_setpoint: float, carry: Callable[[], None]
    ) -> None:
        """
        Run ``carry`` -- the transport and release -- while watching the left gripper's
        knuckle joint for ``body`` slipping out.

        The grasp is first given :attr:`post_lift_settle` seconds to settle: the lift has
        just transferred the piece's weight onto the fingers and the knuckle is still
        moving, so a reading taken now would seed the slip detector from a position the
        grasp never reaches. Then the close is firmed to ``close_setpoint`` and the
        knuckle read once: an empty
        gripper (the grasp missed) skips the watch. Otherwise a re-close just past
        ``close_setpoint`` is commanded every :attr:`slip_watch_interval` seconds for as
        long as ``carry`` runs; each
        poll's verdict is logged, and a slip also streams a
        :class:`~experiments.tracy_experiments.montessori.gripper_feedback.
        GripperSlipEvent` to the dashboard.

        :param body: The piece being carried.
        :param close_setpoint: The piece's own close setpoint, re-commanded to firm the
            grasp before the knuckle is read.
        :param carry: Runs the transport-and-place motion.
        """
        piece_name = body.name.name
        time.sleep(self.post_lift_settle)
        self.gripper.close_to(PICK_ARM, close_setpoint)
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


def _parse_arguments() -> argparse.Namespace:
    """
    :return: The demo's own command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Sort the Montessori pieces with the physical Tracy by looking."
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help=(
            "Record a rosbag of the camera, depth camera, joint states and transforms "
            "for the duration of the sorting."
        ),
    )
    parser.add_argument(
        "--bag-directory",
        default=DEFAULT_BAG_DIRECTORY,
        help=(
            f"Directory the recorded bag is placed in. Default: "
            f"{DEFAULT_BAG_DIRECTORY}."
        ),
    )
    parser.add_argument(
        "--keep-every-nth-frame",
        type=int,
        default=KEEP_EVERY_NTH_FRAME,
        metavar="N",
        help=(
            f"Record only one in every N frames of the heavy camera streams "
            f"({', '.join(DECIMATED_TOPICS)}). Joint states and transforms are always "
            f"recorded whole. Pass 1 to record every frame. Default: "
            f"{KEEP_EVERY_NTH_FRAME}."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()

    feed = EventFeed()
    run_dashboard(feed)

    check_large_messages_can_arrive()
    rclpy.init()
    node = rclpy.create_node("tracy_pickup_demo_real")
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    thread.start()

    world = fetch_world_from_service(node=node, timeout_seconds=300)
    [robot] = world.get_semantic_annotations_by_type(Tracy)

    # Build the rviz marker + tf publisher before the WorldSynchronizer exists.
    # TFPublisher registers a state-change callback partway through its own
    # construction; a sync update landing in that window reaches it before its
    # tf_model_callback is set and takes down the executor thread.
    viz_marker_publisher = VizMarkerPublisher(_world=world, node=node)

    WorldSynchronizer(_world=world, node=node)

    context = Context(
        world=world, robot=robot, ros_node=node, evaluate_conditions=False
    )
    grasp_description = GraspDescription(
        ApproachDirection.FRONT,
        VerticalAlignment.TOP,
        ViewManager.get_end_effector_view(PICK_ARM, robot),
        rotate_gripper=True,
    )

    # Giskard's Tracy interface has no command channel for the gripper fingers, so a
    # plan's own MoveGripperMotion blocks forever on the real robot. The arm motion
    # still runs through the plan; the gripper is driven straight through its Robotiq
    # action server instead.
    gripper = RobotiqGripperController(node)
    gripper_listener = GripperJointStateListener(node=node, arm=PICK_ARM)
    tool_frame = ViewManager.get_end_effector_view(PICK_ARM, robot).tool_frame
    rig = _SortingRig(
        context,
        world,
        robot,
        feed,
        gripper,
        gripper_listener,
        grasp_description,
        tool_frame,
    )
    sorting = PerceivedSorting(
        world=world,
        look=build_node(node, world),
        described_board=lab_board(),
        sorter=rig,
        looks_for_board=LOOKS_FOR_THE_BOARD,
    )
    sorting.perceive()

    park = sequential([ParkArmsAction(PICK_ARM)], context=context).plan

    logger.info(
        "Board and %d perceived piece(s) in rviz. Check they line up with the real "
        "objects, then press Enter to run the sorting.",
        len(sorting.pieces),
    )
    input()
    logger.info("Sorting %d piece(s) on the real robot.", len(sorting.pieces))
    # Recording starts here rather than at start-up so the bag holds the sorting itself,
    # not the operator's wait at the prompt above, and closes as soon as the last piece
    # is placed.
    recorder = (
        RosbagRecorder.timestamped(
            BAG_NAME_PREFIX,
            arguments.bag_directory,
            keep_every_nth_frame=arguments.keep_every_nth_frame,
        )
        if arguments.record
        else contextlib.nullcontext()
    )
    with (
        recorder,
        ExecutionEnvironment(
            execution_type=ExecutionType.REAL, collision_avoidance=True
        ),
    ):
        park.perform()
        sorting.sort_every_piece()
    logger.info("Sorting finished.")


if __name__ == "__main__":
    main()
