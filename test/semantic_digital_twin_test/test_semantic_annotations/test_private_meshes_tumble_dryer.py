"""
The private_meshes objects of this kind are annotated with this class.
"""

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import TumbleDryer
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body


def test_tumble_dryer_annotates_a_body():
    world = World()
    body = Body(name=PrefixedName("tumble_dryer"))
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
        annotation = TumbleDryer(root=body)
        world.add_semantic_annotation(annotation)
    assert world.get_semantic_annotations_by_type(TumbleDryer) == [annotation]
    assert annotation.root is body
