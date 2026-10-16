"""Record giskard moving a PR2 that MuJoCo simulates physically.

Every motion is ticked by giskard against the world; the servos of the PR2 take each tick's
command as their set point and the physics advances one control cycle in between. Frames are
rendered straight from the running simulation, so the video shows where the physics put the
robot, not where giskard commanded it.

Usage: record_physics_motion.py <out.mp4>
"""
import sys
import time
from dataclasses import dataclass, field
from math import pi
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np

from giskardpy.executor import Executor, SteppedSimulationPacer
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.graph_node import EndMotion
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPose, CartesianPosition
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.datastructures.definitions import StaticJointState, TorsoState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    Pose,
)
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

output_path = Path(sys.argv[1])
control_frequency = 50
render_every = 2
width, height = 1280, 720


@dataclass
class RecordingPacer(SteppedSimulationPacer):
    """Steps the physics like its base class and renders a frame every few cycles."""

    renderer: mujoco.Renderer = field(kw_only=True, default=None)
    camera: mujoco.MjvCamera = field(kw_only=True, default=None)
    frames: list = field(kw_only=True, default_factory=list)
    cycles: int = 0

    def sleep(self) -> None:
        super().sleep()
        self.cycles += 1
        if self.cycles % render_every:
            return
        self.renderer.update_scene(self.simulation.simulator._mj_data, self.camera)
        self.frames.append(self.renderer.render())


world = World()
with world.modify_world():
    root = Body(name=PrefixedName("map"))
    world.add_kinematic_structure_entity(root)
    floor = Body(name=PrefixedName("floor_tiles"))
    floor.visual = ShapeCollection(
        [
            Box(
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(z=-0.005, reference_frame=floor),
                scale=Scale(8.0, 8.0, 0.01),
                color=Color(0.55, 0.6, 0.65, 1.0),
            )
        ],
        reference_frame=floor,
    )
    world.add_kinematic_structure_entity(floor)
    world.add_connection(FixedConnection(parent=root, child=floor))
    # tiles every half metre and coloured posts at the waypoints, so travel is visible
    tiles = Body(name=PrefixedName("grid_tiles"))
    tiles.visual = ShapeCollection(
        [
            Box(
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(x=x, y=y, z=0.001, reference_frame=tiles),
                scale=Scale(0.46, 0.46, 0.002),
                color=Color(0.42, 0.47, 0.52, 1.0),
            )
            for x in np.arange(-1.5, 3.6, 1.0)
            for y in np.arange(-1.5, 3.1, 1.0)
        ]
        + [
            Box(
                origin=HomogeneousTransformationMatrix.from_xyz_rpy(x=x, y=y, z=0.15, reference_frame=tiles),
                scale=Scale(0.08, 0.08, 0.3),
                color=color,
            )
            for x, y, color in (
                (0.0, -0.6, Color(0.9, 0.2, 0.2, 1.0)),
                (2.0, -0.6, Color(0.2, 0.7, 0.2, 1.0)),
                (2.6, 1.5, Color(0.2, 0.4, 0.9, 1.0)),
            )
        ],
        reference_frame=tiles,
    )
    world.add_kinematic_structure_entity(tiles)
    world.add_connection(FixedConnection(parent=root, child=tiles))
robot = RobotSpecification(PR2).spawn(world)
for arm in robot.all_arms:
    arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
world.notify_state_change()

simulation = MujocoSim(world=world, headless=True)
simulation.start_stepped_simulation()
model = simulation.simulator._mj_model
model.vis.global_.offwidth, model.vis.global_.offheight = width, height
model.vis.headlight.ambient[:] = [0.45, 0.45, 0.45]
model.vis.headlight.diffuse[:] = [0.75, 0.75, 0.75]
camera = mujoco.MjvCamera()
camera.lookat[:] = [1.0, 0.7, 0.5]
camera.distance, camera.azimuth, camera.elevation = 6.0, -120.0, -32.0
pacer = RecordingPacer(simulation, renderer=mujoco.Renderer(model, height, width), camera=camera)
tool_frame = robot.right_arm.end_effector.tool_frame


def perform(name: str, *tasks) -> None:
    """Have giskard tick tasks in parallel against the physically simulated robot until all are done."""
    motion_statechart = MotionStatechart()
    motion_statechart.add_nodes([*tasks, EndMotion.when_all_true(list(tasks))])
    executor = Executor(
        context=MotionStatechartContext(
            world=world, qp_controller_config=QPControllerConfig(target_frequency=control_frequency)
        ),
        pacer=pacer,
    )
    executor.compile(motion_statechart=motion_statechart)
    start = time.time()
    executor.tick_until_end(timeout=3000)
    base = simulation.simulator.get_body_position(body_name=robot.root.name.name).result
    tool = simulation.simulator.get_body_position(body_name=tool_frame.name.name).result
    print(
        f"{name}: done={motion_statechart.is_end_motion()} in {time.time() - start:.0f}s, "
        f"{len(pacer.frames)} frames, simulated base at {np.round(base, 3)}, tool at {np.round(tool, 3)}",
        flush=True,
    )


try:
    for name, x, y, yaw in (
        ("drive forward", 2.0, 0.0, 0.0),
        ("drive sideways while turning", 2.0, 1.5, pi / 2),
        ("drive back to the start", 0.0, 0.0, 0.0),
    ):
        perform(
            name,
            CartesianPose(
                root_link=world.root,
                tip_link=robot.root,
                goal_pose=Pose.from_xyz_rpy(x=x, y=y, yaw=yaw, reference_frame=world.root),
            ),
        )
finally:
    simulation.stop_simulation()
    if pacer.frames:
        imageio.mimwrite(output_path, pacer.frames, fps=control_frequency // render_every, macro_block_size=8)
        print("wrote", output_path, len(pacer.frames), "frames", flush=True)
