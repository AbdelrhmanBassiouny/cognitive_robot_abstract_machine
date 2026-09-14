"""
Tests for :mod:`experiments.tracy_experiments.lab_without_the_robot`: the world is
fetched as the bringup serves it, the camera shows a capture from where it was taken,
and each gripper's driver closes the fingers in the published world and reports what the
Robotiq driver reports.

Everything here crosses the middleware, so the lab is brought up once for the module and
the demo's side is a node of its own, spun the way the demo spins it.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest
import rclpy
from coraplex.datastructures.enums import Arms
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from rclpy.node import Node
from typing_extensions import Callable, Iterator

from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.imagination import piece_mesh
from experiments.montessori.perception.live_camera import LiveCamera
from experiments.montessori.pieces import SMALLER_PIECES
from experiments.montessori.semantics import CubeShape, MontessoriShapeCategory
from experiments.tracy_experiments.lab_without_the_robot import (
    KNUCKLE_POSITION_ON_A_PIECE,
    MERGED_JOINT_STATE_TOPIC,
    LabWithoutTheRobot,
)
from experiments.tracy_experiments.live_tracy import LiveTracy
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    OPEN_KNUCKLE_POSITION,
    GraspVerdict,
    GripperJointStateListener,
    confirm_grasp,
    gripper_joint_state_topic,
    knuckle_joint_name,
    reclose_setpoint_for,
)
from experiments.tracy_experiments.robotiq_gripper import RobotiqGripperController
from experiments.tracy_experiments.rosbag_recording import DEFAULT_TOPICS
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Mesh
from semantic_digital_twin.world_description.mesh_file_storage import MeshFileStorage
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from .test_tracy_montessori_scene_builder import MEASURED_CAPTURE

ANOTHER_CAPTURE = "shadowed_lid_rim"
"""
A second capture of the same table, told apart from the measured one by its picture.
"""

ARRIVAL_TIMEOUT = 10.0
"""
How long a test waits for something to cross the middleware, in seconds.
"""

POLL_PERIOD = 0.05
"""
How often a test looks whether what it waits for has arrived, in seconds.
"""

MOTION_TICKS = 200
"""
How many states a motion publishes, one per tick of its controller.
"""

MOTION_TICK_PERIOD = 0.01
"""
Seconds between two ticks of a motion's controller.
"""

CLOSE_SETPOINT_ON_A_PIECE = 0.65
"""
A close sized to a piece, as the demo's close table sizes one.
"""

# %% the lab and the demo's side of it


@pytest.fixture(scope="module")
def ros() -> Iterator[None]:
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture(scope="module")
def capture() -> SceneCapture:
    return SceneCapture.load(MEASURED_CAPTURE)


@pytest.fixture(scope="module")
def lab(ros: None, capture: SceneCapture) -> Iterator[LabWithoutTheRobot]:
    with LabWithoutTheRobot.brought_up(capture) as lab:
        yield lab


@pytest.fixture(scope="module")
def demo_node(ros: None) -> Iterator[Node]:
    """
    The demo's own node, spun on a thread as the demo's connection spins it.
    """
    node = rclpy.create_node("lab_without_the_robot_test")
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()
    yield node
    executor.shutdown()
    node.destroy_node()


@pytest.fixture(scope="module")
def gripper(demo_node: Node) -> RobotiqGripperController:
    return RobotiqGripperController(demo_node)


@pytest.fixture(scope="module")
def listener(demo_node: Node) -> GripperJointStateListener:
    return GripperJointStateListener(node=demo_node, arm=Arms.LEFT)


def wait_until(arrived: Callable[[], bool]) -> None:
    """
    Wait for what a test waits for to arrive over the middleware.

    :raises TimeoutError: If it never does.
    """
    deadline = time.monotonic() + ARRIVAL_TIMEOUT
    while time.monotonic() < deadline:
        if arrived():
            return
        time.sleep(POLL_PERIOD)
    raise TimeoutError(f"nothing arrived within {ARRIVAL_TIMEOUT} s")


# %% the world the robot publishes


def test_the_world_fetched_from_the_lab_holds_tracy_as_the_service_serves_it(
    lab: LabWithoutTheRobot, demo_node: Node
):
    """
    The world reaches the demo the way it reaches it in the lab: rebuilt from the JSON
    the service serves, so every mesh of it is exported afresh into this process's own
    mesh storage.
    """
    fetched = fetch_world_from_service(node=demo_node, timeout_seconds=ARRIVAL_TIMEOUT)

    assert fetched is not lab.world
    [robot] = fetched.get_semantic_annotations_by_type(Tracy)
    assert robot.name == lab.world.get_semantic_annotations_by_type(Tracy)[0].name
    assert fetched.root.name == lab.world.root.name
    meshes = [
        Path(shape.filename)
        for body in fetched.bodies
        for shape in [*body.visual, *body.collision]
        if isinstance(shape, Mesh)
    ]
    assert meshes
    assert all(MeshFileStorage().is_in_a_root(mesh) for mesh in meshes)


# %% the camera


def test_the_camera_shows_the_capture_from_where_it_was_taken(
    lab: LabWithoutTheRobot, demo_node: Node, capture: SceneCapture
):
    camera = LiveCamera(node=demo_node)
    reference_frame = lab.world.root.name.name

    wait_until(lambda: camera.frame_in(reference_frame) is not None)
    frame = camera.frame_in(reference_frame)

    expected = capture.to_frame()
    np.testing.assert_array_equal(frame.color, expected.color)
    np.testing.assert_allclose(frame.depth, expected.depth)
    assert frame.intrinsics == capture.intrinsics
    np.testing.assert_allclose(
        frame.reference_frame_T_camera, capture.reference_frame_T_camera, atol=1e-9
    )


def test_the_camera_shows_another_capture_once_told_to(
    lab: LabWithoutTheRobot, demo_node: Node, capture: SceneCapture
):
    another = SceneCapture.load(ANOTHER_CAPTURE)
    camera = LiveCamera(node=demo_node)
    reference_frame = lab.world.root.name.name
    shown = another.to_frame().color

    lab.camera.show(another)
    try:
        wait_until(
            lambda: camera.frame_in(reference_frame) is not None
            and np.array_equal(camera.frame_in(reference_frame).color, shown)
        )
    finally:
        lab.camera.show(capture)

    assert lab.camera.capture is capture


# %% the grippers' drivers


def test_a_close_on_nothing_reaches_fully_closed_and_reads_as_an_empty_gripper(
    lab: LabWithoutTheRobot,
    gripper: RobotiqGripperController,
    listener: GripperJointStateListener,
):
    [left] = [driver for driver in lab.grippers if driver.arm is Arms.LEFT]

    gripper.move(Arms.LEFT, GripperState.CLOSE)

    assert left.knuckle_position == pytest.approx(FULLY_CLOSED_KNUCKLE_POSITION)
    knuckle = lab.world.get_degree_of_freedom_by_name(knuckle_joint_name(Arms.LEFT))
    assert lab.world.state[knuckle.id].position == pytest.approx(
        FULLY_CLOSED_KNUCKLE_POSITION
    )
    wait_until(
        lambda: listener.has_reading and listener.latest_closure.closed_on_nothing()
    )
    assert confirm_grasp(listener.latest_closure).verdict is GraspVerdict.GRIPPER_EMPTY

    gripper.move(Arms.LEFT, GripperState.OPEN)

    assert left.knuckle_position == pytest.approx(OPEN_KNUCKLE_POSITION)


def stand_a_piece_at_the_tool_frame(world: World, robot: Tracy) -> CubeShape:
    """
    Stand a cube in the world where the left tool frame is, so the fingers meet it.
    """
    name = PrefixedName("cube_between_the_fingers", "lab_without_the_robot_test")
    body = Body.from_shape_collection(
        name,
        ShapeCollection(
            [piece_mesh(SMALLER_PIECES.by_category[MontessoriShapeCategory.CUBE])]
        ),
    )
    piece = CubeShape(name=name, root=body)
    tool_frame = robot.left_arm.end_effector.tool_frame.global_transform.to_np()
    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=body,
                parent_T_connection_expression=HomogeneousTransformationMatrix(
                    tool_frame, reference_frame=world.root
                ),
            )
        )
        world.add_semantic_annotation(piece)
    return piece


def take_down(world: World, piece: CubeShape) -> None:
    with world.modify_world():
        world.remove_semantic_annotation(piece)
        world.remove_kinematic_structure_entity(piece.root)


def test_a_close_on_a_piece_stalls_where_the_fingers_stop_and_stays_there_on_a_reclose(
    lab: LabWithoutTheRobot,
    gripper: RobotiqGripperController,
    listener: GripperJointStateListener,
):
    """
    A close that meets a piece is what the driver reports as a stall, and a re-close a
    little past it, as the slip watch sends every second, moves the fingers no further:

    the piece is still held.
    """
    [left] = [driver for driver in lab.grippers if driver.arm is Arms.LEFT]
    [robot] = lab.world.get_semantic_annotations_by_type(Tracy)
    piece = stand_a_piece_at_the_tool_frame(lab.world, robot)
    try:
        gripper.close_to(Arms.LEFT, CLOSE_SETPOINT_ON_A_PIECE)
        assert left.knuckle_position == pytest.approx(KNUCKLE_POSITION_ON_A_PIECE)
        wait_until(
            lambda: listener.has_reading
            and listener.latest_closure.knuckle_position
            == pytest.approx(KNUCKLE_POSITION_ON_A_PIECE)
        )
        confirmation = confirm_grasp(listener.latest_closure)
        assert confirmation.verdict is GraspVerdict.OBJECT_HELD

        gripper.close_to(Arms.LEFT, reclose_setpoint_for(CLOSE_SETPOINT_ON_A_PIECE))

        assert left.knuckle_position == pytest.approx(KNUCKLE_POSITION_ON_A_PIECE)
        assert (
            confirmation.slip_detector.check(listener.latest_closure)
            is GraspVerdict.OBJECT_HELD
        )
    finally:
        take_down(lab.world, piece)
        gripper.move(Arms.LEFT, GripperState.OPEN)


# %% what a bag can record of it


def test_the_lab_publishes_the_camera_and_joint_state_topics_a_bag_records(
    lab: LabWithoutTheRobot,
):
    published = lab.published_topics

    assert set(published) <= set(DEFAULT_TOPICS)
    assert set(published) >= set(lab.camera.published_topics) & set(DEFAULT_TOPICS)
    assert MERGED_JOINT_STATE_TOPIC in published
    assert gripper_joint_state_topic(Arms.LEFT) in published


# %% the demo's connection over the lab


def test_the_demo_connects_to_the_lab_as_it_connects_to_the_robot(
    lab: LabWithoutTheRobot,
):
    """
    The connection fetches the served world, finds Tracy in it and watches the shown
    capture through its perception node; it spins its node on one thread, since the
    multi-threaded executor starves the process for as long as a callback runs.
    """
    with LiveTracy.connected("lab_without_the_robot_test_demo") as tracy:
        assert (
            tracy.robot.name
            == lab.world.get_semantic_annotations_by_type(Tracy)[0].name
        )
        assert type(tracy.executor) is SingleThreadedExecutor
        frame = tracy.look.wait_for_frame(timeout_seconds=ARRIVAL_TIMEOUT)

    np.testing.assert_allclose(
        frame.reference_frame_T_camera, lab.camera.capture.reference_frame_T_camera
    )


def test_every_tick_a_motion_publishes_reaches_the_demo_while_its_camera_looks(
    lab: LabWithoutTheRobot,
):
    """
    The world a motion changes tick by tick is kept in step while the camera keeps
    looking at the table: Giskard's goal waits for its last tick to arrive, and a look
    runs for as long as the pipeline takes.
    """
    joint = lab.world.get_degree_of_freedom_by_name(knuckle_joint_name(Arms.RIGHT))
    positions = np.linspace(
        OPEN_KNUCKLE_POSITION, FULLY_CLOSED_KNUCKLE_POSITION, MOTION_TICKS
    )
    with LiveTracy.connected("lab_without_the_robot_test_motion") as tracy:
        tracy.look.wait_for_scene(timeout_seconds=ARRIVAL_TIMEOUT)
        for position in positions:
            lab.world.state[joint.id].position = position
            lab.world.notify_state_change()
            time.sleep(MOTION_TICK_PERIOD)
        wait_until(
            lambda: np.isclose(tracy.world.state[joint.id].position, positions[-1])
        )
