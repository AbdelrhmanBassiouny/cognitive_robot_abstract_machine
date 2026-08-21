"""
Tracy parks both arms, in MuJoCo.

Runs entirely in a local MuJoCo simulation built from Tracy's own URDF, resolved
through the ``iai_tracy_description`` ROS package -- no controller or perception
pipeline needed.

Does not use Giskard at all: the joint targets are commanded directly to a MuJoCo
actuator via :class:`~real_time_simulation.RealTimeSimulation`, not through a
``ParkArmsAction``/``JointPositionList`` motion goal. Three earlier attempts routed
through Giskard and failed -- kinematic driving with no actuator moved very badly,
physical simulation with invented gains oscillated without ever converging, and physical
simulation with real, empirically-tuned gains still failed to reach the target, which
turned out to be Giskard's own control loop reading back its own prior command rather
than the robot's true physical position (see :mod:`tracy_equipment`'s own docstring for
the full diagnosis). Driving the actuator directly sidesteps Giskard, and
:class:`~real_time_simulation.RealTimeSimulation` steps physics from the calling thread
rather than the background thread a Giskard-driven run normally uses, which sidesteps a
second, related race in reading the true position back out.
"""

from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.robots.tracy import Tracy

# coraplex/demos is not part of the coraplex package (only coraplex/src is on
# sys.path); this "demos" tree is a collection of standalone scripts run directly
# (python coraplex/demos/coraplex_tracy_demo/demo.py), matching every sibling demo
# here, so these sibling modules are only reachable as bare imports.
from real_time_simulation import RealTimeSimulation
from tracy_equipment import (
    apply_gravity_compensation,
    close_grippers,
    equip_arms_with_servos,
    strip_collision_geometry,
)

logger = logging.getLogger(__name__)

CONVERGENCE_THRESHOLD = 0.01
"""
Maximum per-joint error, in radians, :func:`main` waits for before ending the park
motion; comfortably above the roughly 0.003 rad worst-case residual observed in
practice, and far tighter than a visible difference in pose.
"""

MAXIMUM_PARK_DURATION = 10.0
"""
Simulated seconds :func:`main` waits for both arms to reach :data:`CONVERGENCE_THRESHOLD`
before giving up and reporting whichever joint is furthest off; comfortably above the
roughly 3 simulated seconds a park motion takes in practice.
"""


def _park_targets(robot: Tracy) -> dict[str, float]:
    """
    Every joint of both arms, mapped to its own park target.

    :param robot: The robot to read park targets from.
    """
    targets: dict[str, float] = {}
    for arm in robot.get_arms():
        park_state = next(
            joint_state
            for joint_state in arm.joint_states
            if joint_state.state_type == StaticJointState.PARK
        )
        targets.update(
            {
                connection.raw_dof.name.name: target
                for connection, target in zip(
                    park_state.connections, park_state.target_values
                )
            }
        )
    return targets


def main(headless: bool = False) -> None:
    """
    Build the scene, park both arms, and report whether they converged.

    :param headless: Whether to run without opening MuJoCo's viewer window.
    """
    world = URDFParser.from_file(Tracy.get_ros_file_path()).parse()
    robot = Tracy.from_world(world)

    close_grippers(world, robot)
    apply_gravity_compensation(world, robot)
    strip_collision_geometry(world, robot)
    actuators = equip_arms_with_servos(world, robot)
    targets = _park_targets(robot)

    with RealTimeSimulation(world=world, headless=headless, step_size=1e-3) as sim:
        for joint_name, target in targets.items():
            sim.command(actuators[joint_name], target)

        simulated_time = 0.0
        step = 0.05
        while simulated_time < MAXIMUM_PARK_DURATION:
            sim.advance(step)
            simulated_time += step
            errors = {
                joint_name: abs(
                    sim.multi_sim.simulator.get_joint_value(joint_name).result - target
                )
                for joint_name, target in targets.items()
            }
            if max(errors.values()) < CONVERGENCE_THRESHOLD:
                logger.info("Both arms parked after %.2fs.", simulated_time)
                break
        else:
            worst_joint = max(errors, key=errors.get)
            logger.warning(
                "Arms did not park within %.0fs; worst joint %s is %.3f rad off.",
                MAXIMUM_PARK_DURATION,
                worst_joint,
                errors[worst_joint],
            )

        if not headless:
            while sim.is_running:
                sim.advance(step)


if __name__ == "__main__":
    main()
