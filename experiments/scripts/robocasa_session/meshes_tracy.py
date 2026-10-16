"""List the mesh assets the MuJoCo builder makes for Tracy."""
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
for mesh in builder.spec.meshes:
    print(mesh.name, mesh.file)
