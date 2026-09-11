"""
A ROS node that watches the Montessori scene continuously and answers queries about it.

Run it against the live robot with (the camera and the robot drivers must already be up
via ``ros2 launch iai_tracy_bringup tracy_ros2.launch.py``)::

    python -m experiments.montessori.perception.node

It subscribes to the colour and depth streams, runs
:class:`~experiments.montessori.perception.pipeline.MontessoriPerceptionPipeline` on each
pair, and keeps the newest result. That result is what an entity query language query
evaluated against
:class:`~experiments.montessori.perception.backend.MontessoriPerceptionBackend` is answered from,
and it is also drawn into rviz so the detections can be checked against the real table.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field

import numpy as np
import rclpy
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, CompressedImage
from typing_extensions import Callable, List, Optional, TypeVar

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.board_publishing import BoardPublisher
from experiments.montessori.perception.camera import (
    CameraIntrinsics,
    CameraTopic,
    RgbdFrame,
    decode_compressed_color_image,
    decode_compressed_depth_image,
)
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.exceptions import NoSceneAvailable
from experiments.montessori.perception.markers import DetectionMarkerPublisher
from experiments.montessori.perception.overlay import (
    DetectionOverlay,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import MontessoriSceneSource
from experiments.montessori.perception.scene_windows import SceneWindows
from experiments.montessori.perception.viewer import CameraFrameViewer
from experiments.montessori.semantics import ShapeSortingBoard
from experiments.network_limits import check_large_messages_can_arrive
from semantic_digital_twin.adapters.ros.tfwrapper import TFWrapper
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

logger = logging.getLogger(__name__)

NODE_NAME = "montessori_perception"
"""
Name this node registers under.
"""

REPORT_PERIOD_SECONDS = 1.0
"""
How often the scene is logged while the node runs.
"""

BOARD_SEARCH_PERIOD_SECONDS = 1.0
"""
How long the node waits before looking for the described board again, while no board
answering the description is in view.
"""

Held = TypeVar("Held")
"""
Whatever the node holds that a caller waits to arrive: a look, or a frame.
"""

# %% the node


@dataclass
class MontessoriPerceptionNode(MontessoriSceneSource):
    """
    Watches the Montessori scene continuously and serves the newest result.

    Answers a query evaluated against
    :class:`~experiments.montessori.perception.backend.MontessoriPerceptionBackend` with the most
    recent look at the table rather than one taken on demand -- the camera is already
    running, and a result that is one frame old beats blocking a plan on a fresh capture.
    """

    node: Node
    """
    The node subscriptions and transform lookups are made on.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    Turns a frame into detections.
    """

    minimum_period: float = 0.5
    """
    Shortest time between two pipeline runs, in seconds.

    The camera publishes far faster than the scene changes, and rectifying a full
    resolution frame twice is not worth doing at camera rate.
    """

    scene_check_period: float = 0.05
    """
    How long :meth:`wait_for_scene` waits between two checks for a result, in seconds.
    """

    markers: Optional[DetectionMarkerPublisher] = None
    """
    Draws the detections into rviz, or None to publish nothing.
    """

    viewer: Optional[CameraFrameViewer] = None
    """
    Shows the frames as they arrive, or None to open no window.
    """

    overlay: DetectionOverlay = field(default_factory=DetectionOverlay)
    """
    Draws the detections onto the frame the viewer shows.
    """

    _transforms: TFWrapper = field(init=False)
    """
    Reads where the camera stood when a frame was taken.
    """

    _intrinsics: Optional[CameraIntrinsics] = field(init=False, default=None)
    """
    The intrinsics the camera last reported.
    """

    _camera_frame: Optional[str] = field(init=False, default=None)
    """
    The frame the camera last reported its images in.
    """

    _latest_depth: Optional[CompressedImage] = field(init=False, default=None)
    """
    The newest depth image, held until a colour image arrives to pair it with.
    """

    _frame: Optional[RgbdFrame] = field(init=False, default=None)
    """
    The newest frame the pipeline ran on, kept for a look a request has to take afresh.
    """

    _scene: Optional[MontessoriScene] = field(init=False, default=None)
    """
    The newest result, or None until the first frame has been processed.
    """

    _last_run: float = field(init=False, default=0.0)
    """
    When the pipeline last ran, as a monotonic timestamp.
    """

    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    """
    Guards the newest result against being read while it is being replaced.
    """

    def __post_init__(self) -> None:
        self._transforms = TFWrapper(node=self.node)
        self.node.create_subscription(
            CameraInfo,
            CameraTopic.CAMERA_INFO,
            self._on_camera_info,
            qos_profile_sensor_data,
        )
        self.node.create_subscription(
            CompressedImage, CameraTopic.DEPTH, self._on_depth, qos_profile_sensor_data
        )
        self.node.create_subscription(
            CompressedImage, CameraTopic.COLOR, self._on_color, qos_profile_sensor_data
        )

    # %% subscriptions

    def _on_camera_info(self, message: CameraInfo) -> None:
        """
        Remember the intrinsics and the frame the camera reports its images in.

        :param message: The camera's own calibration.
        """
        self._intrinsics = CameraIntrinsics.from_camera_info_matrix(message.k)
        self._camera_frame = message.header.frame_id

    def _on_depth(self, message: CompressedImage) -> None:
        """
        Hold the newest depth image until a colour image arrives to pair it with.

        :param message: The depth image.
        """
        self._latest_depth = message

    def _on_color(self, message: CompressedImage) -> None:
        """
        Pair a colour image with the newest depth image and run the pipeline on the two.

        The bare images are shown only while the camera cannot be placed in the world,
        since a viewer that is about to be handed the same ones cut down to the
        workspace and drawn on would otherwise flash the bare ones first.

        :param message: The colour image.
        """
        if not self._ready() or time.monotonic() - self._last_run < self.minimum_period:
            return
        self._last_run = time.monotonic()
        color = decode_compressed_color_image(message.data, message.format)
        depth = decode_compressed_depth_image(
            self._latest_depth.data, self._latest_depth.format
        )
        frame = self._build_frame(color, depth)
        if frame is None:
            if self.viewer is not None:
                self.viewer.show_color(color)
                self.viewer.show_depth(depth)
            return
        scene = self.pipeline.detect(frame)
        with self._lock:
            self._scene = scene
            self._frame = frame
        if self.markers is not None:
            self.markers.publish(scene)
        if self.viewer is not None:
            self._show(frame, scene)

    def _show(self, frame: RgbdFrame, scene: MontessoriScene) -> None:
        """
        Draw one look at the scene, on the camera's own image and on the top-down view
        the outlines were measured in.

        :param frame: The frame the detections were found in.
        :param scene: The detections to draw.
        """
        SceneWindows(
            pipeline=self.pipeline, viewer=self.viewer, overlay=self.overlay
        ).show(frame, scene)

    def _ready(self) -> bool:
        """
        Whether everything the pipeline needs has arrived at least once.
        """
        return self._intrinsics is not None and self._latest_depth is not None

    def _missing_inputs(self) -> List[str]:
        """
        The inputs that have not arrived yet, for reporting why no scene is available.
        """
        missing = []
        if self._intrinsics is None:
            missing.append(str(CameraTopic.CAMERA_INFO))
        if self._latest_depth is None:
            missing.append(str(CameraTopic.DEPTH))
        if self._scene is None:
            missing.append(str(CameraTopic.COLOR))
        return missing

    def _build_frame(self, color: np.ndarray, depth: np.ndarray) -> Optional[RgbdFrame]:
        """
        Assemble one colour image, the depth image taken with it, and the camera's pose
        into a frame the pipeline can read.

        :param color: The colour image, blue/green/red.
        :param depth: The depth image in metres.
        :return: The frame, or None while the camera's pose is not yet known to the
            transform tree.
        """
        reference_frame_T_camera = self._camera_pose()
        if reference_frame_T_camera is None:
            return None
        return RgbdFrame(
            color=color,
            depth=depth,
            intrinsics=self._intrinsics,
            reference_frame_T_camera=reference_frame_T_camera,
        )

    def _camera_pose(self) -> Optional[np.ndarray]:
        """
        Where the camera stands, in the pipeline's own reference frame.

        Reads the newest transform rather than the one stamped on the image: this camera
        is bolted to the robot's own table, so its pose does not move between the frame
        being taken and being processed, and asking for a past stamp only risks falling
        off the back of the transform buffer.

        :return: The camera's pose as a 4x4 homogeneous transformation, or None while
            the transform tree cannot yet answer for that frame.
        """
        reference_frame = self.pipeline.reference_frame
        if reference_frame is None or self._camera_frame is None:
            return None
        if not self._transforms.wait_for_transform(
            str(reference_frame.name.name),
            self._camera_frame,
            Time(),
            Duration(seconds=0.2),
        ):
            return None
        transform = self._transforms.lookup_transform(
            str(reference_frame.name.name), self._camera_frame
        ).transform
        return HomogeneousTransformationMatrix.from_xyz_quaternion(
            transform.translation.x,
            transform.translation.y,
            transform.translation.z,
            transform.rotation.x,
            transform.rotation.y,
            transform.rotation.z,
            transform.rotation.w,
        ).to_np()

    # %% serving results

    @property
    def reference_frame(self) -> Optional[KinematicStructureEntity]:
        """
        The frame this node's pipeline places its detections in.
        """
        return self.pipeline.reference_frame

    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        """
        Serve the newest look, whatever the request narrowed it to.

        The camera is already running and the pipeline already searches every surface
        for rviz, so a request cannot narrow a look that has been taken: answering from
        the newest result costs nothing, where taking a fresh one would block a plan on
        a capture. Whoever asked keeps filtering. A request describing a board is the
        exception: the running look was not asked to fit that board's layout, so the
        newest frame is looked at afresh for it.

        :param request: What the look was asked for.
        :return: The newest result the pipeline produced, or a fresh look at the newest
            frame for a request describing a board.
        """
        if request.described_board is not None:
            return self.pipeline.detect(self.wait_for_frame(), request)
        return self.wait_for_scene()

    def wait_for_scene(self, timeout_seconds: float = 20.0) -> MontessoriScene:
        """
        Block until the pipeline has produced a result.

        :param timeout_seconds: How long to wait before giving up.
        :return: The newest result, as soon as there is one.
        :raises NoSceneAvailable: If nothing arrived within the timeout.
        """
        return self._wait_for(lambda: self._scene, timeout_seconds)

    def wait_for_frame(self, timeout_seconds: float = 20.0) -> RgbdFrame:
        """
        Block until the pipeline has run on a frame.

        :param timeout_seconds: How long to wait before giving up.
        :return: The newest frame, as soon as there is one.
        :raises NoSceneAvailable: If nothing arrived within the timeout.
        """
        return self._wait_for(lambda: self._frame, timeout_seconds)

    def _wait_for(
        self, newest: Callable[[], Optional[Held]], timeout_seconds: float
    ) -> Held:
        """
        Block until something this node holds has arrived.

        :param newest: Reads what the node holds now, None until it has arrived.
        :param timeout_seconds: How long to wait before giving up.
        :return: What arrived.
        :raises NoSceneAvailable: If nothing arrived within the timeout.
        """
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            with self._lock:
                held = newest()
            if held is not None:
                return held
            time.sleep(self.scene_check_period)
        raise NoSceneAvailable(timeout_seconds, self._missing_inputs())


# %% running it


def build_node(
    node: Node,
    world: World,
    draw_markers: bool = True,
    show_images: bool = False,
) -> MontessoriPerceptionNode:
    """
    Wire the perception node against the live robot's world, which says which stretch of
    table the scene stands on, how high its surfaces lie, and which frame to report
    poses in.

    :param node: The node to subscribe and publish on.
    :param world: The world the robot publishes.
    :param draw_markers: Whether to draw the detections into rviz.
    :param show_images: Whether to open a window on each camera stream.
    :return: The wired, already-subscribing perception node.
    """
    reference_frame: KinematicStructureEntity = world.root
    pipeline = pipeline_of(world)
    logger.info(
        "Watching %s: table top at z=%.3f, poses in %s.",
        pipeline.table.region,
        pipeline.table.height,
        reference_frame.name,
    )
    markers = (
        DetectionMarkerPublisher(node=node, reference_frame=reference_frame)
        if draw_markers
        else None
    )
    return MontessoriPerceptionNode(
        node=node,
        pipeline=pipeline,
        markers=markers,
        viewer=CameraFrameViewer() if show_images else None,
    )


def pipeline_of(world: World) -> MontessoriPerceptionPipeline:
    """
    :param world: The world the robot publishes.
    :return: The pipeline looking at the scene that world describes, on the robot's own
        table.
    """
    [robot] = world.get_semantic_annotations_by_type(Tracy)
    return MontessoriPerceptionPipeline.of_world(world, robot.root)


def find_board(
    perception: MontessoriPerceptionNode, described: DescribedBoard
) -> ShapeSortingBoard:
    """
    Look until a board answering a description is in view.

    :param perception: The node to look through.
    :param described: The board to look for.
    :return: The board, standing where it was found in the world the look brought its
        findings into.
    """
    looking = MontessoriPerceptionBackend(source=perception)
    while True:
        found = list(described.statement().evaluate(backend=looking))
        if found:
            return found[0]
        logger.info("No board answering the description is in view yet.")
        time.sleep(BOARD_SEARCH_PERIOD_SECONDS)


def hold_board(world: World, perception: MontessoriPerceptionNode) -> ShapeSortingBoard:
    """
    Have the world the robot publishes hold the shape-sorting board on this table.

    A world holding no board has the board looked for by the description of the board on
    this table, and the board found published into it, so every process keeping that
    world in step holds it too.

    :param world: The world the robot publishes.
    :param perception: The node to look through, whose pipeline then reads the published
        board's lid.
    :return: The board the world holds.
    """
    held = ShapeSortingBoard.held_by(world)
    if held is not None:
        return held
    described = lab_board()
    published = BoardPublisher(world=world).publish(
        described, find_board(perception, described)
    )
    logger.info("Found the board and published it as %s.", published.name)
    perception.pipeline = pipeline_of(world)
    return published


def parse_arguments() -> Namespace:
    """
    Read the options this node is run with.
    """
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-images",
        action="store_true",
        help="open a window on each camera stream, to watch the frames arriving",
    )
    return parser.parse_args()


def report(scene: MontessoriScene) -> None:
    """
    Log what a scene holds and where.

    :param scene: The scene to report.
    """
    logger.info(
        "%d pieces, %d holes: %s",
        len(scene.shapes),
        len(scene.holes),
        ", ".join(
            f"{piece.category} at "
            f"({piece.pose.to_position().to_np()[0]:.3f}, "
            f"{piece.pose.to_position().to_np()[1]:.3f}) "
            f"turned {math.degrees(piece.yaw):+.0f} deg, fit {piece.outline_agreement:.2f}"
            for piece in scene.shapes
        ),
    )


def main() -> None:
    """
    Run the perception node until interrupted, logging what it sees.

    A world the robot publishes without a shape-sorting board has the board looked for
    first, by the description of the board on this table, and the board found is
    published into that world so every process keeping it in step holds it too.
    """
    arguments = parse_arguments()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    check_large_messages_can_arrive()
    rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor").start()

    world = fetch_world_from_service(node=node, timeout_seconds=300)
    WorldSynchronizer(_world=world, node=node)
    perception = build_node(node, world, show_images=arguments.show_images)
    hold_board(world, perception)
    report(perception.wait_for_scene())
    next_report = time.monotonic() + REPORT_PERIOD_SECONDS
    while rclpy.ok():
        if time.monotonic() >= next_report:
            next_report = time.monotonic() + REPORT_PERIOD_SECONDS
            report(perception.scene())
        if perception.viewer is None:
            time.sleep(REPORT_PERIOD_SECONDS)
            continue
        perception.viewer.refresh()


if __name__ == "__main__":
    main()
