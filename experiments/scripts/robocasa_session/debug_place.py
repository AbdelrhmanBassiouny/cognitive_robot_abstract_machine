import numpy as np
from coraplex.datastructures.enums import ExecutionType
from coraplex.execution_environment import ExecutionEnvironment
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001, seed=10)
world = episode.task.world
with ExecutionEnvironment(ExecutionType.KINEMATICALLY_SIMULATED, collision_avoidance=False):
    episode.pick_up_plan(42).perform()
    placing = episode.placing_into_the_sink()
    standing = placing.standing_pose()
    basin = placing.basin
    print("basin floor centre", np.round(basin.floor_center, 3).tolist(), "rim", round(basin.rim_height, 3), "front", basin.front_direction.tolist())
    print("standing", np.round(standing.to_np()[:3, 3], 3).tolist(), "distance from basin front", round(float(np.dot(standing.to_np()[:2, 3] - basin.floor_corner[:2], basin.front_direction)), 3))
    tool = placing.arm.end_effector.tool_frame
    print("tool_T_object", np.round(world.compute_forward_kinematics_np(tool, placing.held_object)[:3, 3], 3).tolist())
    path = placing.path_into_the_basin(standing)
    print("path corners", len(path), [np.round(p.to_np()[:3], 3).tolist() for p in path[::10]], np.round(path[-1].to_np()[:3], 3).tolist())
    try:
        plan = placing.plan()
        from coraplex.plans.attachment_nodes import ReAttachNode
        plan.perform()
    except Exception as failure:
        print("FAILED", type(failure).__name__)
    print("tool at", np.round(world.compute_forward_kinematics_np(world.root, tool)[:3, 3], 3).tolist())
    print("approach", np.round(placing.approach_direction, 3).tolist(), "tool x axis", np.round(world.compute_forward_kinematics_np(world.root, tool)[:3, 0], 3).tolist())
    print("torso", world.get_connection_by_name("torso_lift_joint").position if hasattr(world.get_connection_by_name("torso_lift_joint"), "position") else None)
box = placing.held_object.collision.as_bounding_box_collection_in_frame(world.root).bounding_box()
print("object box after release", np.round([box.min_x, box.min_y, box.min_z, box.max_x, box.max_y, box.max_z], 3).tolist())
print("object in sink? collisions with sink:", [ (c.body_a.name.name, c.body_b.name.name, round(c.distance, 3)) for c in world.collision_manager.collision_detector.check_collisions(world.collision_manager.collision_matrix).contacts if placing.held_object in (c.body_a, c.body_b)][:6])
env = episode.environment
joint = env.objects["obj"].joints[0]
episode.copy_target_object_pose_into_robocasa()
sim = env.sim
sim.data.set_joint_qvel(joint, np.zeros(6))
for step in range(1000):
    sim.step()
    if step % 100 == 0:
        print("SETTLE", step, np.round(sim.data.get_joint_qpos(joint)[:3], 3).tolist(), "ncon", sim.data.ncon, flush=True)
contacts = [(sim.model.geom_id2name(c.geom1), sim.model.geom_id2name(c.geom2)) for c in sim.data.contact[: sim.data.ncon]]
print("CONTACTS", contacts[:10])
