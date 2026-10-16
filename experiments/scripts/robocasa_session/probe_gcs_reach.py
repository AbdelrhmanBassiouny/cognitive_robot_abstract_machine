"""Can the PR2 reach into the RoboCasa sink along a path a volumetric graph of bounding boxes plans?

Usage: probe_gcs_reach.py <output directory>  (env COLLISION_AVOIDANCE=0/1, BLOAT=metres)
"""
import os
import sys
import time
from math import pi
from pathlib import Path

import numpy as np

from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import ExecutionType
from coraplex.execution_environment import ExecutionEnvironment
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from coraplex.robot_plans.motions.gripper import MoveTCPWaypointsMotion
from semantic_digital_twin.collision_checking.collision_rules import AvoidExternalCollisions
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix, Point3
from semantic_digital_twin.spatial_types.spatial_types import Pose, Quaternion
from semantic_digital_twin.semantic_annotations.semantic_annotations import SemanticEnvironmentAnnotation
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.graph_of_convex_sets.boxes import VolumetricGraphOfBoundingBoxes
from semantic_digital_twin.world_description.shape_collection import BoundingBoxCollection

output_directory = Path(sys.argv[1])
output_directory.mkdir(parents=True, exist_ok=True)
collision_avoidance = os.environ.get("COLLISION_AVOIDANCE", "1") == "1"
bloat = float(os.environ.get("BLOAT", "0.05"))
vertical_bloat = float(os.environ.get("VERTICAL_BLOAT", "0.01"))
pitch = float(os.environ.get("PITCH_DEGREES", "90"))
full_body = os.environ.get("FULL_BODY", "0") == "1"
lateral_offset = float(os.environ.get("LATERAL_OFFSET", "-0.19"))
seed = int(os.environ.get("SEED", "7"))
goal_x_offset = float(os.environ.get("GOAL_X_OFFSET", "0.0"))
torso_state = TorsoState[os.environ.get("TORSO", "HIGH")]
gripper_buffer = os.environ.get("GRIPPER_BUFFER")
label = f"ca{int(collision_avoidance)}_pitch{int(pitch)}_fullbody{int(full_body)}_offset{lateral_offset}_seed{seed}_gripperbuffer{gripper_buffer}_bloat{bloat}_{vertical_bloat}_goalx{goal_x_offset}_torso{torso_state.name}"

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001, seed=seed)
world, robot = episode.task.world, episode.robot
sink = episode.environment.sink
floor_corner, x_corner, y_corner, rim_corner = next(iter(sink.get_int_sites(relative=False).values()))
basin_center = (x_corner + y_corner) / 2
floor_z, rim_z = floor_corner[2], rim_corner[2]
front_y = floor_corner[1]

# stand in front of the sink, facing it, as close as the PR2 stands without colliding
drive = robot.root.parent_connection
robot.torso.get_joint_state_by_type(torso_state).apply_to(world)
world.notify_state_change()
for distance in np.arange(float(os.environ.get("MIN_STAND", "0.40")), 1.2, 0.025):
    drive.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=basin_center[0] + goal_x_offset + lateral_offset, y=front_y - distance, yaw=pi / 2, reference_frame=world.root
    )
    if robot.is_in_collision:
        continue
    base_body = world.get_body_in_branch_by_name(robot.root, "base_link")
    base_inside_buffer = [
        c for c in world.collision_manager.compute_collisions().contacts
        if base_body in (c.body_a, c.body_b)
        and c.distance < world.collision_manager.get_buffer_zone_distance(c.body_a, c.body_b)
    ]
    if not base_inside_buffer:
        break
print(label)
print(f"PR2 stands {distance:.3f} m in front of the basin front wall, in collision: {robot.is_in_collision}")

tool_start = world.compute_forward_kinematics_np(world.root, robot.right_arm.end_effector.tool_frame)[:3, 3]
print("tool frame starts at", np.round(tool_start, 3).tolist())
margin = 0.45
search_space = BoundingBoxCollection(
    shapes=[
        VolumetricBoundingBox(
            min_x=min(basin_center[0] - margin, tool_start[0] - 0.1), max_x=max(basin_center[0] + margin, tool_start[0] + 0.1),
            min_y=min(front_y - 0.4, tool_start[1] - 0.1), max_y=basin_center[1] + margin,
            min_z=floor_z - 0.05, max_z=max(rim_z + 0.6, tool_start[2] + 0.1),
            origin=HomogeneousTransformationMatrix(reference_frame=world.root),
        )
    ],
    reference_frame=world.root,
)
start_time = time.time()
standing_pose = drive.origin
drive.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=-50.0, y=-50.0, reference_frame=world.root)
obstacles = SemanticEnvironmentAnnotation(root=world.root, _world=world).build_bloated_obstacle_collection(
    search_space, bloat_obstacles=bloat, obstacle_height_clearance=vertical_bloat
)
graph = VolumetricGraphOfBoundingBoxes(world=world, search_space=search_space)
for box in BoundingBoxCollection.from_event(
    VolumetricBoundingBox,
    reference_frame=world.root,
    event=VolumetricGraphOfBoundingBoxes.free_space_from_bounding_boxes(obstacles, search_space.event),
):
    graph.add_node(box)
