#!/usr/bin/env python
from giskardpy.middleware.ros2 import rospy
from giskardpy.middleware.ros2.giskard import Giskard
from giskardpy.middleware.ros2.robot_interface_config import (
    StandAloneRobotInterfaceConfig,
)
from giskardpy.middleware.ros2.scripts.iai_robots.pr2.configs import (
    WorldWithPR2Config,
)
from giskardpy.middleware.ros2.server_config import GiskardServerConfig
from giskardpy.middleware.ros2.utils.utils import load_xacro
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.robots.pr2 import PR2


def create_giskard() -> Giskard:
    """
    Build a Giskard that simulates the PR2, described by the file its robot class
    declares.
    """
    return Giskard(
        world_config=WorldWithPR2Config(urdf=load_xacro(PR2.get_ros_file_path())),
        robot_interface_config=StandAloneRobotInterfaceConfig(),
        server_config=GiskardServerConfig(debug_mode=True),
        qp_controller_config=QPControllerConfig(target_frequency=20),
    )


def main():
    rospy.init_node("giskard")
    create_giskard().live()


if __name__ == "__main__":
    main()
