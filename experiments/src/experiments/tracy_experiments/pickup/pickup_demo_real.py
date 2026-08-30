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

Run with (``iai_tracy_description`` and the Giskard/world-fetcher ROS stack must be
running)::

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
import os
import signal
import subprocess
import threading
import time
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
from experiments.tracy_experiments.rosbag_recording import (
    DEFAULT_BAG_DIRECTORY,
    DECIMATED_TOPICS,
    RosbagRecorder,
)
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
from experiments.tracy_experiments.montessori.grasp_widths import GraspCloseTable
from experiments.tracy_experiments.robotiq_gripper import RobotiqGripperController
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
Vertical offset added to the read table-top height when seating the board, matching the
same correction :func:`_add_cube` applies to the cube.
"""

PLACE_HOVER = 0.04
"""
Height above the board's top surface at which a shape is released over its hole.
"""

SHAPE_TABLE_CLEARANCE = 0.04
"""
Vertical offset added to the read table-top height when seating a loose shape, so its
model rests where the real object does.
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


BAG_NAME_PREFIX = "tracy_pickup_demo"
"""
Leading part of the recorded bag's directory name, completed with a timestamp so
consecutive runs do not collide.
"""

KEEP_EVERY_NTH_FRAME = 10
"""
How much of the camera streams a recorded run keeps, by default.

Recording every frame costs around 230 MB of disk per second of wall clock: a sorting
run fills tens of gigabytes, almost all of it registered depth and point cloud. One frame
in ten still shows what the arm did, at roughly a ninth of the size. Pass
``--keep-every-nth-frame 1`` for a run that genuinely needs every frame.
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
    cube_center_z = mounted_table_top_z + CUBE_SIZE / 2 + SHAPE_TABLE_CLEARANCE
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
    shape_center_z = mounted_table_top_z + target.half_height + SHAPE_TABLE_CLEARANCE
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

    gripper: RobotiqGripperController
    """Direct Robotiq gripper control, bypassing Giskard."""

    grasp_description: GraspDescription
    """Grasp used for every shape."""

    tool_frame: Body
    """The picking arm's tool frame, the parent a grasped shape is attached to."""

    table_top_z: float
    """Height of the live robot's own table top."""

    close_table: GraspCloseTable = field(default_factory=GraspCloseTable)
    """Per-shape close setpoint the grasp is sized to."""

    def sort(
        self, body: Body, category: MontessoriShapeCategory, half_height: float
    ) -> None:
        """
        Pick ``body`` off the table and release it :data:`PLACE_HOVER` above the board
        hole matching ``category``.

        The gripper is opened and closed through :attr:`gripper` rather than a plan
        node, since Giskard cannot command Tracy's real fingers, and the close is sized
        to ``category`` via :attr:`close_table`.

        :param body: The shape to sort, already spawned on the table.
        :param category: The board hole the shape belongs to, and the shape whose close
            setpoint the grasp uses.
        :param half_height: Half the shape's own height, for seating it above the hole.
        """
        reach = ReachAction(
            target_pose=Pose(reference_frame=body),
            object_designator=body,
            arm=PICK_ARM,
            grasp_description=self.grasp_description,
        )
        _, _, lift_to_pose = self.grasp_description.grasp_pose_sequence(body)
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

        self.gripper.move(PICK_ARM, GripperState.OPEN)
        reach_plan.perform()
        self.gripper.close_to(PICK_ARM, self.close_table.setpoint_for(category))
        lift.perform()
        place.perform()
        self.gripper.move(PICK_ARM, GripperState.OPEN)
        retract_and_park.perform()


def _parse_arguments() -> argparse.Namespace:
    """
    :return: The demo's own command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Sort the Montessori shapes with the physical Tracy."
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
    # giskard_process = subprocess.Popen(
    #     ["ros2", "launch", "giskardpy_ros", "giskardpy_tracy_velocity.launch.py"],
    #     start_new_session=True,
    # )
    # time.sleep(8)  # Wait for the launch file to start

    arguments = _parse_arguments()

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
    tool_frame = ViewManager.get_end_effector_view(PICK_ARM, robot).tool_frame
    rig = _SortingRig(
        context, world, gripper, grasp_description, tool_frame, table_top_z
    )

    park = sequential([ParkArmsAction(PICK_ARM)], context=context).plan

    input()
    logger.info("Sorting %d shapes on the real robot.", len(shape_bodies) + 1)
    # Recording starts here rather than at start-up so the bag holds the sorting itself,
    # not the operator's wait at the prompt above, and closes as soon as the last shape
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
        rig.sort(cube, MontessoriShapeCategory.CUBE, CUBE_SIZE / 2)
        for target, body in zip(PICK_TARGETS, shape_bodies):
            rig.sort(body, target.category, target.half_height)
    logger.info("Sorting finished.")


if __name__ == "__main__":
    main()
