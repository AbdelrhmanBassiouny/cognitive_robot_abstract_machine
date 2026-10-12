import json

from geometry_msgs.msg import WrenchStamped

from cramph.data_types import ObservationStateValues
from cramph.composites import Sequence, Parallel
from giskardpy.motion_statechart.graph_node import EndMotion
from cramph.statechart import Statechart
from giskardpy.motion_statechart.ros2_nodes.force_torque_monitor import (
    ForceImpactMonitor,
)
from giskardpy.motion_statechart.ros2_nodes.topic_monitor import (
    PublishOnStart,
    WaitForMessage,
)
from semantic_digital_twin.world import World
from giskardpy.motion_control import MotionControl
from giskardpy.motion_statechart.ros_context import RosNodeAccess
from cramph.context import StatechartContext
from cramph.executor import StatechartExecutor


def test_force_impact_node(rclpy_node):
    topic_name = "force_torque_topic"

    msg_below = WrenchStamped()

    msg_above = WrenchStamped()
    msg_above.wrench.force.x = 20.0

    msc = Statechart()
    msc.add_node(
        parallel := Parallel(
            [
                ForceImpactMonitor(topic_name=topic_name, threshold=10),
                Sequence(
                    nodes=[
                        PublishOnStart(topic_name=topic_name, msg=msg_below),
                        WaitForMessage(topic_name=topic_name, msg_type=WrenchStamped),
                        PublishOnStart(topic_name=topic_name, msg=msg_above),
                    ]
                ),
            ]
        )
    )
    msc.add_node(EndMotion.when_true(parallel))

    json_data = msc.to_json()
    json_str = json.dumps(json_data)
    new_json_data = json.loads(json_str)
    msc_copy = Statechart.from_json(new_json_data)

    kin_sim = StatechartExecutor(
        context=StatechartContext(world=World()),
        extensions=[RosNodeAccess(rclpy_node), MotionControl()],
    )
    kin_sim.compile(statechart=msc_copy)

    ft_node = msc_copy.nodes[0].nodes[0]

    kin_sim.tick_until_end(timeout=5_000)
    msc_copy.draw("muh.pdf")
    assert (
        msc_copy.history.get_observation_history_of_node(ft_node)[0]
        == ObservationStateValues.UNKNOWN
    )
    assert (
        ObservationStateValues.FALSE
        in msc_copy.history.get_observation_history_of_node(ft_node)
    )
    assert (
        msc_copy.history.get_observation_history_of_node(ft_node)[-1]
        == ObservationStateValues.TRUE
    )
