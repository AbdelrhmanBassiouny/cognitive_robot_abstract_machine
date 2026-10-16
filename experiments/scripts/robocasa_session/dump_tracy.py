"""Print the compiled MuJoCo model of a parked Tracy: masses, actuators, and where the left tool ends up."""
from datetime import timedelta
import numpy as np
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
import mujoco

world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
tracy = RobotSpecification(Tracy).spawn(world)
for arm in tracy.all_arms:
    arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
world.notify_state_change()
sim = MujocoSim(world=world, headless=True)
sim.start_stepped_simulation()
m, d = sim.simulator._mj_model, sim.simulator._mj_data
for b in range(m.nbody):
    if "left" in m.body(b).name:
        print(f"body {m.body(b).name:40s} mass {m.body_mass[b]:8.3f} inertia {np.round(m.body_inertia[b],4)}")
for a in range(m.nu):
    print(f"act {m.actuator(a).name:40s} joint {m.joint(m.actuator_trnid[a,0]).name:30s} gain {m.actuator_gainprm[a,0]:8.1f} bias {np.round(m.actuator_biasprm[a,:3],1)} frc {m.actuator_forcerange[a]} limited {m.actuator_forcelimited[a]} ctrl {d.ctrl[a]:.3f} ctrlrange {m.actuator_ctrlrange[a]} ctrllim {m.actuator_ctrllimited[a]}")
for j in range(m.njnt):
    print(f"jnt {m.joint(j).name:30s} qpos {d.qpos[m.jnt_qposadr[j]]:.3f} damp {m.dof_damping[m.jnt_dofadr[j]]:.2f} arm {m.dof_armature[m.jnt_dofadr[j]]:.3f} gravcomp-body {m.body_gravcomp[m.jnt_bodyid[j]]}")
sim.step_simulation(timedelta(seconds=1))
for j in range(m.njnt):
    print(f"after jnt {m.joint(j).name:30s} qpos {d.qpos[m.jnt_qposadr[j]]:.3f}")
sim.stop_simulation()
print("ncon", d.ncon)
for c in d.contact[: d.ncon]:
    print("contact", m.body(m.geom_bodyid[c.geom1]).name, "<->", m.body(m.geom_bodyid[c.geom2]).name, round(float(c.dist), 4))
for a in range(m.nu):
    print(f"force {m.actuator(a).name:40s} {d.actuator_force[a]:9.2f}")
