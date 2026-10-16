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
commanded = {PR2Joint.HEAD_PAN: 0.5, PR2Joint.RIGHT_WRIST_FLEX: -0.6, PR2Joint.RIGHT_WRIST_ROLL: 0.7, PR2Joint.RIGHT_ELBOW_FLEX: -1.0}
sim = MujocoSim(world=world, headless=True)
sim.start_stepped_simulation()
m, d = sim.simulator._mj_model, sim.simulator._mj_data
print("integrator", m.opt.integrator, "timestep", m.opt.timestep)
for name, value in commanded.items():
    world.state[world.get_connection_by_name(name).raw_dof.id].position = value
world.notify_state_change()
for t in range(6):
    sim.step_simulation(timedelta(seconds=0.5))
    row = []
    for name in commanded:
        j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, name)
        a = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, name + "_servo")
        row.append(f"{name}: q={d.qpos[m.jnt_qposadr[j]]:.3f} v={d.qvel[m.jnt_dofadr[j]]:.3f} ctrl={d.ctrl[a]:.2f} f={d.actuator_force[a]:.2f} arm={m.dof_armature[m.jnt_dofadr[j]]:.3f} damp={m.dof_damping[m.jnt_dofadr[j]]:.2f} frc={m.dof_frictionloss[m.jnt_dofadr[j]]:.2f} bias={d.qfrc_bias[m.jnt_dofadr[j]]:.2f} constr={d.qfrc_constraint[m.jnt_dofadr[j]]:.2f}")
    print(f"t={(t+1)*0.5}", *row, sep="\n  ")
print("contacts", d.ncon)
for i in range(d.ncon):
    c = d.contact[i]
    print("  ", mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, m.geom_bodyid[c.geom1]), mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, m.geom_bodyid[c.geom2]), round(c.dist, 4))
print("equalities", m.neq, [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY, i) for i in range(m.neq)][:20])
sim.stop_simulation()