graph.calculate_connectivity()
drive.origin = standing_pose
shoulder = world.compute_forward_kinematics_np(world.root, robot.right_arm.root)[:3, 3]
print("right arm root at", np.round(shoulder, 3).tolist())
print(f"graph: {len(graph.graph.nodes())} boxes in {time.time() - start_time:.1f}s")

start = Point3(*tool_start, reference_frame=world.root)
raised_start = Point3(tool_start[0], tool_start[1], max(tool_start[2], rim_z + 0.15), reference_frame=world.root)
goal = Point3(basin_center[0] + goal_x_offset, basin_center[1], floor_z + 0.1, reference_frame=world.root)
path = [start, *graph.path_from_to(raised_start, goal)]
if path is None:
    raise SystemExit("NO PATH between the start and the goal")
print("GCS path:", [np.round(p.to_np()[:3], 3).tolist() for p in path])

gripper_pointing_down = Quaternion.from_rpy(0.0, np.radians(pitch), pi / 2, reference_frame=world.root)
waypoints = [Pose(position=p, orientation=gripper_pointing_down, reference_frame=world.root) for p in path]
arm = robot.right_arm
robot.mobile_base.full_body_controlled = full_body
if gripper_buffer is not None:
  with world.modify_world():
    world.collision_manager.extend_default_rules(
        [
            AvoidExternalCollisions(
                buffer_zone_distance=float(gripper_buffer),
                violated_distance=0.0,
                robot=robot,
                body_subset=set(arm.end_effector.bodies_with_collision),
            )
        ]
    )
context = Context(world, robot)
plan = sequential([MoveTorsoAction(torso_state), MoveTCPWaypointsMotion(waypoints, arm)], context)
start_time = time.time()
with ExecutionEnvironment(ExecutionType.KINEMATICALLY_SIMULATED, collision_avoidance=collision_avoidance):
    try:
        plan.perform()
        print("motion succeeded")
    except Exception as failure:
        print("motion failed:", type(failure).__name__, str(failure).splitlines()[0])
print(f"motion took {time.time() - start_time:.1f}s")

tool = world.compute_forward_kinematics_np(world.root, arm.end_effector.tool_frame)[:3, 3]
print("tool frame at", np.round(tool, 3).tolist(), "goal", np.round(goal.to_np()[:3], 3).tolist(),
      f"error {np.linalg.norm(tool - goal.to_np()[:3]):.3f} m",
      f"below the rim by {rim_z - tool[2]:.3f} m")
inside_x = x_corner[0] >= tool[0] >= floor_corner[0]
inside_y = y_corner[1] >= tool[1] >= floor_corner[1]
print("tool frame inside the basin:", inside_x and inside_y and floor_z <= tool[2] <= rim_z)
print("robot in collision:", robot.is_in_collision)
collision_manager = world.collision_manager
collision_manager.update_collision_matrix()
robot_bodies = set(robot.bodies)
for contact in sorted(collision_manager.compute_collisions().contacts, key=lambda c: c.distance):
    robot_body, other = (contact.body_a, contact.body_b) if contact.body_a in robot_bodies else (contact.body_b, contact.body_a)
    if other in robot_bodies:
        continue
    buffer_zone = collision_manager.get_buffer_zone_distance(contact.body_a, contact.body_b)
    print(f"CONTACT {robot_body.name.name:32s} {other.name.name:40s} distance {contact.distance:.3f} buffer zone {buffer_zone:.2f}",
          "INSIDE BUFFER" if contact.distance < buffer_zone else "")
base_now = robot.root.global_pose.to_np()[:3, 3]
print("base drifted by", np.round(base_now - standing_pose.to_np()[:3, 3], 3).tolist())

import imageio.v3 as imageio
import mujoco
from semantic_digital_twin.adapters.multi_sim import MujocoSim

simulation = MujocoSim(world=world, headless=True)
simulation.start_stepped_simulation()
model, data = simulation.simulator._mj_model, simulation.simulator._mj_data
model.vis.global_.offwidth, model.vis.global_.offheight = 1280, 960
model.vis.headlight.ambient[:] = [0.45, 0.45, 0.45]
model.vis.headlight.diffuse[:] = [0.75, 0.75, 0.75]
mujoco.mj_forward(model, data)
renderer = mujoco.Renderer(model, 960, 1280)
views = {"side": (1.7, 50.0, -30.0), "front": (1.5, 90.0, -45.0), "top": (1.1, 90.0, -80.0)}
for view, (camera_distance, azimuth, elevation) in views.items():
    for geometry in ("visual", "collision"):
        camera = mujoco.MjvCamera()
        camera.lookat[:] = [basin_center[0], basin_center[1] - 0.15, rim_z]
        camera.distance, camera.azimuth, camera.elevation = camera_distance, azimuth, elevation
        option = mujoco.MjvOption()
        option.geomgroup[:] = [1, 1, 1, 0, 0, 0] if geometry == "visual" else [1, 1, 0, 1, 0, 0]
        renderer.update_scene(data, camera, scene_option=option)
        path = output_directory / f"gcs_reach_{label}_{view}_{geometry}.png"
        imageio.imwrite(path, renderer.render())
        print("wrote", path)
simulation.stop_simulation()
