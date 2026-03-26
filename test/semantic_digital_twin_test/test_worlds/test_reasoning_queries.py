from semantic_digital_twin.predetermined_maps.suturo_lab_map import load_environment
from semantic_digital_twin.reasoning.queries import query_semantic_annotations_on_surfaces, \
    query_get_next_object_euclidean_x_y, query_surface_of_most_similar_obj, query_annotations_by_color, \
    query_class_by_label, query_sort_by_size
from semantic_digital_twin.semantic_annotations.semantic_annotations import *
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color


def test_load_environment_returns_world():
    """
    Tests that loading the environment returns a World object with the correct root name.
    """
    world = load_environment()
    assert isinstance(world, World)
    assert world.root.name == PrefixedName("root")


def test_query_semantic_annotations_on_surfaces(kitchen_environment_fixture):
    """
    Tests that giving Table annotations gives a list of the correct annotation on top.
    """
    table1 = kitchen_environment_fixture.get_semantic_annotation_by_name("fruit_table")
    table2 = kitchen_environment_fixture.get_semantic_annotation_by_name("vegetable_table")
    table3 = kitchen_environment_fixture.get_semantic_annotation_by_name("empty_table")
    apple = kitchen_environment_fixture.get_semantic_annotation_by_name("apple")
    carrot = kitchen_environment_fixture.get_semantic_annotation_by_name("carrot")
    orange = kitchen_environment_fixture.get_semantic_annotation_by_name("orange")
    lettuce = kitchen_environment_fixture.get_semantic_annotation_by_name("lettuce")
    assert [type(x) for x in query_semantic_annotations_on_surfaces([table1, table2], kitchen_environment_fixture).evaluate()] == [type(x) for x in
        [apple,
        orange,
        carrot,
        lettuce,
    ]]
    assert set(query_semantic_annotations_on_surfaces([table3], kitchen_environment_fixture).tolist()) == set([])
    assert set(query_semantic_annotations_on_surfaces([], kitchen_environment_fixture).tolist()) == set([])


def test_query_get_next_object_euclidean_x_y(kitchen_environment_fixture):
    """
    Tests the functionality of the `query_get_next_object_euclidean_x_y` function to verify that it accurately identifies
    the next objects based on their Euclidean proximity within a simulation world. The test involves setting up a virtual
    world, retrieving specific objects and annotations, and validating the results returned by the function against
    predetermined expectations.

    :raises AssertionError: If any of the function assertions fail during testing.
    """
    toya = kitchen_environment_fixture.get_body_by_name("base_link_body")
    table1 = kitchen_environment_fixture.get_semantic_annotation_by_name("fruit_table")
    table2 = kitchen_environment_fixture.get_semantic_annotation_by_name("vegetable_table")
    table3 = kitchen_environment_fixture.get_semantic_annotation_by_name("empty_table")
    apple = kitchen_environment_fixture.get_semantic_annotation_by_name("apple")
    carrot = kitchen_environment_fixture.get_semantic_annotation_by_name("carrot")
    orange = kitchen_environment_fixture.get_semantic_annotation_by_name("orange")
    lettuce = kitchen_environment_fixture.get_semantic_annotation_by_name("lettuce")

    assert query_get_next_object_euclidean_x_y(toya, table1).tolist() == [orange, apple]
    assert query_get_next_object_euclidean_x_y(toya, table2).tolist() == [
        carrot,
        lettuce,
    ]
    assert query_get_next_object_euclidean_x_y(toya, table3).tolist() == []


