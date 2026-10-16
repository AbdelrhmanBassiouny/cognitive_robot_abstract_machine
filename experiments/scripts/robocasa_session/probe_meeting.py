"""Where does the PR2's gripper aim a grasp, relative to its tool frame?"""
import numpy as np
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
pr2 = RobotSpecification(PR2).spawn(world)
gripper = pr2.right_arm.end_effector
print("tool_P_grasp_when_closed", np.round(gripper.tool_P_grasp_when_closed.to_np()[:3], 4))
print("fingertips tool_P_grasp now", np.round(gripper.fingertips.tool_P_grasp.to_np()[:3], 4))
print("tool_R_grasp", np.round(gripper.tool_R_grasp.to_np()[:3, :3], 3))
tool = gripper.tool_frame.global_pose.to_np()
for tip in (gripper.thumb.tip, gripper.finger.tip):
    tool_T_tip = np.linalg.inv(tool) @ tip.global_pose.to_np()
    print(tip.name.name, "in tool frame", np.round(tool_T_tip[:3, 3], 4))
