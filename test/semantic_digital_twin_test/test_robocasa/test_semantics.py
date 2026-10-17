from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from semantic_digital_twin.adapters.mjcf import MJCFParser
from semantic_digital_twin.adapters.robocasa_dataset.loader import (
    RoboCasaDatasetLoader,
    _category_from_class_name,
    _mjcf_document_from_element_copy,
    _parse_robosuite_mjcf,
)
from semantic_digital_twin.adapters.robocasa_dataset.semantics import (
    RoboCasaKitchenApplianceCategory,
    RoboCasaKitchenApplianceResolver,
    RoboCasaObjectCategory,
    RoboCasaObjectResolver,
)
from semantic_digital_twin.semantic_annotations.natural_language import (
    NaturalLanguageWithTypeDescription,
)
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Apple,
    Button,
    Cabinet,
    CoffeeMachine,
    Cooktop,
    Dishwasher,
    Door,
    Faucet,
    Floor,
    Handle,
    Knob,
    Lever,
    Microwave,
    Oven,
    Pan,
    Sink,
    Toaster,
)
from semantic_digital_twin.world_description.connections import (
    PrismaticConnection,
    RevoluteConnection,
)

ROBOCASA_RESOURCES_DIR = (
    Path(__file__).resolve().parents[3]
    / "semantic_digital_twin"
    / "resources"
    / "robocasa"
)


def test_kitchen_appliance_resolver_resolves_known_category():
    resolver = RoboCasaKitchenApplianceResolver()
    assert resolver.resolve("cabinet") is Cabinet
    assert resolver.resolve("MICROWAVE") is Microwave


def test_kitchen_appliance_resolver_returns_none_for_unknown_category():
    resolver = RoboCasaKitchenApplianceResolver()
    assert resolver.resolve("paper_towel_holder") is None


def test_kitchen_appliance_resolver_resolves_compound_class_name():
    resolver = RoboCasaKitchenApplianceResolver()
    assert resolver.resolve("HingeCabinet") is Cabinet
    assert resolver.resolve("hinge_cabinet") is Cabinet


def test_kitchen_appliance_resolver_resolves_enum_category():
    resolver = RoboCasaKitchenApplianceResolver()
    assert resolver.resolve(RoboCasaKitchenApplianceCategory.CABINET) is Cabinet


def test_kitchen_appliance_resolver_resolves_floor():
    """
    The floor of a kitchen is what a robot drives on, so it resolves to a floor rather
    than to a description in words.
    """
    resolver = RoboCasaKitchenApplianceResolver()
    assert resolver.resolve(RoboCasaKitchenApplianceCategory.FLOOR) is Floor


def test_object_resolver_resolves_known_category():
    resolver = RoboCasaObjectResolver()
    assert resolver.resolve("apple") is Apple


def test_object_resolver_returns_none_for_unknown_category():
    resolver = RoboCasaObjectResolver()
    assert resolver.resolve("blender") is None


def test_object_resolver_resolves_enum_category():
    resolver = RoboCasaObjectResolver()
    assert resolver.resolve(RoboCasaObjectCategory.APPLE) is Apple


def test_category_from_class_name_converts_upper_camel_case():
    assert _category_from_class_name("HingeCabinet") == "hinge_cabinet"
    assert _category_from_class_name("Sink") == "sink"


def test_mjcf_document_from_element_copy_wraps_element_in_worldbody():
    fixture_body = ET.fromstring(
        '<body name="hinge_cabinet_main">'
        '<geom type="box" size="0.3 0.3 0.5"/>'
        "</body>"
    )

    document = _mjcf_document_from_element_copy(fixture_body)

    root = ET.fromstring(document)
    assert root.tag == "mujoco"
    assert root.find("worldbody/body").attrib["name"] == "hinge_cabinet_main"


def test_mjcf_document_from_element_copy_does_not_mutate_original_element():
    fixture_body = ET.fromstring(
        '<body name="hinge_cabinet_main">'
        '<geom type="box" size="0.3 0.3 0.5"/>'
        "</body>"
    )

    _mjcf_document_from_element_copy(fixture_body)

    # the original element must be unchanged, i.e. a copy (not the element itself) was reparented
    # into the new document
    assert [child.tag for child in fixture_body] == ["geom"]
    assert fixture_body.attrib["name"] == "hinge_cabinet_main"


