"""
Minimal Tracy sanity check: mount Tracy on its own built-in table (no Montessori board
or loose shapes at all) and park both arms via
:func:`~experiments.tracy_experiments.trajectory_planning.park_arms`.

:mod:`~experiments.tracy_experiments.montessori.montessori_demo_mujoco`'s first full run, built on
CRAM's ``ParkArmsAction`` ticking Giskard live against Tracy's physically simulated
joints, stalled: Giskard's own QP control loop reads ``world.state`` as its belief of
the robot's current position, but for a physically simulated DOF that same state is also
written by Giskard's own prior command, not exclusively by MuJoCo's true physics
readback -- so Giskard was satisfied by its own prior write, not by the robot actually
having moved. This script isolates whether Tracy's own mounting and physical-simulation
equipping (see :mod:`~experiments.tracy_experiments.equipment`) work at all, using the
same direct-actuator, plan-then-execute architecture
:mod:`~experiments.tracy_experiments.montessori.montessori_demo_mujoco` now uses, before putting
the Montessori task back on top of it.

Run with (the ``experiments`` package must be importable, and ``iai_tracy_description``
must be built and sourced)::

    python -m experiments.tracy_experiments.parkarms_demo
    python -m experiments.tracy_experiments.parkarms_demo --viewer
"""

from __future__ import annotations

import argparse
import logging
import time

from coraplex.datastructures.enums import Arms
from experiments.montessori.world import (
    _body_with_visual_only_shape,
    mount_stationary_robot,
)
from experiments.tracy_experiments.equipment import (
    apply_gravity_compensation,
    equip_arms_with_servos,
    equip_grippers_with_servos,
    exclude_self_collision,
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from experiments.tracy_experiments.trajectory_planning import park_arms
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

FLOOR_SCALE = Scale(4.0, 4.0, 0.02)
"""
Size of the bare floor slab Tracy is mounted on; just big enough to visibly carry its
own table.
"""

FLOOR_Z = 0.0
"""
Height of the ground Tracy's table is mounted to stand on.
"""


def _build_world() -> tuple[World, Tracy]:
    """
    Build a bare floor and mount Tracy on it -- no Montessori board, no loose shapes.

    :return: The assembled world and the mounted Tracy.
    """
    world = World()
    root = Body(name=PrefixedName(name="root", prefix="world"))
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        floor = _body_with_visual_only_shape(
            PrefixedName("floor", "tracy_parkarms"),
            Box(scale=FLOOR_SCALE, color=Color.GREY()),
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=floor,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.0, y=0.0, z=FLOOR_Z - FLOOR_SCALE.z / 2
                ),
            )
        )

    tracy_world = parse_tracy()
    mount_position, table_top_z = tracy_table_mount_position(tracy_world, x=0.0, y=0.0)
    logger.info(
        "Mounting Tracy at %s; table top lands at z=%.3f.", mount_position, table_top_z
    )
    robot = mount_stationary_robot(
        world, Tracy, tracy_world, mount_position, mount_yaw=0.0
    )
    return world, robot


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Open a MuJoCo viewer window; off by default so the demo runs headless.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    arguments = _parse_arguments()

    world, robot = _build_world()
    apply_gravity_compensation(world, robot)
    exclude_self_collision(world, robot)
    arm_actuators = equip_arms_with_servos(world, robot)
    gripper_actuators = equip_grippers_with_servos(world, robot)
    actuators = {**arm_actuators, **gripper_actuators}
    logger.info("Built world with %d bodies.", len(world.bodies))

    with RealTimeSimulation(world=world, headless=not arguments.viewer) as sim:
        try:
            time.sleep(2)
            logger.info("Parking both arms.")
            park_arms(sim, actuators, robot, [Arms.LEFT, Arms.RIGHT])
            logger.info("Both arms parked.")
        finally:
            if arguments.viewer:
                while sim.is_running:
                    time.sleep(0.1)


if __name__ == "__main__":
    main()
