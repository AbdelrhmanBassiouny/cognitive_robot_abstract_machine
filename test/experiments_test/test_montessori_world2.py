import pytest

from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world2 import (
    SHAPE_ROW_SPACING,
    SHAPE_ROW_START_X,
    SHAPE_ROW_Y,
    SHAPE_STAND_POSITION,
    SHAPE_STAND_SCALE,
    MontessoriWorld2,
)


def test_montessori_world2_places_movable_shapes_resting_on_the_shape_stand():
    """
    A movable shape is attached by a free connection whose pose is written through the
    connection's origin setter, which needs the assigned transform to carry a reference
    frame. Without one the shape never reaches the stand at all.
    """
    montessori = MontessoriWorld2(shapes_are_movable=True)
    montessori.world.update_forward_kinematics()

    shapes = montessori.world.get_semantic_annotations_by_type(MontessoriShape)
    assert shapes

    stand_top_z = float(SHAPE_STAND_POSITION.z) + SHAPE_STAND_SCALE.z / 2
    x_positions = []
    for shape in shapes:
        position = shape.global_transform.to_position()
        lowest_local_z = shape.root.collision.combined_mesh.bounds[0][2]
        assert float(position.z) + lowest_local_z == pytest.approx(stand_top_z)
        assert float(position.y) == pytest.approx(SHAPE_ROW_Y)
        x_positions.append(float(position.x))

    assert sorted(x_positions) == pytest.approx(
        [SHAPE_ROW_START_X + index * SHAPE_ROW_SPACING for index in range(len(shapes))]
    )
