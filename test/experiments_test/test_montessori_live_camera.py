"""
Reading the camera as the live robot publishes it, and writing one look as a capture.

Runs against a node of its own with the streams published from this process, so it needs
ROS but no camera and no robot.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

rclpy = pytest.importorskip("rclpy")

from geometry_msgs.msg import TransformStamped
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage
from tf2_ros import StaticTransformBroadcaster
from typing_extensions import Callable, Iterator, List, Optional

from experiments.montessori.perception.camera import (
    CameraIntrinsics,
    CameraTopic,
    DepthQuantization,
    RgbdFrame,
)
from experiments.montessori.perception.capture_from_camera import (
    LIVE_CAMERA_TAKE,
    take_name,
    write_capture,
)
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.exceptions import (
    LookingHasStopped,
    NoSceneAvailable,
)
from experiments.montessori.perception.live_camera import LiveCamera
from experiments.montessori.perception.measured_plane import CameraPoseError
from experiments.montessori.perception.node import (
    MontessoriPerceptionNode,
    configure_logging,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import perception_pipeline
from experiments.montessori.perception.scene_request import SceneRequest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from .test_montessori_camera import (
    COLOR_FORMAT_FIELD,
    DEPTH_FORMAT_FIELD,
    encode_compressed_depth,
)
from .test_montessori_measured_plane import LEAN, leaned_capture

# %% the scene this process publishes

REFERENCE_FRAME = "map"
"""
The frame the camera's pose is asked for in.
"""

CAMERA_FRAME = "camera_color_optical_frame"
"""
The frame the published calibration says the images are taken in.
"""

INTRINSIC_MATRIX = np.array(
    [[1117.0, 0.0, 960.0], [0.0, 1117.0, 540.0], [0.0, 0.0, 1.0]]
)
"""
The calibration the camera publishes.
"""

CAMERA_POSE = HomogeneousTransformationMatrix.from_xyz_quaternion(
    0.5, -0.2, 1.4, 1.0, 0.0, 0.0, 0.0
).to_np()
"""
Where the transform tree stands the camera, a half turn about x at a stated place.
"""

COLOR_IMAGE = np.full((4, 6, 3), (10, 200, 30), dtype=np.uint8)
"""
The colour image published, blue/green/red, which is the order its format field says the
payload is stored in.
"""

DEPTH_MILLIMETRES = np.full((4, 6), 880, dtype=np.uint16)
"""
The depth image published, in millimetres.
"""

DEPTH_QUANTIZATION = DepthQuantization(0, 0.0, 0.0)
"""
A header for a depth image stored in millimetres, which needs no quantization undone.
"""

PUBLISH_PERIOD = 0.05
"""
How often the streams are re-published while a test waits, in seconds.
"""

ARRIVAL_TIMEOUT = 5.0
"""
How long a test waits for a message to cross the middleware, in seconds.
"""


@pytest.fixture(scope="module")
def ros() -> Iterator[None]:
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node(ros: None) -> Iterator[Node]:
    node = rclpy.create_node("live_camera_test")
    yield node
    node.destroy_node()


class PublishedCamera:
    """
    Publishes the camera's three streams and its pose the way the robot does.
    """

    def __init__(self, node: Node):
        self.camera_info = node.create_publisher(
            CameraInfo, CameraTopic.CAMERA_INFO, qos_profile_sensor_data
        )
        self.depth = node.create_publisher(
            CompressedImage, CameraTopic.DEPTH, qos_profile_sensor_data
        )
        self.color = node.create_publisher(
            CompressedImage, CameraTopic.COLOR, qos_profile_sensor_data
        )
        self.transforms = StaticTransformBroadcaster(node)

    def publish_camera_info(self) -> None:
        message = CameraInfo()
        message.header.frame_id = CAMERA_FRAME
        message.k = INTRINSIC_MATRIX.flatten().tolist()
        self.camera_info.publish(message)

    def publish_depth(self) -> None:
        message = CompressedImage()
        message.format = DEPTH_FORMAT_FIELD
        message.data = encode_compressed_depth(DEPTH_MILLIMETRES, DEPTH_QUANTIZATION)
        self.depth.publish(message)

    def publish_color(self) -> None:
        message = CompressedImage()
        message.format = COLOR_FORMAT_FIELD
        message.data = cv2.imencode(".png", COLOR_IMAGE)[1].tobytes()
        self.color.publish(message)

    def publish_pose(self) -> None:
        x, y, z = CAMERA_POSE[:3, 3]
        transform = TransformStamped()
        transform.header.frame_id = REFERENCE_FRAME
        transform.child_frame_id = CAMERA_FRAME
        transform.transform.translation.x = float(x)
        transform.transform.translation.y = float(y)
        transform.transform.translation.z = float(z)
        transform.transform.rotation.x = 1.0
        transform.transform.rotation.w = 0.0
        self.transforms.sendTransform(transform)

    def publish_all(self) -> None:
        self.publish_camera_info()
        self.publish_depth()
        self.publish_color()
        self.publish_pose()


@pytest.fixture
def published(node: Node) -> PublishedCamera:
    return PublishedCamera(node)


def spin_until(
    node: Node, publish: Callable[[], None], arrived: Callable[[], bool]
) -> None:
    """
    Re-publish and spin until what a test waits for has arrived.

    :param node: The node to spin.
    :param publish: Publishes what is waited for, again each turn.
    :param arrived: Whether it has arrived.
    :raises TimeoutError: If it never does.
    """
    deadline = time.monotonic() + ARRIVAL_TIMEOUT
    while time.monotonic() < deadline:
        publish()
        rclpy.spin_once(node, timeout_sec=PUBLISH_PERIOD)
        if arrived():
            return
    raise TimeoutError(f"nothing arrived within {ARRIVAL_TIMEOUT} s")


# %% the streams


def test_every_stream_is_missing_before_anything_has_arrived(node: Node):
    camera = LiveCamera(node=node)

    assert camera.missing_inputs() == [
        str(CameraTopic.CAMERA_INFO),
        str(CameraTopic.DEPTH),
        str(CameraTopic.COLOR),
    ]


def test_a_stream_stops_being_missing_once_a_message_has_arrived_on_it(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(node, published.publish_depth, lambda: camera.depth is not None)

    assert camera.missing_inputs() == [
        str(CameraTopic.CAMERA_INFO),
        str(CameraTopic.COLOR),
    ]


def test_the_calibration_is_read_as_intrinsics_and_the_frame_it_names(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(
        node, published.publish_camera_info, lambda: camera.camera_info is not None
    )

    assert camera.intrinsics == CameraIntrinsics.from_camera_info_matrix(
        INTRINSIC_MATRIX
    )
    assert camera.camera_frame == CAMERA_FRAME


def test_a_colour_image_completes_a_look_and_is_handed_to_the_callback(
    node: Node, published: PublishedCamera
):
    completed: List[CompressedImage] = []
    camera = LiveCamera(node=node, color_callback=completed.append)

    spin_until(node, published.publish_color, lambda: len(completed) > 0)

    assert completed[0] is camera.color


def test_the_images_are_decoded_as_published(node: Node, published: PublishedCamera):
    camera = LiveCamera(node=node)

    spin_until(
        node,
        published.publish_all,
        lambda: camera.color is not None and camera.depth is not None,
    )

    np.testing.assert_array_equal(camera.color_image, COLOR_IMAGE)
    np.testing.assert_allclose(camera.depth_image, DEPTH_MILLIMETRES / 1000.0)


# %% where the camera stands


def test_the_pose_is_unknown_until_the_calibration_names_the_camera_frame(
    node: Node,
):
    camera = LiveCamera(node=node)

    assert camera.pose_in(REFERENCE_FRAME) is None


def test_the_camera_stands_where_the_transform_tree_puts_it(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(
        node,
        published.publish_all,
        lambda: camera.pose_in(REFERENCE_FRAME) is not None,
    )

    np.testing.assert_allclose(camera.pose_in(REFERENCE_FRAME), CAMERA_POSE, atol=1e-9)


def test_a_frame_carries_the_images_the_calibration_and_the_pose(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(
        node,
        published.publish_all,
        lambda: camera.frame_in(REFERENCE_FRAME) is not None,
    )
    frame = camera.frame_in(REFERENCE_FRAME)

    np.testing.assert_array_equal(frame.color, camera.color_image)
    np.testing.assert_array_equal(frame.depth, camera.depth_image)
    assert frame.intrinsics == camera.intrinsics
    np.testing.assert_allclose(frame.reference_frame_T_camera, CAMERA_POSE, atol=1e-9)


# %% writing a look as a capture


def test_a_capture_taken_off_the_camera_reads_back_as_the_look_it_was_taken_from(
    node: Node, published: PublishedCamera, tmp_path: Path
):
    timer = node.create_timer(PUBLISH_PERIOD, published.publish_all)

    capture = write_capture(
        node,
        "live_look",
        reference_frame=REFERENCE_FRAME,
        timeout_seconds=ARRIVAL_TIMEOUT,
        directory=tmp_path,
    )
    node.destroy_timer(timer)

    read_back = SceneCapture.load("live_look", tmp_path)
    assert read_back.intrinsics == CameraIntrinsics.from_camera_info_matrix(
        INTRINSIC_MATRIX
    )
    assert read_back.reference_frame == REFERENCE_FRAME
    assert read_back.color_format == COLOR_FORMAT_FIELD
    np.testing.assert_allclose(read_back.reference_frame_T_camera, CAMERA_POSE)
    frame = read_back.to_frame()
    np.testing.assert_array_equal(frame.color, COLOR_IMAGE)
    np.testing.assert_allclose(frame.depth, DEPTH_MILLIMETRES / 1000.0)
    assert capture.recorded_from == read_back.recorded_from
    assert read_back.recorded_from.startswith(LIVE_CAMERA_TAKE)


def test_a_capture_names_the_moment_it_was_taken_at():
    assert take_name(datetime(2026, 9, 11, 18, 24, 5)) == (
        f"{LIVE_CAMERA_TAKE}_20260911_182405"
    )


def test_writing_a_capture_reports_what_never_arrived_when_the_camera_is_silent(
    node: Node, tmp_path: Path
):
    with pytest.raises(NoSceneAvailable) as raised:
        write_capture(node, "silent", timeout_seconds=0.2, directory=tmp_path)

    assert raised.value.missing_inputs == [
        str(CameraTopic.CAMERA_INFO),
        str(CameraTopic.DEPTH),
        str(CameraTopic.COLOR),
    ]


# %% the stated pose is checked against the table on the first placed look


def test_the_node_reports_how_far_the_stated_pose_is_off_on_its_first_placed_look(
    node: Node,
):
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())

    error = perception.check_camera_pose(leaned_capture().to_frame())

    assert perception.camera_pose_error is error
    assert not error.within_tolerance
    assert error.tilt == pytest.approx(LEAN, abs=0.5)


# %% the newest result is one taken through the pipeline the node reads with

A_LOOK = "tracy_pickup_demo"
"""
A capture any pipeline of the recorded setup can look at.
"""

A_SHORT_WAIT = 0.1
"""
How long a test waits for a result: long enough for one the node already holds, and
short enough not to hold up a test for one it expects the node not to have.
"""


@dataclass
class _PipelineHandingOverAnotherMidLook(MontessoriPerceptionPipeline):
    """
    A pipeline that, while it takes a look, hands the node another pipeline to read
    with -- what a board being held while a look is under way does.
    """

    node: MontessoriPerceptionNode = field(kw_only=True)
    """
    The node to hand the other pipeline to.
    """

    handed_over: MontessoriPerceptionPipeline = field(kw_only=True)
    """
    The pipeline handed over.
    """

    def detect(self, frame: RgbdFrame, request: SceneRequest = SceneRequest()):
        self.node.read_with(self.handed_over)
        return super().detect(frame, request)


@dataclass
class _PipelineAskingForTheFrameMidLook(MontessoriPerceptionPipeline):
    """
    A pipeline that, while it takes a look, asks the node for its newest frame -- what
    a run waiting for a frame does while the camera's thread is still detecting.
    """

    node: MontessoriPerceptionNode = field(kw_only=True)
    """
    The node asked for the frame.
    """

    served_mid_look: Optional[RgbdFrame] = None
    """
    The frame the node served while the look was under way.
    """

    def detect(self, frame: RgbdFrame, request: SceneRequest = SceneRequest()):
        self.served_mid_look = self.node.wait_for_frame(A_SHORT_WAIT)
        return super().detect(frame, request)


def test_the_frame_a_look_is_taken_on_is_served_before_the_look_ends(node: Node):
    """
    A first look under load can outlast a run's wait for a frame; the frame is there
    as soon as it is built, whether or not the pipeline has finished with it.
    """
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())
    read_with_now = perception.pipeline
    asking = _PipelineAskingForTheFrameMidLook(
        table=read_with_now.table,
        lid=read_with_now.lid,
        reference_frame=read_with_now.reference_frame,
        world=read_with_now.world,
        pieces=read_with_now.pieces,
        node=perception,
    )
    perception.read_with(asking)
    frame = SceneCapture.load(A_LOOK).to_frame()

    perception.look_at(frame)

    assert asking.served_mid_look is frame


A_SLOW_LOOK = 3 * A_SHORT_WAIT
"""
How long a slow look takes: longer than a wait that starts when the look does, so a wait
that gives up on its own clock alone runs out while the look is still under way.
"""


@dataclass
class _PipelineTakingItsTime(MontessoriPerceptionPipeline):
    """
    A pipeline whose look takes :data:`A_SLOW_LOOK`, as a first look through a pipeline
    just handed over does.
    """

    def detect(self, frame: RgbdFrame, request: SceneRequest = SceneRequest()):
        time.sleep(A_SLOW_LOOK)
        return super().detect(frame, request)


def test_a_wait_for_a_scene_outlasts_a_look_that_is_under_way(node: Node):
    """
    The first look through a pipeline just handed over is slow, and a run waiting for
    the scene must not give up while the camera's thread is still looking at it.
    """
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())
    read_with_now = perception.pipeline
    perception.read_with(
        _PipelineTakingItsTime(
            table=read_with_now.table,
            lid=read_with_now.lid,
            reference_frame=read_with_now.reference_frame,
            world=read_with_now.world,
            pieces=read_with_now.pieces,
        )
    )
    frame = SceneCapture.load(A_LOOK).to_frame()
    looking = threading.Thread(target=perception.look_at, args=(frame,))
    looking.start()
    time.sleep(A_SHORT_WAIT / 2)

    seen = perception.wait_for_scene(A_SHORT_WAIT)

    looking.join()
    assert seen is perception.wait_for_scene(A_SHORT_WAIT)


def test_a_node_told_to_stop_looking_lets_the_look_under_way_finish_first(
    node: Node,
):
    """
    A look copies the world it is taken in, so whoever stops the looking to change that
    world waits for the look under way rather than changing the world beneath it.
    """
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())
    read_with_now = perception.pipeline
    perception.read_with(
        _PipelineTakingItsTime(
            table=read_with_now.table,
            lid=read_with_now.lid,
            reference_frame=read_with_now.reference_frame,
            world=read_with_now.world,
            pieces=read_with_now.pieces,
        )
    )
    looking = threading.Thread(
        target=perception.look_at, args=(SceneCapture.load(A_LOOK).to_frame(),)
    )
    looking.start()
    time.sleep(A_SHORT_WAIT / 2)

    perception.stop_looking()

    assert not looking.is_alive()
    looking.join()


def test_a_node_that_stopped_looking_takes_no_look(node: Node):
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())

    perception.stop_looking()

    with pytest.raises(LookingHasStopped):
        perception.look_at(SceneCapture.load(A_LOOK).to_frame())


def test_a_look_taken_is_the_newest_result_the_node_serves(node: Node):
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())
    frame = SceneCapture.load(A_LOOK).to_frame()

    seen = perception.look_at(frame)

    assert perception.wait_for_scene(A_SHORT_WAIT) is seen
    assert perception.wait_for_frame(A_SHORT_WAIT) is frame


def test_a_node_handed_another_pipeline_forgets_the_result_of_the_old_one(node: Node):
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())
    perception.look_at(SceneCapture.load(A_LOOK).to_frame())
    lidless = replace(perception.pipeline, lid=None)

    perception.read_with(lidless)

    assert perception.pipeline is lidless
    with pytest.raises(NoSceneAvailable):
        perception.wait_for_scene(A_SHORT_WAIT)
    with pytest.raises(NoSceneAvailable):
        perception.wait_for_frame(A_SHORT_WAIT)


def test_a_look_begun_through_a_pipeline_since_replaced_is_not_kept(node: Node):
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())
    handed_over = perception_pipeline()
    read_with_now = perception.pipeline
    perception.read_with(
        _PipelineHandingOverAnotherMidLook(
            table=read_with_now.table,
            lid=read_with_now.lid,
            reference_frame=read_with_now.reference_frame,
            world=read_with_now.world,
            pieces=read_with_now.pieces,
            node=perception,
            handed_over=handed_over,
        )
    )

    perception.look_at(SceneCapture.load(A_LOOK).to_frame())

    assert perception.pipeline is handed_over
    with pytest.raises(NoSceneAvailable):
        perception.wait_for_scene(A_SHORT_WAIT)


# %% a look after a handover is taken of images the camera sent after it

TABLE_AS_IT_IS_NOW = np.full((4, 6, 3), (200, 10, 30), dtype=np.uint8)
"""
The colour image the camera sends once the table has changed, unlike
:data:`COLOR_IMAGE`.
"""

A_STALE_IMAGE_ON_ITS_WAY = 0.5
"""
How long a test spins for an image already sent to arrive, in seconds.
"""


@dataclass
class _PipelineNotingWhatItLooksAt(MontessoriPerceptionPipeline):
    """
    A pipeline that finds nothing and notes every frame it was handed.
    """

    looked_at: List[RgbdFrame] = field(kw_only=True, default_factory=list)
    """
    The frames looked at, in order.
    """

    def detect(self, frame: RgbdFrame, request: SceneRequest = SceneRequest()):
        self.looked_at.append(frame)
        return MontessoriScene()


def noting_pipeline_placed_in(world: World) -> _PipelineNotingWhatItLooksAt:
    """
    :param world: The world whose root the camera's pose is published against.
    :return: A pipeline of the recorded setup reporting in that world's root.
    """
    recorded = perception_pipeline()
    return _PipelineNotingWhatItLooksAt(
        table=recorded.table,
        lid=recorded.lid,
        reference_frame=world.root,
        world=world,
        pieces=recorded.pieces,
    )


def world_rooted_where_the_camera_pose_is_published() -> World:
    """
    :return: A world holding only a root named as the frame the camera's pose is
        published against.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName(REFERENCE_FRAME)))
    return world


