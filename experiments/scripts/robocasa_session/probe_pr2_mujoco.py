import sys, time, tempfile
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.adapters.multi_sim import MujocoBuilder
world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
robot = RobotSpecification(PR2).spawn(world)
print("drive", type(robot.root.parent_connection).__name__, robot.root.parent_connection.name, [d.name for d in robot.root.parent_connection.dofs])
print("drive parent chain", robot.root.parent_connection.parent.name, robot.root.parent_connection.parent.parent_connection)
for part in [robot.left_arm.end_effector, robot.torso, robot.torso.neck, robot.left_arm]:
    print(type(part).__name__)
    for c in part.active_connections:
        print("   ", c.name.name, type(c).__name__, c.raw_dof.name.name if isinstance(c, ActiveConnection1DOF) else "", getattr(c, "multiplier", None), c.has_hardware_interface)
unactuated = [c.name.name for c in world.connections if isinstance(c, ActiveConnection1DOF) and not c.has_hardware_interface and c in set(world.get_connections_of_branch(robot.root))]
print("not controlled 1dof in robot:", unactuated)
print("body attrs", [a for a in dir(robot.bodies[0]) if "inert" in a or "mass" in a])
t=time.time()
b = MujocoBuilder()
try:
    b.build_world(world=world, file_path=tempfile.mkdtemp() + "/scene.xml")
    print("built in", time.time()-t)
except Exception as e:
    print("BUILD FAILED", type(e).__name__, str(e)[:500])
