#!/usr/bin/env python
from rclpy import Parameter

from giskardpy.qp.qp_controller_config import QPControllerConfig
from giskardpy.middleware.ros2.server_config import GiskardServerConfig
from giskardpy.middleware.ros2.giskard import Giskard
from giskardpy.middleware.ros2.scripts.iai_robots.pr2.configs import WorldWithPR2Config
from giskardpy.middleware.ros2.robot_interface_config import (
    StandAloneRobotInterfaceConfig,
)
from giskardpy.middleware.ros2 import rospy


def main():
    rospy.init_node("giskard")
    rospy.get_node().declare_parameters(
        namespace="", parameters=[("robot_description", Parameter.Type.STRING)]
    )
    robot_description = rospy.get_node().get_parameter_or("robot_description").value
    giskard = Giskard(
        world_config=WorldWithPR2Config(urdf=robot_description),
        robot_interface_config=StandAloneRobotInterfaceConfig(),
        server_config=GiskardServerConfig(debug_mode=True),
        qp_controller_config=QPControllerConfig(target_frequency=20),
    )
    giskard.live()


if __name__ == "__main__":
    main()