WHILE_THE_PERSON_ACTS = 0.1
"""
How long passes between the camera sending an image of the table as it was and the run
handing the node the pipeline to look again with, in seconds.
"""

A_DAY = 24 * 60 * 60.0
"""
How far behind the moment it is sent a bag played back a day after it was recorded
stamps an image, in seconds.
"""


def publish_color_sent_now(
    node: Node,
    published: PublishedCamera,
    image: np.ndarray,
    stamped_behind: float = 0.0,
) -> None:
    """
    Send one colour image stamped with the moment it is sent, as the camera does, or a
    stated time before it, as a bag played back does.

    :param node: The node whose clock stamps it.
    :param published: The camera's publishers.
    :param image: The image, blue/green/red.
    :param stamped_behind: How far before the moment it is sent its stamp lies, in
        seconds.
    """
    message = CompressedImage()
    message.header.stamp = (
        node.get_clock().now() - Duration(seconds=stamped_behind)
    ).to_msg()
    message.format = COLOR_FORMAT_FIELD
    message.data = cv2.imencode(".png", image)[1].tobytes()
    published.color.publish(message)


def publish_all_sent_now(
    node: Node,
    published: PublishedCamera,
    image: np.ndarray,
    stamped_behind: float = 0.0,
) -> None:
    """
    Send the calibration, the depth, the pose and one colour image stamped as
    :func:`publish_color_sent_now` stamps it.

    :param node: The node whose clock stamps the colour image.
    :param published: The camera's publishers.
    :param image: The colour image, blue/green/red.
    :param stamped_behind: How far before the moment it is sent the colour image's stamp
        lies, in seconds.
    """
    published.publish_camera_info()
    published.publish_depth()
    published.publish_pose()
    publish_color_sent_now(node, published, image, stamped_behind)


