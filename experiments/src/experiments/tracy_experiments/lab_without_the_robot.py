"""
The lab's ROS side without the robot and the camera: everything the real pickup demo
reaches over ROS, served by this process from Tracy's description and a capture, so a
run is recorded and checked exactly as it is on the robot before anyone stands at it.

What the demo reaches is the robot's own, and it is reached the same way: the world is
served by the service the bringup runs and fetched, synchronized and drawn as it is
there; the camera publishes a capture's colour and depth over the transports the camera
uses, its calibration, and where it stood over the transform tree; each gripper is
driven through the action its Robotiq driver serves, with the fingers closing in the
published world and the driver's joint state reported as the driver reports it. The
arm's motions are the one thing a rehearsal runs differently, and that is the demo's own
choice rather than this module's: through Giskard in the demo's process against the
world's own joints, rather than through Giskard's node on the robot.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from dataclasses import dataclass, field

import numpy as np
import rclpy
from control_msgs.action import ParallelGripperCommand
from geometry_msgs.msg import TransformStamped
from rclpy.action import ActionServer
from rclpy.action.server import ServerGoalHandle
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.publisher import Publisher
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage, Image, JointState
from tf2_ros import StaticTransformBroadcaster
from typing_extensions import Dict, Iterator, List, Optional

from coraplex.datastructures.enums import Arms
from experiments.montessori.perception.camera import (
    COMPRESSED_DEPTH_IN_MILLIMETRES_FORMAT,
    MILLIMETRES_PER_METRE,
    CameraTopic,
    ImageEncoding,
    encode_compressed_depth_image,
)
from experiments.montessori.perception.captures import CapturePart, SceneCapture
from experiments.montessori.perception.recordings import RAW_DEPTH_TOPIC
from experiments.montessori.semantics import MontessoriShape
from experiments.tracy_experiments.equipment import parse_tracy
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    OPEN_KNUCKLE_POSITION,
    gripper_joint_state_topic,
    knuckle_joint_name,
)
from experiments.tracy_experiments.robotiq_gripper import (
    FingerSetpoint,
    gripper_action_name,
)
from experiments.tracy_experiments.rosbag_recording import DEFAULT_TOPICS
from semantic_digital_twin.adapters.ros.world_fetcher import FetchWorldServer
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom

logger = logging.getLogger(__name__)

LAB_NODE_NAME = "lab_without_the_robot"
"""
The name the node serving the lab's side registers under.
"""

CAMERA_FRAME = "camera_color_optical_frame"
"""
The frame the camera's calibration says its images are taken in.
"""

CAMERA_QUEUE_DEPTH = 5
"""
How many raw depth frames a publisher keeps for a subscriber that falls behind.
"""

CAMERA_PERIOD_SECONDS = 0.25
"""
How often the camera publishes its streams again.

