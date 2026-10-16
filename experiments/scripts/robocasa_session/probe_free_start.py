import sys
import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.datastructures.definitions import StaticJointState


def touching(world, robot):
    manager = world.collision_manager
    own = set(robot.bodies_with_collision)
    return sorted({
        (str(contact.body_a.name), str(contact.body_b.name), round(contact.distance, 3))
        for contact in manager.compute_collisions().contacts
        if (contact.body_a in own or contact.body_b in own)
        and contact.distance <= manager.get_violated_distance(contact.body_a, contact.body_b)
        and "floor" not in str(contact.body_a.name) + str(contact.body_b.name)
    })


for layout in sys.argv[1:]:
    episode = CounterToSinkEpisode.compose(LayoutType[layout], StyleType.STYLE001)
    world, robot = episode.task.world, episode.robot
    world.collision_manager.update_collision_matrix()
    for arm in robot.all_arms:
        arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
    drive = robot.root.parent_connection
    base = episode.task.robot_base_pose.to_np()
    for step in range(0, 20):
        back = np.eye(4); back[0, 3] = -0.05 * step
        drive.origin = base @ back
        contacts = touching(world, robot)
        print(layout, f"{0.05 * step:.2f} m:", len(contacts), contacts[:3], flush=True)
        if not contacts:
            break
