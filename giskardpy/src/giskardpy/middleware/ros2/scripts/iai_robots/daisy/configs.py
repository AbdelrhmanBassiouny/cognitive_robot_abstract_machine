from dataclasses import dataclass, field
from typing import Optional

from giskardpy.middleware.ros2.robot_interface_config import (
    ClosedLoopRobotInterfaceConfig,
)
from giskardpy.model.world_config import WorldWithFixedRobot
from semantic_digital_twin.robots.daisy import DAiSy
from semantic_digital_twin.robots.robot_parts import AbstractRobot

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName


@dataclass
class DAiSyVelocityInterface(ClosedLoopRobotInterfaceConfig):
    """
    Commands both arms of DAiSy through their forward velocity controllers.
    """

    def setup(self):
        self.sync_robot_parts()
        self.add_velocity_controllers_from_controller_manager()


@dataclass
class WorldWithDaisyConfig(WorldWithFixedRobot):
    """
    A world containing only DAiSy, whose base is fixed to the world root.
    """

    root_name: PrefixedName = field(default=PrefixedName(name="map2"))
    """
    Name of the body DAiSy is attached to.
    """

    urdf_view: AbstractRobot = field(kw_only=True, default=DAiSy, init=False)
    """
    Semantic view that is applied to the parsed urdf.
    """

    def setup_world(self, robot_name: Optional[str] = None) -> None:
        super().setup_world()
        self.robot = self.world.get_semantic_annotations_by_type(DAiSy)[0]
