"""Which way do the grasps of RoboCasa objects approach and close, in the world?"""
import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT002, StyleType.STYLE001)
target = episode.target_object
gripper = episode.robot.right_arm.end_effector
print(episode.task.instruction, type(target).__name__, type(target).grasp_candidates.__qualname__)
for grasp in target.grasp_candidates()[:4]:
    world_T_grasp = grasp.world_T_grasp.to_np()
    tool_goal = gripper.tool_frame_goal_for_grasp(grasp.grasp_pose)
    world_T_tool = episode.task.world.transform(tool_goal, episode.task.world.root).to_np() if hasattr(tool_goal, "reference_frame") else None
    print("grasp x (approach?)", np.round(world_T_grasp[:3, 0], 2), "y", np.round(world_T_grasp[:3, 1], 2), "z", np.round(world_T_grasp[:3, 2], 2))
    if world_T_tool is not None:
        print("   tool goal x", np.round(world_T_tool[:3, 0], 2), "tool y (closing)", np.round(world_T_tool[:3, 1], 2))
print("tool_R_grasp", np.round(gripper.tool_R_grasp.to_np()[:3, :3], 2))
