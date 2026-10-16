from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.robots.pr2 import PR2
world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
pr2 = RobotSpecification(PR2).spawn(world)
print([type(p).__name__ for p in pr2._robot_parts])
print("robot bodies", len(pr2.bodies), "base", len(pr2.mobile_base.bodies), "torso", len(pr2.torso.bodies), "arm", len(pr2.right_arm.bodies), "gripper", len(pr2.right_arm.end_effector.bodies), "neck", len(pr2.torso.neck.bodies))
print("base bodies", sorted(b.name.name for b in pr2.mobile_base.bodies)[:50])
c = world.get_connection_by_name("r_shoulder_pan_joint")
print("dynamics", c.dynamics)
print("total mass", sum(b.inertial.mass for b in pr2.bodies if b.inertial is not None))
up = [b for b in world.get_kinematic_structure_entities_of_branch(world.get_body_by_name("torso_lift_link")) if hasattr(b, "inertial") and b.inertial is not None]
print("mass above torso lift", sum(b.inertial.mass for b in up))