def node_looking_through(
    node: Node, pipeline: MontessoriPerceptionPipeline
) -> MontessoriPerceptionNode:
    """
    :param node: The node to subscribe on.
    :param pipeline: What takes the looks.
    :return: A perception node looking at every image it is sent, the camera's pose
        already checked on a capture, since the tiny images published here show no
        table to check it against.
    """
    perception = MontessoriPerceptionNode(
        node=node, pipeline=pipeline, minimum_period=0.0
    )
    perception.camera_pose_error = CameraPoseError.of(
        SceneCapture.load(A_LOOK).to_frame(), pipeline.table
    )
    return perception


def test_a_camera_stamping_its_images_a_day_behind_is_looked_at_after_a_handover(
    node: Node, published: PublishedCamera
):
    """
    A bag played back beside the robot stamps its images with the day it was recorded,
    so the moment a pipeline is handed over is read against the camera's own stamps.
    """
    world = world_rooted_where_the_camera_pose_is_published()
    before = noting_pipeline_placed_in(world)
    perception = node_looking_through(node, before)
    spin_until(
        node,
        lambda: publish_all_sent_now(node, published, COLOR_IMAGE, A_DAY),
        lambda: len(before.looked_at) > 0,
    )
    after = noting_pipeline_placed_in(world)

    time.sleep(WHILE_THE_PERSON_ACTS)
    perception.read_with(after)
    spin_until(
        node,
        lambda: publish_color_sent_now(node, published, TABLE_AS_IT_IS_NOW, A_DAY),
        lambda: len(after.looked_at) > 0,
    )

    np.testing.assert_array_equal(after.looked_at[0].color, TABLE_AS_IT_IS_NOW)


