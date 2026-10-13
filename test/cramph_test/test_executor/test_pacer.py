from time import perf_counter

import numpy as np

import pytest

from cramph.exceptions import NonPositiveRealTimeFactorError
from cramph.executor import (
    NoPacing,
    RealTimePacer,
    SimulationPacer,
    SteppedSimulationPacer,
)
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import Connection6DoF
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from ...pytest_environment import runs_in_continuous_integration


def test_simulation_pacer_timing_real_time(monkeypatch):
    pacer = SimulationPacer(real_time_factor=1.0)
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert np.isclose(perf_counter() - start_time, 1.0, rtol=0.01)


def test_simulation_pacer_timing_2x(monkeypatch):
    pacer = SimulationPacer(real_time_factor=2.0)
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    actual = perf_counter() - start_time
    assert np.isclose(actual, 0.5, rtol=0.01)


def test_simulation_pacer_timing_halfx(monkeypatch):
    pacer = SimulationPacer(real_time_factor=0.5)
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert np.isclose(perf_counter() - start_time, 2.0, rtol=0.01)


def test_no_pacing_does_not_wait():
    pacer = NoPacing()
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert perf_counter() - start_time < 0.01


def test_a_pacer_has_no_target_frequency_before_it_paces_a_loop():
    assert NoPacing().target_frequency is None


def test_real_time_pacer_holds_the_target_frequency():
    pacer = RealTimePacer()
    pacer.target_frequency = 50
    start_time = perf_counter()
    for i in range(50):
        pacer.sleep()
    assert np.isclose(perf_counter() - start_time, 1.0, rtol=0.01)


def test_a_simulation_cannot_be_configured_to_stand_still():
    with pytest.raises(NonPositiveRealTimeFactorError):
        SimulationPacer(real_time_factor=0.0)


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_stepped_simulation_pacer_advances_the_physics_one_cycle_per_sleep():
    """
    A box dropped from a metre falls under the simulation's gravity exactly as far as
    the paced cycles add up to, so the physics and the loop stay in lockstep.
    """
    world = World()
    with world.modify_world():
        root = Body(name=PrefixedName("root"))
        world.add_body(root)
        box = Body(name=PrefixedName("box"))
        box.collision = ShapeCollection(
            [Box(origin=HomogeneousTransformationMatrix(), scale=Scale(0.1, 0.1, 0.1))],
            reference_frame=box,
        )
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
    cycles, frequency = 25, 50

    simulation = MujocoSim(world=world, headless=True)
    simulation.start_stepped_simulation()
    try:
        pacer = SteppedSimulationPacer(simulation)
        pacer.target_frequency = frequency
        for _ in range(cycles):
            pacer.sleep()
        height = simulation.simulator.get_body_position(body_name="box").result[2]
    finally:
        simulation.stop_simulation()

    fallen = 0.5 * 9.81 * (cycles / frequency) ** 2
    assert height == pytest.approx(1.0 - fallen, abs=0.01)
