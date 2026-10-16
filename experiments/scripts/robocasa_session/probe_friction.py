"""What contact parameters do the PR2's finger pads and the RoboCasa target object get in MuJoCo?"""
import mujoco, numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.multi_sim import MujocoSim

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT002, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
target = episode.target_object.root
print("task:", episode.task.instruction, "target body", target.name.name, flush=True)
simulation = MujocoSim(world=world, headless=True, step_size=0.002, integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST)
m = simulation.simulator._mj_model
o = m.opt
print("opt: cone", o.cone, "impratio", o.impratio, "noslip", o.noslip_iterations, "o_solref", o.o_solref, "o_friction", o.o_friction, "enableflags", o.enableflags, "disableflags", o.disableflags)
gripper = robot.right_arm.end_effector
gripper_bodies = {b.name.name for b in world.get_kinematic_structure_entities_of_branch(gripper.root)}
def describe(body_name):
    b = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, body_name)
    for g in range(m.ngeom):
        if m.geom_bodyid[g] != b:
            continue
        if m.geom_contype[g] == 0 and m.geom_conaffinity[g] == 0:
            continue
        print(f"  {body_name:34s} geom {g} type {m.geom_type[g]} size {np.round(m.geom_size[g],4)} friction {m.geom_friction[g]} condim {m.geom_condim[g]} solref {m.geom_solref[g]} solimp {np.round(m.geom_solimp[g],3)} margin {m.geom_margin[g]} priority {m.geom_priority[g]} solmix {m.geom_solmix[g]} contype {m.geom_contype[g]} conaff {m.geom_conaffinity[g]}")
    print(f"  {body_name:34s} mass {m.body_mass[b]:.4f} inertia {np.round(m.body_inertia[b],6)}")
print("gripper bodies:")
for name in sorted(gripper_bodies):
    if "finger" in name or "palm" in name:
        describe(name)
print("target:")
describe(target.name.name)
for a in range(m.nu):
    name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, a)
    if "gripper" in name:
        print("actuator", name, "gain", m.actuator_gainprm[a][:3], "bias", m.actuator_biasprm[a][:3], "forcerange", m.actuator_forcerange[a], "forcelimited", m.actuator_forcelimited[a], "ctrlrange", m.actuator_ctrlrange[a])
for e in range(m.neq):
    print("equality", mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY, e), m.eq_type[e], m.eq_data[e][:5], "solref", m.eq_solref[e])
for j in range(m.njnt):
    name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j)
    if "r_gripper" in name:
        print("joint", name, "range", m.jnt_range[j], "damping", m.dof_damping[m.jnt_dofadr[j]], "armature", m.dof_armature[m.jnt_dofadr[j]], "frictionloss", m.dof_frictionloss[m.jnt_dofadr[j]])
