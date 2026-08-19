"""
Minimal demo: the Panda picks up one cube and places it on top of another.
"""

import logging
import os
import time
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms, ApproachDirection, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
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

SCENE_PATH = Path(__file__).parent / "panda.xml"
CUBE_SIZE = 0.05

# %% World setup
PandaMeshAssets(scene=SCENE_PATH).download_if_missing()
world = MJCFParser(str(SCENE_PATH)).parse()
panda = Panda.from_world(world)
arm = panda.get_arms()[0]

with world.modify_world():
    ground_plane = Body(name=PrefixedName("ground_plane"))
    ground_plane.collision = ShapeCollection(
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
    cube_bottom.collision = ShapeCollection(
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
    cube_to_pick.collision = ShapeCollection(
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

# %% Visualization
# The arm's actuator gains assume gravity is separately cancelled out via MuJoCo's
# own gravcomp mechanism, not held against by the position controller alone.
# Without it, each joint settles with a steady-state gravity-sag error large enough
# to keep failing Giskard's convergence check, so a motion holding the arm under
# gravity never registers as done and the controller keeps sending corrective
# commands indefinitely.
for connection in arm.active_connections:
    connection.child.simulator_additional_properties.append(
        MujocoBody(gravitation_compensation_factor=1.0)
    )

headless = os.environ.get("CI", "false").lower() == "true"
multi_sim = MujocoSim(world=world, headless=headless, step_size=1e-3)
multi_sim.start_simulation()

# %% Plan
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
                # PickUpAction(
                #     cube_to_pick,
                #     Arms.LEFT,
                #     GraspDescription(
                #         ApproachDirection.FRONT,
                #         VerticalAlignment.TOP,
                #         arm.end_effector,
                #     ),
                # ),
                # PlaceAction(cube_to_pick, place_location, Arms.LEFT),
                # ParkArmsAction(Arms.BOTH),
            ],
            context=context,
        ).perform()
    time.sleep(2.0)
finally:
    multi_sim.stop_simulation()
