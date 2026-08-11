import pytest

from experiments.montessori.franka_panda_equipment import (
    GRASP_FRICTION,
    GRASP_SOLVER_IMPEDANCE,
    GRASP_SOLVER_REFERENCE,
    PANDA_SCENE_BODIES_TO_DISCARD,
    PANDA_SCENE_PATH,
    apply_grasp_contact_parameters,
    equip_panda_for_physical_simulation,
    parse_panda,
)
from experiments.montessori.world import MontessoriWorld
from semantic_digital_twin.adapters.multi_sim import MujocoBody, MujocoGeom
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.panda import Panda
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

pytestmark = pytest.mark.skipif(
    not PANDA_SCENE_PATH.exists(),
    reason="coraplex_panda_demo/stacking_scene.xml is not present",
)

MOUNT_POSITION = Point3(0.25, 0.0, 0.5)


def _mounted_and_equipped_panda():
    montessori = MontessoriWorld()
    robot = montessori.mount_stationary_robot(Panda, parse_panda(), MOUNT_POSITION)
    equip_panda_for_physical_simulation(robot)
    return montessori, robot


def test_parse_panda_drops_the_stacking_tasks_own_bodies():
    panda_world = parse_panda()

    body_names = {body.name.name for body in panda_world.bodies}
    assert body_names.isdisjoint(PANDA_SCENE_BODIES_TO_DISCARD)


def test_parse_panda_keeps_the_robots_own_body_tree():
    panda_world = parse_panda()

    body_names = {body.name.name for body in panda_world.bodies}
    assert {"link0", "link7", "/hand", "/left_finger", "/right_finger"} <= body_names


def test_parse_panda_drops_the_scenes_own_actuator():
    panda_world = parse_panda()

    assert len(panda_world.actuators) == 0


def test_parse_panda_renames_the_root_so_it_does_not_collide_on_merge():
    panda_world = parse_panda()

    assert panda_world.root.name.name == "panda_mount"


def test_equip_panda_for_physical_simulation_adds_one_actuator_per_controlled_dof():
    montessori, robot = _mounted_and_equipped_panda()

    assert len(montessori.world.actuators) == len(
        robot.degrees_of_freedom_with_hardware_interface
    )


def test_equip_panda_for_physical_simulation_reports_the_controlled_dofs():
    montessori, robot = _mounted_and_equipped_panda()

    physically_simulated_dofs = equip_panda_for_physical_simulation(robot)

    assert physically_simulated_dofs == set(
        robot.degrees_of_freedom_with_hardware_interface
    )


def test_equip_panda_for_physical_simulation_adds_gravity_compensation_to_arm_links():
    montessori, robot = _mounted_and_equipped_panda()
    arm = robot.get_arms()[0]

    for connection in arm.active_connections:
        properties = connection.child.simulator_additional_properties
        assert any(
            isinstance(prop, MujocoBody) and prop.gravitation_compensation_factor == 1.0
            for prop in properties
        )


def test_equip_panda_for_physical_simulation_leaves_the_fingertip_friction_alone():
    montessori, robot = _mounted_and_equipped_panda()
    arm = robot.get_arms()[0]

    # coraplex_panda_demo grasps reliably without overriding its fingertip friction, so
    # equip must not add a grasp-tuned MujocoGeom of its own (see GRASP_FRICTION).
    for finger in arm.end_effector.fingers:
        for shape in finger.root.collision:
            assert all(
                not isinstance(prop, MujocoGeom) or prop.friction != GRASP_FRICTION
                for prop in shape.simulator_additional_properties
            )


def _box_body_with_geometry() -> Body:
    return Body.from_shape_collection(
        PrefixedName("box", "test"),
        ShapeCollection([Box(scale=Scale(0.03, 0.03, 0.03))]),
    )


def test_apply_grasp_contact_parameters_sets_friction_reference_and_impedance():
    body = _box_body_with_geometry()

    apply_grasp_contact_parameters([body])

    [geometry] = list(body.collision)
    [mujoco_geom] = [
        prop
        for prop in geometry.simulator_additional_properties
        if isinstance(prop, MujocoGeom)
    ]
    assert mujoco_geom.friction == GRASP_FRICTION
    assert mujoco_geom.solver_reference == GRASP_SOLVER_REFERENCE
    assert mujoco_geom.solver_impedance == GRASP_SOLVER_IMPEDANCE


def test_apply_grasp_contact_parameters_modifies_an_existing_mujoco_geom_in_place():
    body = _box_body_with_geometry()
    [geometry] = list(body.collision)
    geometry.simulator_additional_properties.append(
        MujocoGeom(friction=[1.0, 0.005, 0.0001])
    )

    apply_grasp_contact_parameters([body])

    # A second, appended MujocoGeom would be silently ignored by MujocoBuilder, which
    # reads only the first one -- so the existing one must be modified, not duplicated.
    mujoco_geoms = [
        prop
        for prop in geometry.simulator_additional_properties
        if isinstance(prop, MujocoGeom)
    ]
    assert len(mujoco_geoms) == 1
    assert mujoco_geoms[0].friction == GRASP_FRICTION
