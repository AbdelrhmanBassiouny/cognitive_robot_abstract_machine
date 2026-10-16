import re, tempfile
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.adapters.multi_sim import MujocoBuilder
world = World()
with world.modify_world():
    world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
pr2 = RobotSpecification(PR2).spawn(world)
path = tempfile.mkdtemp() + "/scene.xml"
b = MujocoBuilder(); b.build_world(world=world, file_path=path)
x = open(path).read()
print(re.search(r"<compiler[^>]*>", x).group(0))
i = x.find('name="r_shoulder_pan_link"'); print(x[i-10:i+900])
spec_body = next(bb for bb in b.spec.bodies if bb.name == "r_shoulder_pan_link")
print("spec mass", spec_body.mass, "explicitinertial", getattr(spec_body, "explicitinertial", None))
import mujoco, xml.etree.ElementTree as ET
spec2 = mujoco.MjSpec.from_file(path)
for n in ["r_shoulder_pan_link", "base_link", "head_pan_link", "r_wrist_roll_link"]:
    sb = next(bb for bb in spec2.bodies if bb.name == n)
    print(n, "reloaded spec mass", sb.mass, "explicit", sb.explicitinertial, "world", world.get_body_by_name(n).inertial.mass if world.get_body_by_name(n).inertial else None)
root = ET.parse(path).getroot()
xml_order = [e.get("name") for e in root.findall(".//body")]
spec_order = [bb.name for bb in b.spec.bodies][1:]
print("orders equal", xml_order == spec_order, len(xml_order), len(spec_order))
for i, (a, c) in enumerate(zip(xml_order, spec_order)):
    if a != c:
        print("first mismatch at", i, a, c); break
