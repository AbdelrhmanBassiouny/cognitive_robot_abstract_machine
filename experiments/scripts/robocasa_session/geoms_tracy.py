"""Print the geoms of Tracy's left arm base and forearm and the contacts at the parked start."""
import mujoco
import numpy as np
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

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
mujoco.mj_forward(m, d)
for g in range(m.ngeom):
    body = m.body(m.geom_bodyid[g]).name
    if body in ("left_base_link_inertia", "left_forearm_link"):
        mesh = m.geom_dataid[g]
        print(body, m.geom(g).name, "type", m.geom_type[g], "contype", m.geom_contype[g], "conaff", m.geom_conaffinity[g], "rbound", round(float(m.geom_rbound[g]), 3), "mesh", m.mesh(mesh).name if mesh >= 0 else None)
print("start ncon", d.ncon)
for c in d.contact[: d.ncon]:
    print("start contact", m.body(m.geom_bodyid[c.geom1]).name, m.geom(c.geom1).name, "<->", m.body(m.geom_bodyid[c.geom2]).name, m.geom(c.geom2).name, round(float(c.dist), 4))
sim.stop_simulation()
