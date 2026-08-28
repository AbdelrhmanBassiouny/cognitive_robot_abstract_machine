"""
The physical Tracy's left arm picks up a single cube -- pickup only, no place -- wired
the way :mod:`coraplex_real_tracy.demo` wires the physical robot: a Giskard standalone
node is launched, the live world is fetched from a running ``WorldFetcher`` service and
kept in sync via :class:`~semantic_digital_twin.adapters.ros.
world_synchronizer.WorldSynchronizer`, and the plan runs under
:attr:`~coraplex.datastructures.enums.ExecutionType.REAL`.

The cube is added to the live, fetched world as a plain
:class:`~semantic_digital_twin.world_description.world_entity.Body`, the same
symbolic-anchor trick :mod:`~experiments.tracy_experiments.stacking.stacking_demo_real`
uses -- it is not a perception result, so the physical cube must already be placed at
:data:`CUBE_X`/:data:`CUBE_Y` by hand before this runs. Once added it is visible in the
same rviz the physical robot renders in (via ``WorldSynchronizer``), so its position can
be checked against the real cube before the pickup runs -- the script pauses for that
check right after spawning it.

Each pick is watched by a SegMind :func:`~experiments.tracy_experiments.montessori.
event_monitoring.build_pick_monitor` monitor -- support, grasp, lift and pick-up, but
no hole-contact or insertion, since the shapes here are bare bodies with no board model.
Its events stream to the live dashboard at ``http://127.0.0.1:5000`` while the demo
runs, and a per-shape yes/no verdict is logged after each pick.

While a shape is carried to its hole, the left gripper's knuckle joint is watched for
slip: the close is re-commanded a little past fully closed on a fixed period and, if the
fingers then travel past where the grasp first settled, the shape has left the pads (see
:mod:`~experiments.tracy_experiments.montessori.gripper_feedback`). Each poll's verdict
is logged, and a slip also shows on the dashboard as a ``GripperSlipEvent``.

Run with (``iai_tracy_description`` and the Giskard/world-fetcher ROS stack must be
running)::

    python -m experiments.tracy_experiments.pickup.pickup_demo_real
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
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
from coraplex.plans.attachment_nodes import AttachNode, DetachNode
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.pick_up import ReachAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.robot_plans.motions.gripper import MoveToolCenterPointMotion
from coraplex.view_manager import ViewManager
from experiments.montessori.hole_geometry import HoleFootprint
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.world import (
    BOARD_COLOR,
    BOARD_SCALE,
    _BOARD_MESH,
    _HOLE_FOOTPRINTS,
    _board_body,
    _shape_body,
)
from experiments.tracy_experiments.equipment import table_top_z as read_table_top_z
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
from experiments.tracy_experiments.robotiq_gripper import RobotiqGripperController
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
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Mesh, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
    VizMarkerPublisher,
)

logger = logging.getLogger(__name__)

PICK_ARM = Arms.LEFT
"""
Which arm picks up the cube.
"""

CUBE_SIZE = 0.03
"""
Edge length of the cube, in metres.
"""

CUBE_X = 0.79
CUBE_Y = 0.4
"""
Where the cube must already be placed by hand before this runs, in the live world's root
frame.
"""

BOARD_X = 1.035
BOARD_Y = 0.16
"""
Where the Montessori shape-sorting board sits on the same table as the cube, in the live
world's root frame.
"""

BOARD_TABLE_CLEARANCE = 0
"""
Vertical offset added to the read table-top height when seating the board.
"""

PLACE_HOVER = 0.035
"""
Height above the board's top surface at which a shape is released over its hole.
"""

GRASP_HEIGHT_OFFSET = 0.032
"""
Height, in metres, the reach, grasp and lift are aimed above a loose shape's own centre.

The shapes and cube are spawned resting on the table (:func:`_add_montessori_shape`,
:func:`_add_cube`), so the model sits where the real object does and SegMind's own
model-based support and contact detectors see it on the table. This offset then lifts
the grasp target back up by the same distance the shapes used to be spawned hovering, so
the arm still reaches where it did before the spawn was lowered. A starting point to
tune on hardware, not a measured value.
"""

SLIP_WATCH_INTERVAL_SECONDS = 1.0
"""
Seconds between the slip watch's re-closes while a shape is carried to its hole (see
:class:`~experiments.tracy_experiments.montessori.gripper_feedback.LiveGraspGuard`).
"""

POST_LIFT_SETTLE_SECONDS = 5.0
"""
Seconds to hold still after the lift before the grasp is read and the slip watch starts.

