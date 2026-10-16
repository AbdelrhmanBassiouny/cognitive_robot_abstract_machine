from datetime import timedelta
import mujoco
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.adapters.multi_sim import MujocoSim
import sys
from semantic_digital_twin.robots.pr2 import PR2, PR2Gripper, PR2JointDrive
k, dmp, arm = map(float, sys.argv[1:4])
PR2Gripper.finger_drive = property(lambda self: PR2JointDrive(torque_limit=5.0, stiffness=k, damping=dmp, armature=arm))
world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
pr2 = RobotSpecification(PR2).spawn(world)
g = pr2.right_arm.end_effector
g.get_joint_state_by_type(GripperState.OPEN).apply_to(world); world.notify_state_change()
sim = MujocoSim(world=world, headless=True); sim.start_stepped_simulation()
m, d = sim.simulator._mj_model, sim.simulator._mj_data
g.get_joint_state_by_type(GripperState.CLOSE).apply_to(world); world.notify_state_change()
a = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, "r_gripper_l_finger_joint_servo")
for t in range(10):
    sim.step_simulation(timedelta(seconds=0.1))
    print(sys.argv[1:4], t, "q", round(sim.simulator.get_joint_value("r_gripper_l_finger_joint").result, 4), "ctrl", d.ctrl[a], "force", round(float(d.actuator_force[a]), 3))
sim.stop_simulation()