def test_mjcf_document_from_element_copy_is_parseable_by_mjcf_parser():
    fixture_body = ET.fromstring(
        '<body name="hinge_cabinet_main">'
        '<inertial mass="5.0" pos="0 0 0" diaginertia="1 1 1"/>'
        '<geom type="box" size="0.3 0.3 0.5" contype="1" conaffinity="1" group="3"/>'
        "</body>"
    )

    world = MJCFParser.from_xml_string(
        _mjcf_document_from_element_copy(fixture_body)
    ).parse()

    assert world.get_body_by_name("hinge_cabinet_main") is not None


ROBOSUITE_STYLE_GEOM_GROUPS_MJCF = """
<mujoco>
  <worldbody>
    <body name="base">
      <geom type="box" size="0.1 0.1 0.1" rgba="1 0 0 1"/>
      <geom type="box" size="0.1 0.1 0.1" group="1" rgba="0 1 0 1"/>
    </body>
  </worldbody>
</mujoco>
"""


def test_parse_robosuite_mjcf_excludes_default_group_geoms_from_visuals():
    """
    Robosuite's own convention (confirmed against its own ``mjcf_utils.sort_elements``) treats
    a geom with an unset ``group`` as collision-only, reserving group 1 for visual geoms - the
    opposite of this project's own MJCF convention. ``_parse_robosuite_mjcf`` must relabel that
    default-group geom before parsing, or it would be parsed as visible, as it would be by the
    unmodified, convention-agnostic ``MJCFParser`` alone.
    """
    world = _parse_robosuite_mjcf(
        MJCFParser.from_xml_string(ROBOSUITE_STYLE_GEOM_GROUPS_MJCF)
    )
    base = world.get_kinematic_structure_entity_by_name("base")

    visual_colors = {tuple(shape.color.to_rgba()) for shape in base.visual.shapes}
    assert (1.0, 0.0, 0.0, 1.0) not in visual_colors
    assert (0.0, 1.0, 0.0, 1.0) in visual_colors


ROBOSUITE_STYLE_REGION_GEOM_MJCF = """
<mujoco>
  <worldbody>
    <body name="base">
      <geom type="box" size="0.1 0.1 0.1" group="1" rgba="0 1 0 1"/>
      <geom name="reg_bbox" type="box" size="0.2 0.2 0.2" group="1" rgba="0 0 0 0"
            contype="0" conaffinity="0"/>
    </body>
  </worldbody>
</mujoco>
"""


def test_parse_robosuite_mjcf_excludes_transparent_region_geoms_from_visuals():
    """
    RoboCasa marks the regions it places objects by, such as an object's bounding box,
    with fully transparent geoms in the visual group; they are not part of how the
    object looks.
    """
    world = _parse_robosuite_mjcf(
        MJCFParser.from_xml_string(ROBOSUITE_STYLE_REGION_GEOM_MJCF)
    )
    base = world.get_kinematic_structure_entity_by_name("base")

    assert [tuple(shape.color.to_rgba()) for shape in base.visual.shapes] == [
        (0.0, 1.0, 0.0, 1.0)
    ]


ROBOSUITE_STYLE_UNNAMED_BODIES_MJCF = """
<mujoco>
  <worldbody>
    <body>
      <body name="object">
        <body pos="0 -0.045 0">
          <geom type="box" size="0.1 0.1 0.1" group="1"/>
        </body>
      </body>
    </body>
  </worldbody>
</mujoco>
"""


def test_parse_robosuite_mjcf_gives_every_unnamed_body_a_name_of_its_own():
    """
    Some RoboCasa objects, such as its pans, nest their shapes in more than one unnamed
    body.
    """
    world = _parse_robosuite_mjcf(
        MJCFParser.from_xml_string(ROBOSUITE_STYLE_UNNAMED_BODIES_MJCF)
    )

    names = [body.name.name for body in world.bodies]
    assert len(set(names)) == len(names) == 4
    assert all(names)


ROBOSUITE_STYLE_PAN_WITH_LIQUID_MJCF = """
<mujoco>
  <worldbody>
    <body name="pan_main">
      <geom name="pan_liquid" type="cylinder" size="0.1 0.001" group="1"
            rgba="0.5 0.6 1 0.3" contype="0" conaffinity="0"/>
      <body>
        <geom type="box" size="0.1 0.1 0.02" group="1" rgba="0 1 0 1"
              contype="0" conaffinity="0"/>
        <geom type="box" size="0.1 0.1 0.02"/>
      </body>
    </body>
  </worldbody>
</mujoco>
"""