def test_query_surface_of_most_similar_obj(kitchen_environment_fixture):
    """
    Tests the `query_surface_of_most_similar_obj` function for determining the surface of the most suitable
    semantic annotation object from a set of candidates based on similarity and
    other constraints. The function is evaluated under multiple scenarios to verify
    its logic in choosing the correct table, handling empty tables, and cases with
    no valid candidates.
    """
    table1 = kitchen_environment_fixture.get_semantic_annotation_by_name("fruit_table")
    table2 = kitchen_environment_fixture.get_semantic_annotation_by_name("vegetable_table")
    table3 = kitchen_environment_fixture.get_semantic_annotation_by_name("empty_table")
    table4 = kitchen_environment_fixture.get_semantic_annotation_by_name("empty_table2")

    banana = kitchen_environment_fixture.get_semantic_annotation_by_name("banana")
    apple = kitchen_environment_fixture.get_semantic_annotation_by_name("apple")
    carrot = kitchen_environment_fixture.get_semantic_annotation_by_name("carrot")
    orange = kitchen_environment_fixture.get_semantic_annotation_by_name("orange")
    lettuce = kitchen_environment_fixture.get_semantic_annotation_by_name("lettuce")

    # choosing the correct table
    assert query_surface_of_most_similar_obj(banana, [table1, table2, table3]) == table1
    assert query_surface_of_most_similar_obj(carrot, [table1, table2, table3]) == table2
    # choosing the empty table
    assert query_surface_of_most_similar_obj(lettuce, [table1, table3]) == table3
    assert query_surface_of_most_similar_obj(table1, [table1, table2, table3]) == table3
    # trying with a new threshold
    assert query_surface_of_most_similar_obj(orange, [table2, table3], 2) == table2
    # returning None if there is no empty table or no tables
    assert query_surface_of_most_similar_obj(apple, [table2]) == None
    assert query_surface_of_most_similar_obj(orange, []) == None
    # trying with 2 empty tables
    assert query_surface_of_most_similar_obj(apple, [table2, table3, table4]) == table3
    assert query_surface_of_most_similar_obj(apple, [table2, table4, table3]) == table4

def test_query_body_by_color(kitchen_environment_fixture):
    """
    Tests the query_annotations_by_color function by verifying the retrieval of semantic
    annotations by their associated colors.

    The function validates that calling query_annotations_by_color with different color
    parameters returns the expected list of annotations corresponding to that color
    within the given list of objects.
    """
    table1 = kitchen_environment_fixture.get_semantic_annotation_by_name("fruit_table")
    table2 = kitchen_environment_fixture.get_semantic_annotation_by_name("vegetable_table")
    apple = kitchen_environment_fixture.get_semantic_annotation_by_name("apple")
    orange = kitchen_environment_fixture.get_semantic_annotation_by_name("orange")
    carrot = kitchen_environment_fixture.get_semantic_annotation_by_name("carrot")

    assert query_annotations_by_color(Color.RED(), [apple, orange]) == [apple]
    assert query_annotations_by_color(Color.ORANGE(), [apple, orange]) == [orange]
    assert query_annotations_by_color(Color.BLUE(), [apple, orange,carrot]) == []
    assert query_annotations_by_color(Color.ORANGE(), (query_semantic_annotations_on_surfaces([table1, table2], kitchen_environment_fixture).tolist())) == [orange, carrot]

def test_query_class_by_label():
    """
    Tests the query_class_by_label function by verifying the retrieval of the semantic class
    """
    assert query_class_by_label("salt_aquasale_mill_transparent") == Salt
    assert query_class_by_label("milk_jumbo_pack_voll") == Milk
    assert query_class_by_label("bowl_collapsable_yellowgrey") == Bowl

    assert query_class_by_label("unknown_object") is None


def test_query_sort_by_size(kitchen_environment_fixture):
    """
    Tests the query_sort_by_size function by verifying the order of the returned annotations.
    """
    table1 = kitchen_environment_fixture.get_semantic_annotation_by_name("fruit_table")
    table2 = kitchen_environment_fixture.get_semantic_annotation_by_name("vegetable_table")

    apple = kitchen_environment_fixture.get_semantic_annotation_by_name("apple")
    carrot = kitchen_environment_fixture.get_semantic_annotation_by_name("carrot")
    lettuce = kitchen_environment_fixture.get_semantic_annotation_by_name("lettuce")

    assert query_sort_by_size([]) ==[]
    assert query_sort_by_size([apple, carrot]) == [apple, carrot]
    assert query_sort_by_size([table1, lettuce, apple]) == [table1, lettuce, apple]
    assert query_sort_by_size([table1, lettuce, apple], False) == [apple, lettuce, table1]
    assert query_sort_by_size(query_semantic_annotations_on_surfaces([table2], kitchen_environment_fixture).tolist()) == [lettuce, carrot]