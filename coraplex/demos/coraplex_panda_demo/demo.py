import logging
import os
import time
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction

from panda_mesh_assets import PandaMeshAssets
from semantic_digital_twin.adapters.mjcf import MJCFParser
from semantic_digital_twin.adapters.multi_sim import MujocoBody, MujocoSim
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.panda import Panda
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

SCENE_PATH = (
    Path(__file__).parent.parent.parent
    / "resources"
    / "robots"
    / "franka_panda"
    / "panda.xml"
)
CUBE_SIZE = 0.05

PandaMeshAssets(scene=SCENE_PATH).download_if_missing()
world = MJCFParser(str(SCENE_PATH)).parse()
panda = Panda.from_world(world)
arm = panda.get_arms()[0]

with world.modify_world():
    ground_plane = Body(name=PrefixedName("ground_plane"))
    ground_plane_geometry = ShapeCollection(
        [
            Box(
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=ground_plane
                ),
                scale=Scale(2.0, 2.0, 0.02),
                color=Color(0.6, 0.6, 0.6, 1.0),
            )
        ],
        reference_frame=ground_plane,
    )
    ground_plane.collision, ground_plane.visual = (
        ground_plane_geometry,
        ground_plane_geometry,
    )
    world.add_connection(
        FixedConnection(
            parent=world.root,
            child=ground_plane,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                z=-0.01, reference_frame=world.root
            ),
        )
    )

    cube_bottom = Body(name=PrefixedName("cube_bottom"))
    cube_bottom_geometry = ShapeCollection(
        [
            Box(
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=cube_bottom
                ),
                scale=Scale(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE),
                color=Color(0.9, 0.3, 0.3, 1.0),
            )
        ],
        reference_frame=cube_bottom,
    )
    cube_bottom.collision, cube_bottom.visual = (
        cube_bottom_geometry,
        cube_bottom_geometry,
    )
    world.add_connection(
        Connection6DoF.create_with_dofs(
            world=world,
            parent=world.root,
            child=cube_bottom,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.40, y=0.10, z=0.06, reference_frame=world.root
            ),
        )
    )

    cube_to_pick = Body(name=PrefixedName("cube_to_pick"))
    cube_to_pick_geometry = ShapeCollection(
        [
            Box(
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                    reference_frame=cube_to_pick
                ),
                scale=Scale(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE),
                color=Color(0.3, 0.9, 0.3, 1.0),
            )
        ],
        reference_frame=cube_to_pick,
    )
    cube_to_pick.collision, cube_to_pick.visual = (
        cube_to_pick_geometry,
        cube_to_pick_geometry,
    )
    world.add_connection(
        Connection6DoF.create_with_dofs(
            world=world,
            parent=world.root,
            child=cube_to_pick,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.40, y=-0.14, z=0.06, reference_frame=world.root
            ),
        )
    )

for connection in arm.active_connections:
    connection.child.simulator_additional_properties.append(
        MujocoBody(gravitation_compensation_factor=1.0)
    )

headless = os.environ.get("CI", "false").lower() == "true"
multi_sim = MujocoSim(world=world, headless=headless, step_size=1e-3)
multi_sim.start_simulation()

context = Context(world=world, robot=panda, evaluate_conditions=False)

target_pose = cube_bottom.global_pose
place_location = Pose.from_xyz_rpy(
    x=target_pose.x,
    y=target_pose.y,
    z=target_pose.z + CUBE_SIZE,
    reference_frame=world.root,
)

try:
    with simulated_robot(real_time_factor=1.0, prediction_horizon=20):
        sequential(
            [
                ParkArmsAction(Arms.BOTH),
            ],
            context=context,
        ).perform()
    time.sleep(2.0)
finally:
    multi_sim.stop_simulation()