def test_a_task_object_is_annotated_where_its_shape_is():
    """
    Some RoboCasa objects, such as its pans, keep their shape in a body below the body
    RoboCasa moves them by, which in a task may show only the liquid they hold; the
    annotation goes to the body with the shape, as when the object is loaded alone,
    while the body RoboCasa moves stays the manipulated one.
    """
    world = _parse_robosuite_mjcf(
        MJCFParser.from_xml_string(ROBOSUITE_STYLE_PAN_WITH_LIQUID_MJCF)
    )
    pan_main = world.get_kinematic_structure_entity_by_name("pan_main")

    manipulated = RoboCasaDatasetLoader()._apply_task_object_semantics(
        world,
        [{"name": "pan", "info": {"cat": "pan"}}],
        {"pan": SimpleNamespace(root_body="pan_main")},
    )

    [pan] = world.get_semantic_annotations_by_type(Pan)
    assert manipulated == [pan_main]
    assert pan.root in world.compute_child_kinematic_structure_entities(pan_main)


def test_parse_robosuite_mjcf_keeps_default_group_geoms_collidable():
    """
    Relabelling a default-group geom to ONLY_COLLIDABLE must only affect its visibility, not
    whether it still collides - the whole point of RoboCasa's collision-decomposition proxy
    geoms is to still be collided with.
    """
    world = _parse_robosuite_mjcf(
        MJCFParser.from_xml_string(ROBOSUITE_STYLE_GEOM_GROUPS_MJCF)
    )
    base = world.get_kinematic_structure_entity_by_name("base")

    assert len(base.collision.shapes) == 2


def test_attach_semantic_annotation_uses_kitchen_appliance_resolver():
    world = MJCFParser(str(ROBOCASA_RESOURCES_DIR / "cabinet_fixture.xml")).parse()
    body = world.get_body_by_name("hinge_cabinet_main")

    loader = RoboCasaDatasetLoader()
    loader._attach_semantic_annotation(world, body, "cabinet")

    annotations = world.get_semantic_annotations_by_type(Cabinet)
    assert len(annotations) == 1
    assert annotations[0].root == body


def test_attach_semantic_annotation_falls_back_to_natural_language():
    world = MJCFParser(str(ROBOCASA_RESOURCES_DIR / "cabinet_fixture.xml")).parse()
    body = world.get_body_by_name("hinge_cabinet_main")

    loader = RoboCasaDatasetLoader()
    loader._attach_semantic_annotation(world, body, "paper_towel_holder")

    annotations = world.get_semantic_annotations_by_type(
        NaturalLanguageWithTypeDescription
    )
    assert len(annotations) == 1
    assert annotations[0].type_description == "paper_towel_holder"


def test_attach_semantic_annotation_attaches_door_and_handle_sub_parts():
    world = MJCFParser(str(ROBOCASA_RESOURCES_DIR / "cabinet_fixture.xml")).parse()
    body = world.get_body_by_name("hinge_cabinet_main")
    door_body = world.get_body_by_name("hinge_cabinet_door")

    loader = RoboCasaDatasetLoader()
    loader._attach_semantic_annotation(world, body, "cabinet")

    [cabinet] = world.get_semantic_annotations_by_type(Cabinet)
    [door] = world.get_semantic_annotations_by_type(Door)
    [handle] = world.get_semantic_annotations_by_type(Handle)

    assert door in cabinet.doors
    assert door.root.name.name == "hinge_cabinet_door"

    assert door.handle == handle
    assert handle.root.name.name == "hinge_cabinet_handle"

    # the door's real hinge joint (parsed from the fixture's MJCF) must not have been disturbed by
    # recording the part-whole relationship
    assert isinstance(door_body.parent_connection, RevoluteConnection)
    assert door_body.parent_kinematic_structure_entity == body


def test_find_body_returns_none_for_missing_body():
    world = MJCFParser(str(ROBOCASA_RESOURCES_DIR / "cabinet_fixture.xml")).parse()
    assert RoboCasaDatasetLoader._find_body(world, "does_not_exist") is None


def test_find_body_falls_back_to_prefix_match():
    world = MJCFParser(str(ROBOCASA_RESOURCES_DIR / "cabinet_fixture.xml")).parse()

    body = RoboCasaDatasetLoader._find_body(world, "hinge_cabinet")

    assert body is not None
    assert body.name.name == "hinge_cabinet_main"


