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

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from typing_extensions import Callable, List, Optional, TypeVar

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.board_publishing import BoardPublisher
from experiments.montessori.perception.camera import CameraTopic, RgbdFrame
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.exceptions import NoSceneAvailable
from experiments.montessori.perception.live_camera import LiveCamera
from experiments.montessori.perception.markers import DetectionMarkerPublisher
from experiments.montessori.perception.measured_plane import CameraPoseError
from experiments.montessori.perception.overlay import (
    DetectionOverlay,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import MontessoriSceneSource
from experiments.montessori.perception.scene_windows import SceneWindows
from experiments.montessori.perception.viewer import CameraFrameViewer
from experiments.montessori.pieces import SMALLER_PIECES
from experiments.montessori.semantics import ShapeSortingBoard
from experiments.network_limits import check_large_messages_can_arrive
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.robots.tracy import Tracy
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

    camera_pose_error: Optional[CameraPoseError] = field(init=False, default=None)
    """
    How far the camera's published pose is from levelling the table, read off the first
    look the node could place in the world, or None until one has been.
    """

    _camera: LiveCamera = field(init=False)
    """
    The newest of everything the camera publishes, and where it stands.
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
        self._camera = LiveCamera(node=self.node, color_callback=self._on_look)

    # %% each look

    def _on_look(self, _: CompressedImage) -> None:
        """
        Run the pipeline on the newest look, once a colour image has completed it.

        The bare images are shown only while the camera cannot be placed in the world,
        since a viewer that is about to be handed the same ones cut down to the
        workspace and drawn on would otherwise flash the bare ones first.
        """
        if (
            self._camera.missing_inputs()
            or time.monotonic() - self._last_run < self.minimum_period
        ):
            return
        self._last_run = time.monotonic()
        frame = self._build_frame()
        if frame is None:
            if self.viewer is not None:
                self.viewer.show_color(self._camera.color_image)
                self.viewer.show_depth(self._camera.depth_image)
            return
        if self.camera_pose_error is None:
            self.check_camera_pose(frame)
        scene = self.pipeline.detect(frame)
        with self._lock:
            self._scene = scene
            self._frame = frame
        if self.markers is not None:
            self.markers.publish(scene)
        if self.viewer is not None:
            self._show(frame, scene)

    def check_camera_pose(self, frame: RgbdFrame) -> CameraPoseError:
        """
        Read how far the camera's published pose is off against the table, keep the
        answer, and warn if it is more than the depth image's noise explains.

        The transform tree publishes whatever calibration the robot description was
        written with, and a camera that has moved since reports every detection from the
        wrong place; the table is flat and at a known height whatever the calibration
        says, so it is what the pose is checked against.

        :param frame: A look placed in the world by the published pose.
        """
        self.camera_pose_error = CameraPoseError.of(frame, self.pipeline.table)
        if not self.camera_pose_error.within_tolerance:
            self.node.get_logger().warning(
                f"the camera's published pose is off: {self.camera_pose_error}; "
                "recalibrate the camera link in the robot description"
            )
        return self.camera_pose_error

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

    def _missing_inputs(self) -> List[str]:
        """
        The inputs that have not arrived yet, for reporting why no scene is available.

        A colour image counts as missing until one has been looked at, since it is the
        one that completes a look.
        """
        missing = self._camera.missing_inputs()
        if self._scene is None and str(CameraTopic.COLOR) not in missing:
            missing.append(str(CameraTopic.COLOR))
        return missing

    def _build_frame(self) -> Optional[RgbdFrame]:
        """
        The newest look, in the pipeline's own reference frame.

        :return: The frame, or None while the pipeline has no reference frame or the
            camera's pose is not yet known to the transform tree.
        """
        reference_frame = self.pipeline.reference_frame
        if reference_frame is None:
            return None
        return self._camera.frame_in(str(reference_frame.name.name))

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
        table, for the pieces standing on it now.
    """
    [robot] = world.get_semantic_annotations_by_type(Tracy)
    return MontessoriPerceptionPipeline.of_world(world, robot.root, SMALLER_PIECES)


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