A_BAG_PLAYED_ROUND = 60.0
"""
How much earlier a bag played round again stamps its images than the last ones it sent,
in seconds.
"""


def shows(frames: List[RgbdFrame], image: np.ndarray) -> bool:
    """
    :param frames: Frames looked at.
    :param image: A colour image.
    :return: Whether any of the frames was taken of that image.
    """
    return any(np.array_equal(frame.color, image) for frame in frames)


def test_a_bag_played_round_again_is_still_looked_at_after_a_handover(
    node: Node, published: PublishedCamera
):
    """
    A bag played in a loop starts over from its first stamp; its images were still sent
    after the pipeline was handed over.
    """
    world = world_rooted_where_the_camera_pose_is_published()
    before = noting_pipeline_placed_in(world)
    perception = node_looking_through(node, before)
    spin_until(
        node,
        lambda: publish_all_sent_now(node, published, COLOR_IMAGE, A_DAY),
        lambda: len(before.looked_at) > 0,
    )
    after = noting_pipeline_placed_in(world)
    time.sleep(WHILE_THE_PERSON_ACTS)
    perception.read_with(after)
    spin_until(
        node,
        lambda: publish_color_sent_now(node, published, COLOR_IMAGE, A_DAY),
        lambda: len(after.looked_at) > 0,
    )

    spin_until(
        node,
        lambda: publish_color_sent_now(
            node, published, TABLE_AS_IT_IS_NOW, A_DAY + A_BAG_PLAYED_ROUND
        ),
        lambda: shows(after.looked_at, TABLE_AS_IT_IS_NOW),
    )

    assert shows(after.looked_at, TABLE_AS_IT_IS_NOW)


