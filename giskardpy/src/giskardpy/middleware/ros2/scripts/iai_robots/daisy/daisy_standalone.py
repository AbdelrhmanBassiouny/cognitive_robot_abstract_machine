from giskardpy.middleware.ros2 import rospy
from giskardpy.middleware.ros2.giskard import Giskard
from giskardpy.middleware.ros2.robot_interface_config import (
    StandAloneRobotInterfaceConfig,
)
from giskardpy.middleware.ros2.scripts.iai_robots.daisy.configs import (
    WorldWithDaisyConfig,
)
from giskardpy.middleware.ros2.server_config import GiskardServerConfig
from giskardpy.middleware.ros2.utils.utils import load_xacro
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.robots.daisy import DAiSy


def create_giskard() -> Giskard:
    """
    Build a Giskard that simulates DAiSy, described by the file its robot class
    declares.
    """
    return Giskard(
        world_config=WorldWithDaisyConfig(urdf=load_xacro(DAiSy.get_ros_file_path())),
        robot_interface_config=StandAloneRobotInterfaceConfig(),
        server_config=GiskardServerConfig(debug_mode=True),
        qp_controller_config=QPControllerConfig(target_frequency=33),
    )


def main():
    rospy.init_node("giskard")
    create_giskard().live()


if __name__ == "__main__":
    main()
