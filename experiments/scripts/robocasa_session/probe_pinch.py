"""How hard does the simulated PR2 gripper pinch? Close it on a box fixed between its fingertips and sum the normal forces."""
from datetime import timedelta
import mujoco
import numpy as np
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.spatial_types.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
pr2 = RobotSpecification(PR2).spawn(world)
gripper = pr2.right_arm.end_effector
gripper.get_joint_state_by_type(GripperState.OPEN).apply_to(world)
world.notify_state_change()
tool = gripper.tool_frame.global_pose.to_np()
box = Body(name=PrefixedName("pinched_box"))
box.collision = ShapeCollection([Box(scale=Scale(0.03, 0.04, 0.03), origin=HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=box))])
with world.modify_world():
    world.add_connection(FixedConnection(parent=world.root, child=box, parent_T_connection_expression=HomogeneousTransformationMatrix(tool, reference_frame=world.root)))
simulation = MujocoSim(world=world, headless=True, step_size=0.002, integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST, cone=mujoco.mjtCone.mjCONE_ELLIPTIC, impratio=10.0)
simulation.start_stepped_simulation()
model, data = simulation.simulator._mj_model, simulation.simulator._mj_data
gripper.get_joint_state_by_type(GripperState.CLOSE).apply_to(world)
world.notify_state_change()
simulation.step_simulation(timedelta(seconds=1.5))
box_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pinched_box")
tips = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, t.name.name): t.name.name for t in (gripper.thumb.tip, gripper.finger.tip)}
others = {}
force = np.zeros(6)
for i, c in enumerate(data.contact[: data.ncon]):
    bodies = {model.geom_bodyid[c.geom1], model.geom_bodyid[c.geom2]}
    if box_id not in bodies:
        continue
    mujoco.mj_contactForce(model, data, i, force)
    other = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, (bodies - {box_id}).pop())
    others[other] = others.get(other, 0.0) + force[0]
finger = gripper.thumb.root.parent_connection.name.name
print("finger joint", round(simulation.simulator.get_joint_value(finger).result, 3), "normal force on the box by body (N):", {k: round(v, 1) for k, v in others.items()})
servo = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, finger + "_servo")
print("servo force", round(float(data.actuator_force[servo]), 2), "limit", model.actuator_forcerange[servo])
simulation.stop_simulation()
