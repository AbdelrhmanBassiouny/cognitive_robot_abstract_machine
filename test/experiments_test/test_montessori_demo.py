import pytest

from experiments.montessori.montessori_demo import (
    ARM_ACTUATOR_POSITION_GAIN,
    BASE_ACTUATOR_POSITION_GAIN,
    BASE_JOINT_DAMPING,
    BASE_JOINT_DRY_FRICTION,
    RETRY_HORIZONTAL_JITTER,
    _base_connections_without_hardware_interface,
    _base_degrees_of_freedom_without_hardware_interface,
    _enable_robot_table_collision_avoidance,
    _hold_controlled_joints_in_mujoco,
    _make_all_shapes_movable_in_mujoco,
    _make_shape_movable_in_mujoco,
    _random_horizontal_jitter,
    _settle_shape_in_mujoco,
)
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.montessori.world import MontessoriWorld, robot_installed
from semantic_digital_twin.robots.hsrb import HSRB
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)

EXPECTED_BASE_DOF_NAMES = {
    "base_roll_joint",
    "base_l_passive_wheel_x_frame_joint",
    "base_l_passive_wheel_y_frame_joint",
    "base_l_passive_wheel_z_joint",
    "base_r_passive_wheel_x_frame_joint",
    "base_r_passive_wheel_y_frame_joint",
    "base_r_passive_wheel_z_joint",
    "base_l_drive_wheel_joint",
    "base_r_drive_wheel_joint",
}


@pytest.fixture
def montessori_with_robot():
    if not robot_installed(HSRB):
        pytest.skip("hsr_description is not installed")

    montessori = MontessoriWorld()
    montessori.spawn_robot(HSRB)
    return montessori


def test_base_degrees_of_freedom_without_hardware_interface_finds_the_wheel_joints(
    montessori_with_robot,
):
    robot = montessori_with_robot.robot
    base_dof_names = {
        dof.name.name
        for dof in _base_degrees_of_freedom_without_hardware_interface(robot)
    }

    assert base_dof_names == EXPECTED_BASE_DOF_NAMES


def test_base_degrees_of_freedom_without_hardware_interface_excludes_controlled_and_gripper_dofs(
    montessori_with_robot,
):
    robot = montessori_with_robot.robot
    base_dofs = set(_base_degrees_of_freedom_without_hardware_interface(robot))

    assert base_dofs.isdisjoint(robot.degrees_of_freedom_with_hardware_interface)
    assert not any(dof.name.name.startswith("hand_") for dof in base_dofs)


def test_hold_controlled_joints_in_mujoco_adds_one_actuator_per_held_dof(
    montessori_with_robot,
):
    robot = montessori_with_robot.robot
    controlled_dofs = set(robot.degrees_of_freedom_with_hardware_interface)
    base_dofs = set(_base_degrees_of_freedom_without_hardware_interface(robot))

    _hold_controlled_joints_in_mujoco(robot)

    held_dofs = {dof for actuator in robot._world.actuators for dof in actuator.dofs}
    assert held_dofs == controlled_dofs | base_dofs


def test_hold_controlled_joints_in_mujoco_uses_a_weaker_gain_for_the_base(
    montessori_with_robot,
):
    robot = montessori_with_robot.robot
    base_dofs = set(_base_degrees_of_freedom_without_hardware_interface(robot))

    _hold_controlled_joints_in_mujoco(robot)

    for actuator in robot._world.actuators:
        [mujoco_actuator] = actuator.simulator_additional_properties
        expected_gain = (
            BASE_ACTUATOR_POSITION_GAIN
            if actuator.dofs[0] in base_dofs
            else ARM_ACTUATOR_POSITION_GAIN
        )
        assert mujoco_actuator.gain_parameters[0] == expected_gain


def test_hold_controlled_joints_in_mujoco_adds_joint_damping_to_the_base(
    montessori_with_robot,
):
    robot = montessori_with_robot.robot
    base_connections = _base_connections_without_hardware_interface(robot)

    _hold_controlled_joints_in_mujoco(robot)

    for connection in base_connections:
        assert connection.dynamics.damping == BASE_JOINT_DAMPING
        assert connection.dynamics.dry_friction == BASE_JOINT_DRY_FRICTION


def test_random_horizontal_jitter_stays_within_the_configured_bound():
    jitter = _random_horizontal_jitter()

    assert abs(float(jitter.x)) <= RETRY_HORIZONTAL_JITTER
    assert abs(float(jitter.y)) <= RETRY_HORIZONTAL_JITTER
    assert float(jitter.z) == 0.0


