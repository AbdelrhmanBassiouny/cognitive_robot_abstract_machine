#!/usr/bin/env python
from giskardpy.middleware.ros2 import rospy
from giskardpy.middleware.ros2.python_interface import GiskardWrapper
from giskardpy.motion_statechart.graph_node import EndMotion
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList, JointState
from semantic_digital_twin.datastructures.definitions import JointName


class UniversalRobotJoint(JointName):
    """
    The joints of a Universal Robots arm, in the order its velocity controller expects
    its commands.
    """

    SHOULDER_PAN = "shoulder_pan_joint"
    SHOULDER_LIFT = "shoulder_lift_joint"
    ELBOW = "elbow_joint"
    WRIST_1 = "wrist_1_joint"
    WRIST_2 = "wrist_2_joint"
    WRIST_3 = "wrist_3_joint"


def main() -> None:
    """
    Move two joints of the arm to a goal and wait until the motion ends.
    """
    rospy.init_node("giskard_client")
    giskard = GiskardWrapper(node_handle=rospy.get_node())
    goal_positions_in_radians = {
        UniversalRobotJoint.SHOULDER_PAN: 0.5,
        UniversalRobotJoint.ELBOW: 1.0,
    }

    motion_statechart = MotionStatechart()
    motion_statechart.add_node(
        joint_goal := JointPositionList(
            goal_state=JointState.from_str_dict(
                goal_positions_in_radians, giskard.world
            )
        )
    )
    motion_statechart.add_node(EndMotion.when_true(joint_goal))
    giskard.execute(motion_statechart)

    rospy.shutdown()


if __name__ == "__main__":
    main()