The knuckle keeps moving for a moment after the shape leaves the table: the fingers take
up the piece's weight and it settles between the pads. Reading immediately catches that
transient, which both seeds
:class:`~experiments.tracy_experiments.montessori.gripper_feedback.SlipDetector` from a
position the grasp has not actually reached and risks a first poll that reads the
still-settling travel as a slip.
"""


@dataclass(frozen=True)
class PickTarget:
    """One loose shape to pick off the table and drop through its matching board hole."""

    name: str
    """Name of the shape's body."""

    category: MontessoriShapeCategory
    """Board hole the shape belongs to."""

    pick_y: float
    """Y of the shape on the table, in the world root frame (X is shared: :data:`CUBE_X`)."""

    half_height: float
    """
    Half the shape's own height, used to seat it on the table and above its hole; matches
    :func:`~experiments.montessori.world._shape_body`'s own per-category thickness.
    """


PICK_TARGETS: list[PickTarget] = [
    PickTarget("pickup_circle", MontessoriShapeCategory.CYLINDER, 0.5, 0.015),
    PickTarget(
        "pickup_rectangle", MontessoriShapeCategory.RECTANGULAR_PRISM, 0.3, 0.015
    ),
    PickTarget("pickup_triangle", MontessoriShapeCategory.TRIANGULAR_PRISM, 0.2, 0.01),
]
"""
Every loose shape besides the cube, in pick order. All share :data:`CUBE_X`; only the Y
differs.
"""


def _add_cube(world: World, mounted_table_top_z: float) -> Body:
    """
    Add the cube to the live, fetched world as a fixed, symbolic body at
    :data:`CUBE_X`/:data:`CUBE_Y`, resting on the live robot's own table top -- not a
    perception result, so the physical cube must already be there.

    :param world: The live world to add the cube to, modified in place.
    :param mounted_table_top_z: Height of the live robot's own table top, read via
        :func:`~experiments.tracy_experiments.equipment.table_top_z`.
    :return: The newly added cube.
    """
    cube = Body(
        name=PrefixedName("pickup_cube"),
        collision=ShapeCollection([Box(scale=Scale(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE))]),
        visual=ShapeCollection(
            [
                Box(
                    scale=Scale(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE),
                    color=Color(0.6, 0.6, 0.6),
                )
            ]
        ),
    )
    cube_center_z = mounted_table_top_z + CUBE_SIZE / 2
    with world.modify_world():
        world.add_kinematic_structure_entity(cube)
        world.add_connection(
            FixedConnection.create_with_dofs(
                parent=world.root,
                child=cube,
                world=world,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    CUBE_X, CUBE_Y, cube_center_z
                ),
            )
        )
    return cube


def _board_center_z(mounted_table_top_z: float) -> float:
    """
    :return: Z of the board's centre, seated on the same surface as the cube.
    """
    return mounted_table_top_z + BOARD_SCALE.z / 2 + BOARD_TABLE_CLEARANCE


def _hole_footprint(category: MontessoriShapeCategory) -> HoleFootprint:
    """
    :return: The board hole footprint matching ``category`` (the first, for a category
        with more than one hole).
    """
    return next(
        footprint for footprint in _HOLE_FOOTPRINTS if footprint.category is category
    )


def _hole_place_pose(
    world: World,
    mounted_table_top_z: float,
    category: MontessoriShapeCategory,
    shape_half_height: float,
) -> Pose:
    """
    :return: The pose, in the world root frame, at which a shape's centre should be
        released so it sits :data:`PLACE_HOVER` above its matching board hole.
    """
    footprint = _hole_footprint(category)
    board_top_z = _board_center_z(mounted_table_top_z) + BOARD_SCALE.z / 2
    return Pose.from_xyz_rpy(
        BOARD_X + footprint.center[0],
        BOARD_Y + footprint.center[1],
        board_top_z + shape_half_height + PLACE_HOVER,
        reference_frame=world.root,
    )


def _grasp_target_pose(body: Body, grasp_height_offset: float) -> Pose:
    """
    :return: The pose the reach, grasp and lift are aimed at: ``body``'s own origin
        raised by ``grasp_height_offset`` (see :data:`GRASP_HEIGHT_OFFSET`).

    The shapes are spawned resting on the table, with no roll or pitch, so the offset
    along the body frame's own vertical is the offset along the world's.
    """
    return Pose.from_xyz_rpy(0.0, 0.0, grasp_height_offset, reference_frame=body)