def test_random_horizontal_jitter_varies_between_calls():
    jitters = {
        (float(jitter.x), float(jitter.y))
        for jitter in (_random_horizontal_jitter() for _ in range(20))
    }

    assert len(jitters) > 1


def test_make_shape_movable_in_mujoco_replaces_the_fixed_connection():
    montessori = MontessoriWorld()
    [shape] = [
        shape
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category == "sphere"
    ]

    _make_shape_movable_in_mujoco(shape, montessori.world)

    assert isinstance(shape.root.parent_connection, Connection6DoF)


def test_make_shape_movable_in_mujoco_preserves_the_shapes_pose():
    montessori = MontessoriWorld()
    [shape] = [
        shape
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category == "sphere"
    ]
    montessori.world.update_forward_kinematics()
    position_before = shape.global_transform.to_position()

    _make_shape_movable_in_mujoco(shape, montessori.world)
    montessori.world.update_forward_kinematics()
    position_after = shape.global_transform.to_position()

    assert float(position_after.x) == pytest.approx(float(position_before.x))
    assert float(position_after.y) == pytest.approx(float(position_before.y))
    assert float(position_after.z) == pytest.approx(float(position_before.z))


def test_make_all_shapes_movable_in_mujoco_replaces_every_shapes_connection():
    montessori = MontessoriWorld()
    shapes = list(montessori.world.get_semantic_annotations_by_type(MontessoriShape))
    assert shapes

    _make_all_shapes_movable_in_mujoco(montessori)

    assert all(
        isinstance(shape.root.parent_connection, Connection6DoF) for shape in shapes
    )


def test_settle_shape_in_mujoco_fixes_the_shape_where_gravity_actually_settles_it():
    montessori = MontessoriWorld()
    montessori.world.update_forward_kinematics()

    [shape] = [
        shape
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category == MontessoriShapeCategory.TRIANGULAR_PRISM
    ]
    hole = montessori.board.hole_for(shape)
    hole_position = hole.root.global_transform.to_position()

    # place the shape hovering just above its hole, as PlaceAction's kinematic
    # teleport would, rather than physically dropped through it
    with montessori.world.modify_world():
        montessori.world.remove_connection(shape.root.parent_connection)
        montessori.world.add_connection(
            FixedConnection(
                parent=montessori.world.root,
                child=shape.root,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=hole_position.x, y=hole_position.y, z=hole_position.z + 0.02
                ),
            )
        )
    montessori.world.update_forward_kinematics()
    position_before = shape.global_transform.to_position()

    _settle_shape_in_mujoco(shape, montessori, headless=True)
    montessori.world.update_forward_kinematics()
    position_after = shape.global_transform.to_position()

    # settled back into a FixedConnection, not left as the free Connection6DoF used
    # to simulate it
    assert isinstance(shape.root.parent_connection, FixedConnection)
    # physically dropped through the hole under gravity, not merely left hovering
    # where it started
    assert float(position_after.z) < float(position_before.z) - 0.05


def test_enable_robot_table_collision_avoidance_checks_the_robot_against_the_table(
    montessori_with_robot,
):
    montessori = montessori_with_robot
    [table] = montessori.world.get_semantic_annotations_by_type(Table)

    _enable_robot_table_collision_avoidance(montessori)
    montessori.world.collision_manager.update_collision_matrix()

    checked_bodies = {
        body
        for check in montessori.world.collision_manager.collision_matrix.collision_checks
        for body in (check.body_a, check.body_b)
    }
    assert set(table.bodies_with_collision) <= checked_bodies
    assert set(montessori.robot.bodies_with_collision) & checked_bodies


def test_enable_robot_table_collision_avoidance_does_not_check_the_board(
    montessori_with_robot,
):
    """
    Only the table is registered, not the shape-sorting board: checking the robot
    against the board's ~40-50-piece CoACD collision decomposition too overloads
    Giskard's QP solver for the tight-clearance pickup motion (a convergence timeout,
    not a detected collision).
    """
    montessori = montessori_with_robot

    _enable_robot_table_collision_avoidance(montessori)
    montessori.world.collision_manager.update_collision_matrix()

    checked_bodies = {
        body
        for check in montessori.world.collision_manager.collision_matrix.collision_checks
        for body in (check.body_a, check.body_b)
    }
    assert set(montessori.board.bodies_with_collision).isdisjoint(checked_bodies)
