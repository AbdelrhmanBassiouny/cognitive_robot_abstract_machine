"""
Tests for tuning a world for physical simulation in MuJoCo: servos on joints, contact
parameters on objects, and a servoed joint being driven rather than teleported.
"""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
import pytest

from ...pytest_environment import runs_in_continuous_integration

from semantic_digital_twin.adapters.multi_sim import (
    MujocoGeom,
    MujocoSolverImpedance,
    MujocoSolverReference,
)
from semantic_digital_twin.adapters.mujoco_tuning import (
    MujocoContactParameters,
    equip_with_servos,
    servo_actuator,
)
from semantic_digital_twin.adapters.real_time_simulation import RealTimeSimulation
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.derivatives import DerivativeMap
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Vector3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    FixedConnection,
    RevoluteConnection,
)
from semantic_digital_twin.world_description.degree_of_freedom import (
    DegreeOfFreedom,
    DegreeOfFreedomLimits,
)
from semantic_digital_twin.world_description.connection_properties import ServoGains
from semantic_digital_twin.world_description.geometry import (
    Box,
    ContactFriction,
    Scale,
)
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

# %% servo gains


def test_servo_actuator_is_a_pd_law_clamped_to_the_joints_range():
    gains = ServoGains(stiffness=100.0, damping=10.0, torque_limit=5.0)
    degree_of_freedom = DegreeOfFreedom(
        name=PrefixedName("hinge"),
        limits=DegreeOfFreedomLimits(
            DerivativeMap(position=-1.0), DerivativeMap(position=1.0)
        ),
    )

    servo = servo_actuator(gains, degree_of_freedom)

    assert servo.gain_type == mujoco.mjtGain.mjGAIN_FIXED
    assert servo.gain_parameters[0] == gains.stiffness
    assert servo.bias_type == mujoco.mjtBias.mjBIAS_AFFINE
    assert servo.bias_parameters[:3] == [0.0, -gains.stiffness, -gains.damping]
    assert servo.control_range == [-1.0, 1.0]
    assert servo.force_range == [-gains.torque_limit, gains.torque_limit]


# %% a servoed pendulum


@dataclass
class PendulumWorld:
    """
    A world with one hinge driven by a servo, and the handles a test needs.
    """

    world: World
    """
    The world itself.
    """

    hinge: RevoluteConnection
    """
    The driven hinge.
    """

    mirrored_hinge: RevoluteConnection
    """
    A second hinge following the driven one with a negative multiplier, sharing its
    degree of freedom.
    """


def _pendulum_world() -> PendulumWorld:
    world = World()
    with world.modify_world():
        root = Body(name=PrefixedName("root"))
        world.add_body(root)
        base = Body(name=PrefixedName("base"))
        world.add_connection(FixedConnection(parent=root, child=base))
        arm = Body(name=PrefixedName("arm"))
        mirrored_arm = Body(name=PrefixedName("mirrored_arm"))
        # the two arms hang at different heights so they never touch each other
        for body, height in ((arm, 0.0), (mirrored_arm, 0.1)):
            body.collision = ShapeCollection(
                [
                    Box(
                        origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                            x=0.1, z=height, reference_frame=body
                        ),
                        scale=Scale(0.2, 0.02, 0.02),
                    )
                ],
                reference_frame=body,
            )
        degree_of_freedom = DegreeOfFreedom(
            name=PrefixedName("hinge"),
            limits=DegreeOfFreedomLimits(
                DerivativeMap(position=-1.0), DerivativeMap(position=1.0)
            ),
        )
        world.add_degree_of_freedom(degree_of_freedom)
        hinge = RevoluteConnection(
            name=PrefixedName("hinge"),
            parent=base,
            child=arm,
            axis=Vector3.Z(reference_frame=arm),
            raw_dof=degree_of_freedom,
        )
        world.add_connection(hinge)
        mirrored_hinge = RevoluteConnection(
            name=PrefixedName("mirrored_hinge"),
            parent=base,
            child=mirrored_arm,
            axis=Vector3.Z(reference_frame=mirrored_arm),
            raw_dof=degree_of_freedom,
            multiplier=-1.0,
        )
        world.add_connection(mirrored_hinge)
    return PendulumWorld(world=world, hinge=hinge, mirrored_hinge=mirrored_hinge)


def test_a_shared_degree_of_freedom_gets_one_servo_from_its_declared_gains():
    pendulum = _pendulum_world()
    pendulum.hinge.raw_dof.servo_gains = ServoGains(
        stiffness=50.0, damping=5.0, torque_limit=2.0
    )

    actuators = equip_with_servos(
        pendulum.world, [pendulum.hinge.raw_dof, pendulum.mirrored_hinge.raw_dof]
    )

    assert list(actuators) == ["hinge"]
    assert pendulum.world.actuators == [actuators["hinge"]]