def _add_montessori_shape(
    world: World, mounted_table_top_z: float, target: PickTarget
) -> Body:
    """
    Add one loose Montessori shape to the live world as a fixed body at
    :data:`CUBE_X`/``target.pick_y``, resting on the same table as the cube.

    :param world: The live world to add the shape to, modified in place.
    :param mounted_table_top_z: Height of the live robot's own table top.
    :param target: Which shape to add and where.
    :return: The newly added shape body.
    """
    body = _shape_body(
        PrefixedName(target.name), target.category, _hole_footprint(target.category)
    )
    shape_center_z = mounted_table_top_z + target.half_height
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
        world.add_connection(
            FixedConnection.create_with_dofs(
                parent=world.root,
                child=body,
                world=world,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    CUBE_X, target.pick_y, shape_center_z
                ),
            )
        )
    return body


def _add_montessori_board(world: World, mounted_table_top_z: float) -> Body:
    """
    Add the Montessori shape-sorting board to the live, fetched world as a fixed body at
    :data:`BOARD_X`/:data:`BOARD_Y`, resting on the same table surface as the cube.

    :param world: The live world to add the board to, modified in place.
    :param mounted_table_top_z: Height of the live robot's own table top, read via
        :func:`~experiments.tracy_experiments.equipment.table_top_z`.
    :return: The newly added board body.
    """
    board_shape = Mesh.from_trimesh(mesh=_BOARD_MESH)
    board_shape.color = BOARD_COLOR
    board = _board_body(PrefixedName("montessori_board"), board_shape, _HOLE_FOOTPRINTS)
    board_center_z = _board_center_z(mounted_table_top_z)
    with world.modify_world():
        world.add_kinematic_structure_entity(board)
        world.add_connection(
            FixedConnection.create_with_dofs(
                parent=world.root,
                child=board,
                world=world,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    BOARD_X, BOARD_Y, board_center_z
                ),
            )
        )
    return board


REPORTED_PICK_EVENT_TYPES: tuple[type, ...] = (
    SupportEvent,
    LossOfSupportEvent,
    GraspEvent,
    LossOfGraspEvent,
    LiftEvent,
    PickUpEvent,
)
"""
Event types :func:`_log_pick_events` reports a yes/no on after each shape's pick.
"""


