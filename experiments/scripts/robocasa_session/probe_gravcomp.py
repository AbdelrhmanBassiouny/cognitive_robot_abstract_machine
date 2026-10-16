from datetime import timedelta
import mujoco, numpy as np
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.robots.pr2 import PR2, PR2Joint
world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
pr2 = RobotSpecification(PR2).spawn(world)
sim = MujocoSim(world=world, headless=True)
sim.start_stepped_simulation()
m, d = sim.simulator._mj_model, sim.simulator._mj_data
sim.step_simulation(timedelta(seconds=0.01))
names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(m.nbody)]
print("gravcomp>0 bodies", int((m.body_gravcomp > 0).sum()), "of", m.nbody, "mass total", m.body_mass.sum())
print("no gravcomp with mass:", [(n, round(float(m.body_mass[i]),2)) for i, n in enumerate(names) if m.body_gravcomp[i] == 0 and m.body_mass[i] > 0])
print("disableflags", m.opt.disableflags, "enableflags", m.opt.enableflags, "jnt_actgravcomp", m.jnt_actgravcomp[:5])
for n in ["r_elbow_flex_joint", "r_wrist_flex_joint", "head_pan_joint"]:
    j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n); a = m.jnt_dofadr[j]
    print(n, "qfrc_gravcomp", d.qfrc_gravcomp[a] if hasattr(d, "qfrc_gravcomp") else None, "passive", d.qfrc_passive[a], "bias", d.qfrc_bias[a], "dof_M diag", d.qM[m.dof_Madr[a]] if hasattr(d,"qM") else None)
for n in ["r_shoulder_pan_link","r_upper_arm_link","r_elbow_flex_link","r_forearm_link","r_wrist_flex_link","r_wrist_roll_link","r_gripper_palm_link","head_pan_link","head_tilt_link","torso_lift_link","base_link","head_mount_kinect2_link"]:
    i = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n)
    b = world.get_body_by_name(n)
    print("mass", n, round(float(m.body_mass[i]),3), "world", None if b.inertial is None else round(b.inertial.mass,3), "inertia", np.round(m.body_inertia[i],4))
top = sorted(range(m.nbody), key=lambda i: -m.body_mass[i])[:8]
print("heaviest", [(names[i], round(float(m.body_mass[i]),1)) for i in top])
sim.stop_simulation()
