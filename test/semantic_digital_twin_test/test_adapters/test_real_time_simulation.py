"""
Tests for a MuJoCo simulation stepped by its owner and paced to the wall clock.
"""

from __future__ import annotations

import time

import pytest

from ...pytest_environment import runs_in_continuous_integration

from semantic_digital_twin.adapters.real_time_simulation import RealTimeSimulation
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.exceptions import SimulationNotStartedError
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import Connection6DoF
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body


@pytest.fixture
def falling_box_world() -> World:
    world = World()
    with world.modify_world():
        root = Body(name=PrefixedName("root"))
        world.add_body(root)
        box = Body(name=PrefixedName("box"))
        geometry = ShapeCollection(
            [
                Box(
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                        reference_frame=box
                    ),
                    scale=Scale(0.1, 0.1, 0.1),
                )
            ],
            reference_frame=box,
        )
        box.collision, box.visual = geometry, geometry
        world.add_connection(
            Connection6DoF.create_with_dofs(
                world=world,
                parent=root,
                child=box,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=1.0, reference_frame=root
                ),
            )
        )
    return world


def test_advance_before_start_raises(falling_box_world):
    simulation = RealTimeSimulation(world=falling_box_world, headless=True)
    with pytest.raises(SimulationNotStartedError):
        simulation.advance(0.1)


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_unpaced_advance_does_not_wait_for_the_wall_clock(falling_box_world):
    """
    With no real-time factor, advancing a simulated second must finish well before a
    wall-clock second has passed.
    """
    simulated_seconds = 1.0
    with RealTimeSimulation(
        world=falling_box_world, headless=True, real_time_factor=None
    ) as simulation:
        started = time.time()
        simulation.advance(simulated_seconds)
        elapsed = time.time() - started
    assert elapsed < simulated_seconds / 2


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_paced_advance_waits_for_the_wall_clock(falling_box_world):
    simulated_seconds = 0.3
    with RealTimeSimulation(
        world=falling_box_world, headless=True, real_time_factor=1.0
    ) as simulation:
        started = time.time()
        simulation.advance(simulated_seconds)
        elapsed = time.time() - started
    assert elapsed >= simulated_seconds
