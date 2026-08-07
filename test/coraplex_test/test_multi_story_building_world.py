from semantic_digital_twin.semantic_annotations.semantic_annotations import Floor


def test_multi_story_building_world_has_exactly_one_root(
    _multi_story_building_world_setup,
):
    world = _multi_story_building_world_setup
    assert world.root is not None


def test_multi_story_building_world_has_two_floors_worth_of_rooms(
    _multi_story_building_world_setup,
):
    world = _multi_story_building_world_setup
    floor_annotations = world.get_semantic_annotations_by_type(Floor)
    # Each building floor contributes one slab Floor annotation plus one Floor
    # annotation per room (4 rooms), and there are two building floors (ground + first).
    assert len(floor_annotations) == 2 * (1 + 4)
