from experiments.tracy_experiments.stacking.stacking_actions import stack_target_pose

STACK_X = 0.8
STACK_Y = 0.0
TABLE_TOP_Z = 1.0
CUBE_SIZE = 0.05


def _position_z(index: int) -> float:
    pose = stack_target_pose(index, STACK_X, STACK_Y, TABLE_TOP_Z, CUBE_SIZE, None)
    return float(pose.to_position().z)


def test_stack_target_pose_base_index_rests_on_the_table():
    assert _position_z(0) == TABLE_TOP_Z + CUBE_SIZE / 2


def test_stack_target_pose_adds_exactly_one_cube_height_per_index():
    assert _position_z(1) == _position_z(0) + CUBE_SIZE
    assert _position_z(2) == _position_z(1) + CUBE_SIZE
    assert _position_z(3) == _position_z(0) + 3 * CUBE_SIZE


def test_stack_target_pose_keeps_the_shared_xy():
    pose = stack_target_pose(2, STACK_X, STACK_Y, TABLE_TOP_Z, CUBE_SIZE, None)
    position = pose.to_position()
    assert float(position.x) == STACK_X
    assert float(position.y) == STACK_Y