def test_a_look_after_another_pipeline_is_handed_over_is_taken_of_images_sent_after_it(
    node: Node, published: PublishedCamera
):
    """
    A run hands the node the pipeline to look again with once the person has changed the
    table; an image the camera sent before then, still on its way, shows the table as it
    was.
    """
    world = world_rooted_where_the_camera_pose_is_published()
    before = noting_pipeline_placed_in(world)
    perception = node_looking_through(node, before)
    spin_until(
        node,
        lambda: publish_all_sent_now(node, published, COLOR_IMAGE),
        lambda: len(before.looked_at) > 0,
    )
    after = noting_pipeline_placed_in(world)

    publish_color_sent_now(node, published, COLOR_IMAGE)
    time.sleep(WHILE_THE_PERSON_ACTS)
    perception.read_with(after)
    deadline = time.monotonic() + A_STALE_IMAGE_ON_ITS_WAY
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=PUBLISH_PERIOD)
    stale_looks = len(after.looked_at)
    spin_until(
        node,
        lambda: publish_color_sent_now(node, published, TABLE_AS_IT_IS_NOW),
        lambda: len(after.looked_at) > 0,
    )

    assert stale_looks == 0
    np.testing.assert_array_equal(after.looked_at[0].color, TABLE_AS_IT_IS_NOW)


