#!/usr/bin/env python
from giskardpy.middleware.ros2 import rospy
from giskardpy.middleware.ros2.giskard import Giskard
from giskardpy.middleware.ros2.robot_interface_config import (
    StandAloneRobotInterfaceConfig,
)
from giskardpy.middleware.ros2.scripts.iai_robots.hsr.configs import (
    WorldWithHSRConfig,
)
from giskardpy.middleware.ros2.server_config import GiskardServerConfig
from giskardpy.middleware.ros2.utils.utils import load_xacro
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.robots.hsrb import HSRB


def create_giskard() -> Giskard:
    """
    Build a Giskard that simulates the HSR, described by the file its robot class
    declares.
    """
    return Giskard(
        world_config=WorldWithHSRConfig(urdf=load_xacro(HSRB.get_ros_file_path())),
        robot_interface_config=StandAloneRobotInterfaceConfig(),
        server_config=GiskardServerConfig(debug_mode=True),
        qp_controller_config=QPControllerConfig(target_frequency=20),
    )


def main():
    rospy.init_node("giskard")
    create_giskard().live()


if __name__ == "__main__":
    main()
