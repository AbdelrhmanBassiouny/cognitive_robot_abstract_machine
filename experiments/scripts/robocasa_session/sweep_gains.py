"""Try PR2 servo gain sets against the test's commanded configuration."""
import sys, json
from datetime import timedelta
import mujoco, numpy as np
import semantic_digital_twin.robots.pr2 as pr2_module
from semantic_digital_twin.robots.pr2 import PR2, PR2Joint, PR2JointDrive, PR2Arm, PR2Neck
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.adapters.multi_sim import MujocoSim

config = json.loads(sys.argv[1])
upper, wrist, pan, tilt = (PR2JointDrive(**config[k]) for k in ("upper", "wrist", "pan", "tilt"))
PR2Arm.drives_by_joint = property(lambda self: {**{k: upper for k in ("shoulder_pan_joint", "shoulder_lift_joint", "upper_arm_roll_joint", "elbow_flex_joint", "forearm_roll_joint")}, "wrist_flex_joint": wrist, "wrist_roll_joint": wrist})
PR2Neck.drives_by_joint = property(lambda self: {PR2Joint.HEAD_PAN: pan, PR2Joint.HEAD_TILT: tilt})

world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
pr2 = RobotSpecification(PR2).spawn(world)
commanded = {PR2Joint.TORSO_LIFT: 0.2, PR2Joint.HEAD_PAN: 0.5, PR2Joint.HEAD_TILT: 0.3, PR2Joint.RIGHT_SHOULDER_PAN: -0.5, PR2Joint.RIGHT_SHOULDER_LIFT: 0.3, PR2Joint.RIGHT_UPPER_ARM_ROLL: -0.4, PR2Joint.RIGHT_ELBOW_FLEX: -1.0, PR2Joint.RIGHT_FOREARM_ROLL: 0.5, PR2Joint.RIGHT_WRIST_FLEX: -0.6, PR2Joint.RIGHT_WRIST_ROLL: 0.7}
sim = MujocoSim(world=world, headless=True)
sim.start_stepped_simulation()
m, d = sim.simulator._mj_model, sim.simulator._mj_data
for name, value in commanded.items():
    world.state[world.get_connection_by_name(name).raw_dof.id].position = value
world.notify_state_change()
addresses = {n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in commanded}
vaddresses = {n: m.jnt_dofadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in commanded}
max_speed = {n: 0.0 for n in commanded}
for step in range(30):
    sim.step_simulation(timedelta(seconds=0.1))
    for n in commanded:
        max_speed[n] = max(max_speed[n], abs(d.qvel[vaddresses[n]]))
    if step in (9, 19, 29):
        errors = {n.split("_joint")[0]: round(float(d.qpos[addresses[n]] - v), 3) for n, v in commanded.items()}
        print(f"t={(step+1)/10:.0f}s worst={max(abs(e) for e in errors.values()):.3f}", errors)
print("max speed", {n.split("_joint")[0]: round(v, 2) for n, v in max_speed.items()})
sim.stop_simulation()