def _log_pick_events(body: Body, monitor: MontessoriEventMonitor) -> None:
    """
    Log which of :data:`REPORTED_PICK_EVENT_TYPES` SegMind detected for ``body``.

    :param body: The shape body the monitor tracked.
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
class _SortingRig:
    """
    The fixed pieces every pick-and-place in this demo shares, so one shape can be
    sorted with a single call.
    """

    context: Context
    """Plan context bound to the live world and robot."""

    world: World
    """The live, fetched world."""

    robot: Tracy
    """The robot doing the sorting, for the SegMind grasp and lift detectors."""

    feed: EventFeed
    """Sink the per-shape SegMind events are streamed to for the live dashboard."""

    gripper: RobotiqGripperController
    """Direct Robotiq gripper control, bypassing Giskard."""

    gripper_listener: GripperJointStateListener
    """Live knuckle-position feed for the pick arm, read by the slip watch."""

    grasp_description: GraspDescription
    """Grasp used for every shape."""

    tool_frame: Body
    """The picking arm's tool frame, the parent a grasped shape is attached to."""

    table_top_z: float
    """Height of the live robot's own table top."""

    close_table: GraspCloseTable = field(default_factory=GraspCloseTable)
    """Per-shape close setpoint the grasp is sized to."""

    grasp_height_offset: float = GRASP_HEIGHT_OFFSET
    """Height the reach, grasp and lift are aimed above a shape's own centre."""

    slip_watch_interval: float = SLIP_WATCH_INTERVAL_SECONDS
    """Seconds between the slip watch's re-closes while carrying a shape."""

    post_lift_settle: float = POST_LIFT_SETTLE_SECONDS
    """Seconds to let the grasp settle after the lift before it is read."""

    def sort(
        self, body: Body, category: MontessoriShapeCategory, half_height: float
    ) -> None:
        """
        Pick ``body`` off the table and release it :data:`PLACE_HOVER` above the board
        hole matching ``category``.

        The gripper is opened and closed through :attr:`gripper` rather than a plan
        node, since Giskard cannot command Tracy's real fingers, and the close is sized
        to ``category`` via :attr:`close_table`. The reach and lift are aimed
        :attr:`grasp_height_offset` above ``body``'s own centre, since the shape is
        spawned resting on the table.

        :param body: The shape to sort, already spawned on the table.
        :param category: The board hole the shape belongs to, and the shape whose close
            setpoint the grasp uses.
        :param half_height: Half the shape's own height, for seating it above the hole.
        """
        grasp_target = _grasp_target_pose(body, self.grasp_height_offset)
        reach = ReachAction(
            target_pose=grasp_target,
            object_designator=body,
            arm=PICK_ARM,
            grasp_description=self.grasp_description,
        )
        _, _, lift_to_pose = self.grasp_description.pose_sequence(grasp_target, body)
        place_target = _hole_place_pose(
            self.world, self.table_top_z, category, half_height
        )
        transport_pose, placing_pose, retract_pose = (
            self.grasp_description.pose_sequence(place_target, body, reverse=True)
        )

        reach_plan = sequential([reach], context=self.context).plan
        lift = sequential(
            [
                AttachNode(body=body, new_parent=self.tool_frame),
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
                DetachNode(body=body, new_parent=self.world.root),
                MoveToolCenterPointMotion(
                    retract_pose,
                    PICK_ARM,
                    allow_gripper_collision=True,
                    movement_type=MovementType.TRANSLATION,
                ),
                # Park before the next shape so the arm clears the board on its way
                # back to the table instead of dragging the gripper across it.
                ParkArmsAction(PICK_ARM),
            ],
            context=self.context,
        ).plan

        monitor = build_pick_monitor(
            world=self.world, tracked_body=body, robot=self.robot, arm=PICK_ARM
        )
        shape_name = body.name.name
        monitor.context.require_extension(SegmindContext).logger.add_callback(
            DetectionEvent,
            lambda event, name=shape_name: self.feed.publish(name, event),
        )
        close_setpoint = self.close_table.setpoint_for(category)
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
        just transferred the shape's weight onto the fingers and the knuckle is still
        moving, so a reading taken now would seed the slip detector from a position the
        grasp never reaches. Then the close is firmed to ``close_setpoint`` and the
        knuckle read once: an empty
        gripper (the grasp missed) skips the watch. Otherwise a re-close just past
        ``close_setpoint`` is commanded every :attr:`slip_watch_interval` seconds for as
        long as ``carry`` runs; each
        poll's verdict is logged, and a slip also streams a
        :class:`~experiments.tracy_experiments.montessori.gripper_feedback.
        GripperSlipEvent` to the dashboard.

        :param body: The shape being carried.
        :param close_setpoint: The shape's own close setpoint, re-commanded to firm the
            grasp before the knuckle is read.
        :param carry: Runs the transport-and-place motion.
        """
        shape_name = body.name.name
        time.sleep(self.post_lift_settle)
        self.gripper.close_to(PICK_ARM, close_setpoint)
        confirmation = confirm_grasp(self.gripper_listener.latest_closure)
        logger.info("%s: grasp check -> %s.", shape_name, confirmation.verdict)
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
            name=f"slip-watch-{shape_name}",
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

        :param body: The shape being carried.
        :param verdict: The poll's held-or-slipped verdict.
        """
        logger.info("%s: slip watch -> %s.", body.name.name, verdict)
        if verdict is GraspVerdict.OBJECT_SLIPPED:
            self.feed.publish(body.name.name, GripperSlipEvent(tracked_object=body))


def main() -> None:
    # giskard_process = subprocess.Popen(
    #     ["ros2", "launch", "giskardpy_ros", "giskardpy_tracy_velocity.launch.py"],
    #     start_new_session=True,
    # )
    # time.sleep(8)  # Wait for the launch file to start

    feed = EventFeed()
    run_dashboard(feed)

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
    viz_marker_publisher.with_tf_publisher()

    WorldSynchronizer(_world=world, node=node)

    table_top_z = read_table_top_z(robot)
    cube = _add_cube(world, table_top_z)
    _add_montessori_board(world, table_top_z)
    shape_bodies = [
        _add_montessori_shape(world, table_top_z, target) for target in PICK_TARGETS
    ]

    logger.info(
        "Cube plus %d shapes spawned in rviz at x=%.3f. Check they line up with the "
        "real objects, then press Enter to run the sorting.",
        len(shape_bodies),
        CUBE_X,
    )
    # input()

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
        table_top_z,
    )

    park = sequential([ParkArmsAction(PICK_ARM)], context=context).plan

    input()
    logger.info("Sorting %d shapes on the real robot.", len(shape_bodies) + 1)
    with ExecutionEnvironment(
        execution_type=ExecutionType.REAL, collision_avoidance=True
    ):
        park.perform()
        rig.sort(cube, MontessoriShapeCategory.CUBE, CUBE_SIZE / 2)
        for target, body in zip(PICK_TARGETS, shape_bodies):
            rig.sort(body, target.category, target.half_height)
    logger.info("Sorting finished.")


if __name__ == "__main__":
    main()