def test_a_joint_without_declared_gains_gets_no_servo():
    pendulum = _pendulum_world()

    actuators = equip_with_servos(pendulum.world, [pendulum.hinge.raw_dof])

    assert actuators == {}
    assert pendulum.world.actuators == []


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_a_servoed_joint_is_driven_towards_the_world_state_not_teleported():
    """
    Writing a servoed joint's position into the world hands the servo a set point:

    the joint then moves there through the physics, and the world keeps the set point
    rather than being overwritten with the position reached so far.
    """
    pendulum = _pendulum_world()
    pendulum.hinge.raw_dof.servo_gains = ServoGains(
        stiffness=50.0, damping=5.0, torque_limit=2.0
    )
    equip_with_servos(pendulum.world, [pendulum.hinge.raw_dof])
    world = pendulum.world
    set_point = 0.5

    with RealTimeSimulation(
        world=world, headless=True, real_time_factor=None
    ) as simulation:
        simulator = simulation.mujoco_mirror.simulator
        world.state[pendulum.hinge.raw_dof.id].position = set_point
        world.notify_state_change()
        simulation.advance(simulator.step_size)
        after_one_step = simulator.get_joint_value("hinge").result
        simulation.advance(2.0)
        settled = simulator.get_joint_value("hinge").result

    assert 0.0 < after_one_step < set_point
    assert settled == pytest.approx(set_point, abs=0.02)
    assert world.state[pendulum.hinge.raw_dof.id].position == set_point


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_starting_the_simulation_holds_a_servoed_joint_where_the_world_has_it():
    """
    A freshly reset simulation leaves every control input at zero, so a joint the world
    holds elsewhere would rush to zero the moment the physics starts.
    """
    pendulum = _pendulum_world()
    pendulum.hinge.raw_dof.servo_gains = ServoGains(
        stiffness=50.0, damping=5.0, torque_limit=2.0
    )
    equip_with_servos(pendulum.world, [pendulum.hinge.raw_dof])
    world = pendulum.world
    with world.modify_world():
        world.state[pendulum.hinge.raw_dof.id].position = 0.7
    world.notify_state_change()

    with RealTimeSimulation(
        world=world, headless=True, real_time_factor=None
    ) as simulation:
        simulation.advance(1.0)
        held = simulation.mujoco_mirror.simulator.get_joint_value("hinge").result

    assert held == pytest.approx(0.7, abs=0.02)


# %% contact parameters


def test_solver_parameters_round_trip_through_mujocos_own_order():
    reference = MujocoSolverReference(time_constant=0.008, damping_ratio=0.9)
    impedance = MujocoSolverImpedance(
        minimum=0.96, maximum=0.99, width=0.002, midpoint=0.4, power=3.0
    )

    assert MujocoSolverReference(*reference.to_list()) == reference
    assert MujocoSolverImpedance(*impedance.to_list()) == impedance
    assert reference.to_list() == [0.008, 0.9]
    assert impedance.to_list() == [0.96, 0.99, 0.002, 0.4, 3.0]


def test_contact_parameters_reach_every_collision_geometry():
    body = Body(name=PrefixedName("box"))
    body.collision = ShapeCollection(
        [
            Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1)),
            Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1)),
        ],
        reference_frame=body,
    )
    contact = MujocoContactParameters.grasped_object(sliding_friction=0.4)

    contact.apply_to([body])

    for shape in body.collision:
        assert shape.friction == ContactFriction(
            sliding=0.4, torsional=0.05, rolling=0.001
        )
        mujoco_geom = shape.simulator_property(MujocoGeom)
        assert mujoco_geom.solver_reference == contact.solver_reference
        assert mujoco_geom.solver_impedance == contact.solver_impedance


def test_a_surface_leaves_the_geometrys_own_solver_settings():
    body = Body(name=PrefixedName("table"))
    shape = Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1))
    body.collision = ShapeCollection([shape], reference_frame=body)
    own_reference = MujocoSolverReference(time_constant=0.05)
    shape.simulator_property_or_default(MujocoGeom).solver_reference = own_reference

    MujocoContactParameters.surface(sliding_friction=0.2).apply_to([body])

    assert shape.friction == ContactFriction(sliding=0.2)
    assert shape.simulator_property(MujocoGeom).solver_reference == own_reference


def test_a_surface_without_solver_settings_attaches_no_mujoco_property():
    body = Body(name=PrefixedName("table"))
    shape = Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1))
    body.collision = ShapeCollection([shape], reference_frame=body)

    MujocoContactParameters.surface(sliding_friction=0.2).apply_to([body])

    assert shape.friction == ContactFriction(sliding=0.2)
    assert shape.simulator_property(MujocoGeom) is None
