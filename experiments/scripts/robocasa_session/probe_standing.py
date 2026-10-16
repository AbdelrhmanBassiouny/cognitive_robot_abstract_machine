"""What keeps the PR2 from standing closer to the sink?"""
from math import pi
import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001, seed=7)
world, robot = episode.task.world, episode.robot
floor_corner, x_corner, y_corner, rim_corner = next(iter(episode.environment.sink.get_int_sites(relative=False).values()))
basin_center = (x_corner + y_corner) / 2
front_y = floor_corner[1]
drive = robot.root.parent_connection
collision_manager = world.collision_manager
own = set(robot.bodies_with_collision)
for distance in np.arange(0.30, 0.55, 0.025):
    drive.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=basin_center[0] - 0.19, y=front_y - distance, yaw=pi / 2, reference_frame=world.root)
    violated = [
        f"{c.body_a.name.name}|{c.body_b.name.name} {c.distance:.3f}<={collision_manager.get_violated_distance(c.body_a, c.body_b):.2f}"
        for c in collision_manager.compute_collisions().contacts
        if (c.body_a in own or c.body_b in own) and c.distance <= collision_manager.get_violated_distance(c.body_a, c.body_b)
    ]
    print(f"STAND {distance:.3f}", violated[:4])