def test_apply_object_semantics_annotates_body_with_collision_not_root():
    world = MJCFParser(str(ROBOCASA_RESOURCES_DIR / "cabinet_fixture.xml")).parse()

    loader = RoboCasaDatasetLoader()
    loader._apply_object_semantics(world, "cabinet")

    annotations = world.get_semantic_annotations_by_type(Cabinet)
    assert len(annotations) == 1
    assert annotations[0].root.name.name == "hinge_cabinet_main"
    assert annotations[0].root != world.root


# %% appliance controls as parts of their appliance

APPLIANCE_CONTROLS_FIXTURE = ROBOCASA_RESOURCES_DIR / "appliance_controls_fixture.xml"


@pytest.mark.parametrize(
    "category, appliance_body_name, appliance_type, parts",
    [
        (
            RoboCasaKitchenApplianceCategory.SINK,
            "sink_main_group_main",
            Sink,
            {
                "faucet": (Faucet, {"sink_main_group_spout"}),
                "handle": (Handle, {"sink_main_group_handle"}),
            },
        ),
        (
            RoboCasaKitchenApplianceCategory.STOVE,
            "stove_main_group_main",
            Cooktop,
            {
                "knobs": (
                    Knob,
                    {
                        "stove_main_group_knob_front_left",
                        "stove_main_group_knob_rear_right",
                    },
                ),
            },
        ),
        (
            RoboCasaKitchenApplianceCategory.OVEN,
            "oven_main_group_main",
            Oven,
            {
                "doors": (Door, {"oven_main_group_door"}),
                "knobs": (Knob, {"oven_main_group_knob_temp"}),
            },
        ),
        (
            RoboCasaKitchenApplianceCategory.DISHWASHER,
            "dishwasher_main_group_main",
            Dishwasher,
            {
                "buttons": (Button, {"dishwasher_main_group_button_power"}),
                "doors": (Door, {"dishwasher_main_group_door"}),
            },
        ),
        (
            RoboCasaKitchenApplianceCategory.TOASTER,
            "toaster_main_group_main",
            Toaster,
            {
                "buttons": (Button, {"toaster_main_group_button_cancel"}),
                "knobs": (Knob, {"toaster_main_group_knob_doneness"}),
                "levers": (Lever, {"toaster_main_group_lever"}),
            },
        ),
        (
            RoboCasaKitchenApplianceCategory.COFFEE_MACHINE,
            "coffee_machine_main_group_main",
            CoffeeMachine,
            {
                "buttons": (
                    Button,
                    {
                        "coffee_machine_main_group_Button001",
                        "coffee_machine_main_group_Button002",
                    },
                ),
                "levers": (Lever, {"coffee_machine_main_group_Lever001"}),
            },
        ),
    ],
)
def test_attach_semantic_annotation_attaches_appliance_controls(
    category, appliance_body_name, appliance_type, parts
):
    """
    The controls a RoboCasa appliance ships as bodies of their own become parts of the
    appliance's annotation, each annotated with the type of control it is.
    """
    world = MJCFParser(str(APPLIANCE_CONTROLS_FIXTURE)).parse()
    loader = RoboCasaDatasetLoader()
    loader._attach_semantic_annotation(
        world, world.get_body_by_name(appliance_body_name), category
    )

    [appliance] = world.get_semantic_annotations_by_type(appliance_type)
    for field_name, (part_type, part_body_names) in parts.items():
        value = getattr(appliance, field_name)
        attached_parts = value if isinstance(value, list) else [value]
        assert all(type(part) is part_type for part in attached_parts)
        assert {part.root.name.name for part in attached_parts} == part_body_names


def test_attaching_appliance_controls_keeps_their_joints():
    """
    Recording a control as a part of its appliance leaves the joint the control moves on
    in place.
    """
    world = MJCFParser(str(APPLIANCE_CONTROLS_FIXTURE)).parse()
    toaster_body = world.get_body_by_name("toaster_main_group_main")
    loader = RoboCasaDatasetLoader()
    loader._attach_semantic_annotation(
        world, toaster_body, RoboCasaKitchenApplianceCategory.TOASTER
    )

    knob_body = world.get_body_by_name("toaster_main_group_knob_doneness")
    lever_body = world.get_body_by_name("toaster_main_group_lever")
    assert isinstance(knob_body.parent_connection, RevoluteConnection)
    assert isinstance(lever_body.parent_connection, PrismaticConnection)
    assert knob_body.parent_kinematic_structure_entity == toaster_body
    assert lever_body.parent_kinematic_structure_entity == toaster_body