# %% a look that fails still lets a later wait time out


@dataclass
class _PipelineThatFailsToDetect(MontessoriPerceptionPipeline):
    """
    A pipeline whose look always fails, as a real one can on a picture it cannot make
    sense of.
    """

    def detect(self, frame: RgbdFrame, request: SceneRequest = SceneRequest()):
        raise RuntimeError("the look failed")


def _wait_for_scene_capturing_the_outcome(
    perception: MontessoriPerceptionNode, outcome: List[BaseException]
) -> None:
    try:
        outcome.append(perception.wait_for_scene(A_SHORT_WAIT))
    except NoSceneAvailable as error:
        outcome.append(error)


def test_a_look_that_fails_lets_a_later_wait_time_out_instead_of_hanging_forever(
    node: Node,
):
    """
    A look that raises must not leave the node believing a look is still under way
    forever -- that would make every later wait for a scene keep pushing its deadline
    out and never give up.
    """
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())
    read_with_now = perception.pipeline
    perception.read_with(
        _PipelineThatFailsToDetect(
            table=read_with_now.table,
            lid=read_with_now.lid,
            reference_frame=read_with_now.reference_frame,
            world=read_with_now.world,
            pieces=read_with_now.pieces,
        )
    )
    frame = SceneCapture.load(A_LOOK).to_frame()

    with pytest.raises(RuntimeError):
        perception.look_at(frame)

    outcome: List[BaseException] = []
    waiting = threading.Thread(
        target=_wait_for_scene_capturing_the_outcome,
        args=(perception, outcome),
        daemon=True,
    )
    waiting.start()
    waiting.join(timeout=A_SHORT_WAIT * 10)

    assert not waiting.is_alive()
    assert len(outcome) == 1
    assert isinstance(outcome[0], NoSceneAvailable)


# %% logging wins even if something already configured the root logger without a level


def test_configuring_logging_wins_even_if_the_root_logger_is_already_configured():
    """
    coraplex's own package ``__init__`` calls ``logging.basicConfig`` at import time
    with no level -- reproduced here directly rather than by importing coraplex, since
    the process either has already imported it or never will again. Left as the first
    call to configure the root logger, it silently defeats a later plain
    ``logging.basicConfig(level=logging.INFO, ...)`` call, which is exactly why running
    the node reported nothing: every module logger stayed at the root's default
    :data:`logging.WARNING`.
    """
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        root.handlers = []
        root.setLevel(logging.WARNING)
        logging.basicConfig(format="%(levelname)s:%(filename)s::%(lineno)s %(message)s")

        configure_logging()

        node_logger = logging.getLogger("experiments.montessori.perception.node")
        assert root.getEffectiveLevel() == logging.INFO
        assert node_logger.getEffectiveLevel() == logging.INFO
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
