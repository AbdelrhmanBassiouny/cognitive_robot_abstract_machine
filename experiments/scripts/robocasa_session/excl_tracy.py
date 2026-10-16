"""Print whether the compiled Tracy model excludes contacts between each left arm link and its base."""
import tempfile
from semantic_digital_twin.adapters.multi_sim import MujocoBuilder
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
tracy = RobotSpecification(Tracy).spawn(world)
builder = MujocoBuilder()
builder.build_world(world=world, file_path=tempfile.mktemp(suffix=".xml"))
pairs = {frozenset((e.bodyname1, e.bodyname2)) for e in builder.spec.excludes}
print("excludes", len(pairs))
for link in ["left_shoulder_link", "left_upper_arm_link", "left_forearm_link", "left_wrist_1_link", "left_wrist_2_link"]:
    print(link, frozenset(("left_base_link_inertia", link)) in pairs)
print("rules", [type(r).__name__ for r in world.collision_manager.ignore_collision_rules])