Slower than the camera, since the demo's perception node looks at every frame it is
shown as often as it is willing to and a rehearsal shares one process between those
looks and the arm's motions, which in the lab run in a process of their own; and fast
enough that a bag holds a frame within a quarter second of any moment of the run.
"""

DEPTH_CAMERA_INFO_TOPIC = "/camera/depth/camera_info"
"""
Where the camera publishes the depth stream's calibration, which is the colour stream's
once the depth is registered onto it.
"""

RAW_DEPTH_QUALITY_OF_SERVICE = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE, depth=CAMERA_QUEUE_DEPTH
)
"""
How the raw depth is published: reliably, unlike the camera, since a frame of several
megabytes sent best-effort over this machine's own loopback is fragmented and mostly
lost, and a bag that holds no depth before a colour frame cannot place that frame.
"""

MERGED_JOINT_STATE_TOPIC = "/joint_states"
"""
Where every joint of the robot is published together, as the bringup's joint state
publisher does.
"""

JOINT_STATE_PERIOD_SECONDS = 0.1
"""
How often the joint states are published again.
"""

PIECE_WITHIN_THE_FINGERS = 0.06
"""
How far, in metres, a loose piece's centre may stand from the tool frame for the fingers
to meet it when they close: the demo reaches a piece from
:data:`~experiments.tracy_experiments.pickup.pickup_demo_real.GRASP_HEIGHT_OFFSET` above
its centre, and the pieces of a row stand further apart than this.
"""

KNUCKLE_POSITION_ON_A_PIECE = 0.4
"""
Where the fingers stop when they close on a piece, in knuckle radians: half way, well
short of fully closed, which is where the demo reads a hold rather than an empty close.
"""


def tracys_description() -> World:
    """
    The world the bringup publishes before anything is stood in it: Tracy on its own
    table, as its description gives it.
    """
    world = parse_tracy()
    Tracy.from_world(world)
    return world


# %% the world the robot publishes


@dataclass
class PublishedWorld:
    """
    The world the bringup publishes: served over the world service every process fetches
    it from, and kept in step with every process that has.
    """

    node: Node
    """
    The node the service is served and the synchronization published on.
    """

    world: World
    """
    The world served.
    """

    _service: FetchWorldServer = field(init=False)
    """
    The service the world is fetched over.
    """

    def __post_init__(self) -> None:
        self._service = FetchWorldServer(node=self.node, world=self.world)
        WorldSynchronizer(_world=self.world, node=self.node)

    def close(self) -> None:
        """
        Stop serving the world.
        """
        self._service.close()


# %% the camera


@dataclass
class CaptureCamera:
    """
    The camera, showing one capture: publishes the capture's colour and depth over the
    transports the camera uses and the raw depth a bag records, its calibration, and
    where it stood over the static transform tree, each anew every period as a camera
    does.
    """

    node: Node
    """
    The node the streams are published on.
    """

    capture: SceneCapture
    """
    The capture shown.
    """

    reference_frame: str
    """
    The frame the capture's pose is published against, which is the published world's
    root.
    """

    period: float = CAMERA_PERIOD_SECONDS
    """
    Seconds between two publications of the streams.
    """

    _color: CompressedImage = field(init=False)
    """
    The colour image, as the capture keeps it.
    """

    _depth: CompressedImage = field(init=False)
    """
    The depth image over the compressed transport.
    """

    _raw_depth: Image = field(init=False)
    """
    The depth image over the raw transport.
    """

    _camera_info: CameraInfo = field(init=False)
    """
    The calibration both images were taken with.
    """

    _transforms: StaticTransformBroadcaster = field(init=False)
    """
    Where the camera's pose is published.
    """

    _publishers: Dict[str, Publisher] = field(init=False, default_factory=dict)
    """
    The publisher of each stream, by topic.
    """

    def __post_init__(self) -> None:
        self._transforms = StaticTransformBroadcaster(self.node)
        for topic, message_type, quality_of_service in (
            (CameraTopic.COLOR, CompressedImage, qos_profile_sensor_data),
            (CameraTopic.DEPTH, CompressedImage, qos_profile_sensor_data),
            (RAW_DEPTH_TOPIC, Image, RAW_DEPTH_QUALITY_OF_SERVICE),
            (CameraTopic.CAMERA_INFO, CameraInfo, qos_profile_sensor_data),
            (DEPTH_CAMERA_INFO_TOPIC, CameraInfo, qos_profile_sensor_data),
        ):
            self._publishers[str(topic)] = self.node.create_publisher(
                message_type, str(topic), quality_of_service
            )
        self.show(self.capture)
        self.node.create_timer(self.period, self.publish)

    @property
    def published_topics(self) -> List[str]:
        """
        The topics this camera publishes on.
        """
        return list(self._publishers)

    def show(self, capture: SceneCapture) -> None:
        """
        Publish this capture from now on, from where it was taken.

        :param capture: The capture shown.
        """
        self.capture = capture
        millimetres = np.round(capture.to_frame().depth * MILLIMETRES_PER_METRE).astype(
            np.uint16
        )
        height, width = millimetres.shape
        self._color = CompressedImage(
            format=capture.color_format,
            data=capture.path_to(CapturePart.COLOR).read_bytes(),
        )
        self._depth = CompressedImage(
            format=COMPRESSED_DEPTH_IN_MILLIMETRES_FORMAT,
            data=encode_compressed_depth_image(millimetres),
        )
        self._raw_depth = Image(
            height=height,
            width=width,
            encoding=str(ImageEncoding.DEPTH_IN_MILLIMETRES),
            step=width * millimetres.itemsize,
            data=millimetres.tobytes(),
        )
        self._camera_info = CameraInfo(
            height=height,
            width=width,
            k=capture.intrinsics.to_matrix().flatten().tolist(),
        )
        self._transforms.sendTransform(self._where_it_stood(capture))
        self.publish()

    def _where_it_stood(self, capture: SceneCapture) -> TransformStamped:
        """
        :param capture: A capture.
        :return: Where its camera stood, as the transform tree carries it.
        """
        pose = HomogeneousTransformationMatrix(capture.reference_frame_T_camera)
        x, y, z = pose.to_position().to_np()[:3]
        qx, qy, qz, qw = pose.to_quaternion().to_np()
        transform = TransformStamped()
        transform.header.stamp = self.node.get_clock().now().to_msg()
        transform.header.frame_id = self.reference_frame
        transform.child_frame_id = CAMERA_FRAME
        transform.transform.translation.x = float(x)
        transform.transform.translation.y = float(y)
        transform.transform.translation.z = float(z)
        transform.transform.rotation.x = float(qx)
        transform.transform.rotation.y = float(qy)
        transform.transform.rotation.z = float(qz)
        transform.transform.rotation.w = float(qw)
        return transform

    def publish(self) -> None:
        """
        Publish every stream once, stamped now, the depth before the colour as the
        camera does.
        """
        stamp = self.node.get_clock().now().to_msg()
        for topic, message in (
            (CameraTopic.CAMERA_INFO, self._camera_info),
            (DEPTH_CAMERA_INFO_TOPIC, self._camera_info),
            (CameraTopic.DEPTH, self._depth),
            (RAW_DEPTH_TOPIC, self._raw_depth),
            (CameraTopic.COLOR, self._color),
        ):
            message.header.stamp = stamp
            message.header.frame_id = CAMERA_FRAME
            self._publishers[str(topic)].publish(message)


# %% the grippers' drivers


@dataclass
class GripperDriverInTheWorld:
    """
    One arm's Robotiq driver, standing in: serves the gripper command action, closes and
    opens the fingers in the published world, and reports the gripper's joint state as
    the driver does.

    The fingers meet a loose piece standing within :data:`PIECE_WITHIN_THE_FINGERS` of
    the tool frame: a close then stalls where the fingers stop on the piece rather than
    reaching the position it was given, which is how the driver reports a grasp, and a
    close on nothing reaches it.
    """

    node: Node
    """
    The node the action is served and the joint state published on.
    """

    world: World
    """
    The published world the fingers close in.
    """

    robot: Tracy
    """
    The robot the gripper belongs to, as the published world holds it.
    """

    arm: Arms
    """
    The arm whose gripper this drives.
    """

    period: float = JOINT_STATE_PERIOD_SECONDS
    """
    Seconds between two publications of the joint state.
    """

    _knuckle: DegreeOfFreedom = field(init=False)
    """
    The knuckle joint the fingers close by.
    """

    _server: ActionServer = field(init=False)
    """
    The action the gripper is commanded through.
    """

    _joint_states: Publisher = field(init=False)
    """
    Where the gripper's joint state is published.
    """

    def __post_init__(self) -> None:
        self._knuckle = self.world.get_degree_of_freedom_by_name(
            knuckle_joint_name(self.arm)
        )
        self._server = ActionServer(
            self.node,
            ParallelGripperCommand,
            gripper_action_name(self.arm),
            self.execute,
        )
        self._joint_states = self.node.create_publisher(
            JointState, gripper_joint_state_topic(self.arm), qos_profile_sensor_data
        )
        self.node.create_timer(self.period, self.publish_joint_state)

    @property
    def knuckle_position(self) -> float:
        """
        Where the knuckle stands, in radians.
        """
        return float(self.world.state[self._knuckle.id].position)

    @property
    def tool_frame_position(self) -> np.ndarray:
        """
        Where the arm's tool frame stands, in the world root frame.
        """
        end_effector = (
            self.robot.left_arm if self.arm is Arms.LEFT else self.robot.right_arm
        ).end_effector
        return end_effector.tool_frame.global_transform.to_position().to_np()[:3]

    def fingers_meet_a_piece(self) -> bool:
        """
        Whether a loose piece stands within :data:`PIECE_WITHIN_THE_FINGERS` of the tool
        frame, where the fingers close on it.
        """
        tool_frame = self.tool_frame_position
        return any(
            np.linalg.norm(
                piece.root.global_transform.to_position().to_np()[:3] - tool_frame
            )
            <= PIECE_WITHIN_THE_FINGERS
            for piece in self.world.get_semantic_annotations_by_type(MontessoriShape)
        )

    @staticmethod
    def knuckle_position_for(setpoint: float) -> float:
        """
        :param setpoint: A finger setpoint in the driver's own units.
        :return: Where the knuckle stands once the fingers have reached it: the
            setpoint's share of :attr:`FingerSetpoint.CLOSED` along the knuckle's travel.
        """
        share = min(setpoint / float(FingerSetpoint.CLOSED), 1.0)
        return OPEN_KNUCKLE_POSITION + share * (
            FULLY_CLOSED_KNUCKLE_POSITION - OPEN_KNUCKLE_POSITION
        )

    def execute(self, goal_handle: ServerGoalHandle) -> ParallelGripperCommand.Result:
        """
        Carry one command out: move the fingers, or stop them on the piece they meet.

        :param goal_handle: The accepted command.
        """
        asked = self.knuckle_position_for(goal_handle.request.command.position[0])
        stalled = asked > KNUCKLE_POSITION_ON_A_PIECE and self.fingers_meet_a_piece()
        self.move_knuckle_to(KNUCKLE_POSITION_ON_A_PIECE if stalled else asked)
        goal_handle.succeed()
        return ParallelGripperCommand.Result(
            state=self.joint_state(), stalled=stalled, reached_goal=not stalled
        )

    def move_knuckle_to(self, position: float) -> None:
        """
        Put the knuckle at a position, in the published world.

        :param position: Where, in radians.
        """
        self.world.state[self._knuckle.id].position = position
        self.world.notify_state_change()
        self.publish_joint_state()

    def joint_state(self) -> JointState:
        """
        The gripper's joint state as the driver reports it: the knuckle's position.
        """
        message = JointState()
        message.header.stamp = self.node.get_clock().now().to_msg()
        message.name = [knuckle_joint_name(self.arm)]
        message.position = [self.knuckle_position]
        return message

    def publish_joint_state(self) -> None:
        """
        Publish the gripper's joint state once.
        """
        self._joint_states.publish(self.joint_state())


# %% every joint, published together


@dataclass
class JointStatePublisher:
    """
    Publishes where every joint of the published world stands, together, as the
    bringup's joint state publisher does.
    """

    node: Node
    """
    The node the joint states are published on.
    """

    world: World
    """
    The world whose joints are published.
    """

    period: float = JOINT_STATE_PERIOD_SECONDS
    """
    Seconds between two publications.
    """

    _publisher: Publisher = field(init=False)
    """
    Where the joint states are published.
    """

    def __post_init__(self) -> None:
        self._publisher = self.node.create_publisher(
            JointState, MERGED_JOINT_STATE_TOPIC, qos_profile_sensor_data
        )
        self.node.create_timer(self.period, self.publish)

    def publish(self) -> None:
        """
        Publish every joint's position once, read off the state in one go.
        """
        message = JointState()
        message.header.stamp = self.node.get_clock().now().to_msg()
        names_by_id = {dof.id: dof.name.name for dof in self.world.degrees_of_freedom}
        message.name = [names_by_id[dof_id] for dof_id in self.world.state.keys()]
        message.position = [float(position) for position in self.world.state.positions]
        self._publisher.publish(message)


# %% the lab brought up


@dataclass
class LabWithoutTheRobot:
    """
    The lab's ROS side without the robot and the camera, brought up on a node of this
    process's own.
    """

    node: Node
    """
    The node everything is served on.
    """

    published: PublishedWorld
    """
    The world the robot publishes.
    """

    camera: CaptureCamera
    """
    The camera, showing a capture.
    """

    grippers: List[GripperDriverInTheWorld]
    """
    The drivers of both grippers.
    """

    @property
    def world(self) -> World:
        """
        The world the robot publishes.
        """
        return self.published.world

    @property
    def published_topics(self) -> List[str]:
        """
        The topics a bag of a run on the robot records that this lab publishes.
        """
        published = {
            *self.camera.published_topics,
            MERGED_JOINT_STATE_TOPIC,
            *(gripper_joint_state_topic(gripper.arm) for gripper in self.grippers),
        }
        return [topic for topic in DEFAULT_TOPICS if topic in published]

    @classmethod
    @contextlib.contextmanager
    def brought_up(
        cls,
        capture: SceneCapture,
        world: Optional[World] = None,
        node_name: str = LAB_NODE_NAME,
    ) -> Iterator[LabWithoutTheRobot]:
        """
        Bring the lab up for as long as the block runs.

        ROS must already be initialised. The node is spun on a thread of its own.

        :param capture: The capture the camera shows.
        :param world: The world the robot publishes; Tracy's description when None.
        :param node_name: The name the node registers under.
        """
        node = rclpy.create_node(node_name)
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        spinner = threading.Thread(target=executor.spin, daemon=True, name=node_name)
        spinner.start()
        try:
            if world is None:
                world = tracys_description()
            [robot] = world.get_semantic_annotations_by_type(Tracy)
            published = PublishedWorld(node=node, world=world)
            JointStatePublisher(node=node, world=world)
            lab = cls(
                node=node,
                published=published,
                camera=CaptureCamera(
                    node=node, capture=capture, reference_frame=world.root.name.name
                ),
                grippers=[
                    GripperDriverInTheWorld(
                        node=node, world=world, robot=robot, arm=arm
                    )
                    for arm in (Arms.LEFT, Arms.RIGHT)
                ],
            )
            logger.info(
                "Lab without the robot: serving %s, showing %s.",
                world.root.name,
                capture.name,
            )
            yield lab
        finally:
            executor.shutdown()
            spinner.join()
            node.destroy_node()
