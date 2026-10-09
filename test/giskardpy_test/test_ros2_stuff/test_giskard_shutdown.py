import signal
from dataclasses import dataclass

import rclpy

from giskardpy.middleware.ros2.giskard import Giskard
from giskardpy.middleware.ros2.robot_interface_config import (
    StandAloneRobotInterfaceConfig,
)
from giskardpy.middleware.ros2.server_config import GiskardServerConfig
from giskardpy.model.world_config import WorldConfig
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.input_synchronization import InputSynchronizer
from semantic_digital_twin.robots.minimal_robot import MinimalRobot
from semantic_digital_twin.world import World

# %% being interrupted while waiting for goals


@dataclass
class InterruptingInput(InputSynchronizer):
    """
    Asks the process to shut down as soon as it is read.
    """

    def apply(self) -> bool:
        signal.raise_signal(signal.SIGINT)
        return False


@dataclass
class InterruptedWhileIdleInterface(StandAloneRobotInterfaceConfig):
    """
    Lets the first idle cycle of Giskard be interrupted.
    """

    def connect(self):
        self.motion_server.inputs.add_input(InterruptingInput(world=self.world))


@dataclass
class WorldWithMinimalRobot(WorldConfig):
    """
    Treats everything in an existing world as the robot.
    """

    def setup_world(self):
        MinimalRobot.from_world(self.world)


def test_an_interrupt_while_waiting_for_goals_shuts_ros_down(
    init_rospy, mini_world: World
):
    giskard = Giskard(
        world_config=WorldWithMinimalRobot(world=mini_world),
        robot_interface_config=InterruptedWhileIdleInterface(),
        server_config=GiskardServerConfig(),
        qp_controller_config=QPControllerConfig(target_frequency=50),
    )

    giskard.live()

    assert not rclpy.ok()
