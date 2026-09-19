import pytest

from experiments.montessori.franka_bare_pickup_smoke_test import (
    CUBE_POSITION,
    build_scene,
)


def test_bare_pickup_scene_places_the_cube_at_its_configured_position():
    """
    The cube hangs off a free connection whose pose is written through the connection's
    origin setter, which needs the assigned transform to carry a reference frame.
    Without one the cube never reaches the table.
    """
    world, _, cube = build_scene()
    world.update_forward_kinematics()

    position = world.compute_forward_kinematics(world.root, cube).to_position()

    assert float(position.x) == pytest.approx(float(CUBE_POSITION.x))
    assert float(position.y) == pytest.approx(float(CUBE_POSITION.y))
    assert float(position.z) == pytest.approx(float(CUBE_POSITION.z))
