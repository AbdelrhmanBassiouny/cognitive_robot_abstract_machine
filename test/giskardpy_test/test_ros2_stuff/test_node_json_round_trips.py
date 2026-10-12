"""
Every motion statechart node class that talks to ROS sent through JSON inside a
statechart.
"""

from __future__ import annotations

from enum import StrEnum

import pytest
from geometry_msgs.msg import WrenchStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer
from rclpy.action.server import ServerGoalHandle
from rclpy.node import Node
from typing_extensions import Iterator

from cramph.context import StatechartContext
from cramph.executor import StatechartExecutor
from cramph.node import StatechartNode
from giskardpy.motion_control import MotionControl
from giskardpy.motion_statechart import ros2_nodes
from giskardpy.motion_statechart.ros2_nodes.force_torque_monitor import (
    ForceImpactMonitor,
    ForceTorqueNode,
)
from giskardpy.motion_statechart.ros2_nodes.ros_tasks import NavigateActionServerTask
from giskardpy.motion_statechart.ros2_nodes.topic_monitor import (
    PublishOnStart,
    TopicNode,
    TopicPublisherNode,
    TopicSubscriberNode,
    WaitForMessage,
)
from giskardpy.motion_statechart.ros_context import RosNodeAccess
from semantic_digital_twin.spatial_types.spatial_types import Pose

from ..motion_control_context import create_context_with_motion_control
from ...statechart_json_round_trip import (
    NodeRoundTripCase,
    NodeRoundTripTests,
    concrete_node_types,
)

# %% nodes of the cases


class RosName(StrEnum):
    """
    The names the nodes of the cases talk to ROS under.
    """

    WRENCH_TOPIC = "wrench"
    NAVIGATION_ACTION = "navigate"


def _cases() -> list[NodeRoundTripCase]:
    """
    :return: One case per motion statechart node class that talks to ROS.
    """
    return [
        NodeRoundTripCase(
            ForceTorqueNode,
            lambda world: [ForceTorqueNode(topic_name=RosName.WRENCH_TOPIC)],
        ),
        NodeRoundTripCase(
            ForceImpactMonitor,
            lambda world: [
                ForceImpactMonitor(topic_name=RosName.WRENCH_TOPIC, threshold=10)
            ],
        ),
        NodeRoundTripCase(
            WaitForMessage,
            lambda world: [
                WaitForMessage(topic_name=RosName.WRENCH_TOPIC, msg_type=WrenchStamped)
            ],
        ),
        NodeRoundTripCase(
            PublishOnStart,
            lambda world: [
                PublishOnStart(topic_name=RosName.WRENCH_TOPIC, msg=WrenchStamped())
            ],
        ),
        NodeRoundTripCase(
            NavigateActionServerTask,
            lambda world: [
                NavigateActionServerTask(
                    action_topic=RosName.NAVIGATION_ACTION,
                    message_type=NavigateToPose,
                    target_pose=Pose.from_xyz_rpy(x=0.1, reference_frame=world.root),
                    base_link=world.get_kinematic_structure_entity_by_name("tip"),
                )
            ],
        ),
    ]


def _node_types_never_added_to_a_statechart() -> set[type[StatechartNode]]:
    """
    :return: The node classes that only hold what their subclasses share.
    """
    return {TopicNode, TopicSubscriberNode, TopicPublisherNode}


# %% sender and receiver


@pytest.fixture(params=_cases(), ids=lambda case: case.node_type.__name__)
def case(request: pytest.FixtureRequest) -> NodeRoundTripCase:
    return request.param


def _reach_the_goal_at_once(goal: ServerGoalHandle) -> NavigateToPose.Result:
    goal.succeed()
    return NavigateToPose.Result()


@pytest.fixture(autouse=True)
def navigation_action_server(rclpy_node: Node) -> Iterator[ActionServer]:
    """
    :return: The action server the navigation task waits for before it is built.
    """
    server = ActionServer(
        rclpy_node,
        NavigateToPose,
        RosName.NAVIGATION_ACTION,
        _reach_the_goal_at_once,
    )
    yield server
    server.destroy()


@pytest.fixture()
def cases() -> list[NodeRoundTripCase]:
    return _cases()


@pytest.fixture()
def node_types_needing_a_case() -> set[type[StatechartNode]]:
    return concrete_node_types(ros2_nodes) - _node_types_never_added_to_a_statechart()


@pytest.fixture()
def sending_context(
    case: NodeRoundTripCase, request: pytest.FixtureRequest, rclpy_node: Node
) -> StatechartContext:
    context = create_context_with_motion_control(
        request.getfixturevalue(case.world_fixture)
    )
    RosNodeAccess(rclpy_node).extend_context(context)
    return context


@pytest.fixture()
def receiving_executor(
    case: NodeRoundTripCase, request: pytest.FixtureRequest, rclpy_node: Node
) -> StatechartExecutor:
    return StatechartExecutor(
        context=StatechartContext(world=request.getfixturevalue(case.world_fixture)),
        extensions=[RosNodeAccess(rclpy_node), MotionControl()],
    )


# %% round trips


class TestRosNodeRoundTrips(NodeRoundTripTests):
    pass
