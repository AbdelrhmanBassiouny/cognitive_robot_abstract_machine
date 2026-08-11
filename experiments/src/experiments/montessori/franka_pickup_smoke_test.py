"""
Smallest possible proof that a Franka Panda, bolted next to the Montessori table, can
pick up and put down a loose shape by friction alone -- before wiring in the full
hole-insertion narrative (:mod:`experiments.montessori.montessori_demo`).

Deliberately does not insert the shape into its matching hole: it only proves the mount
position, actuator tuning and contact friction (see
:mod:`experiments.montessori.franka_panda_equipment`) let the Panda grasp and move
something on this table at all, via :class:`~coraplex.robot_plans.actions.core.pick_up.PickUpAction`
and :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction` directly, with no
navigation step (the Panda has no mobile base to navigate).

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.franka_pickup_smoke_test
    python -m experiments.montessori.franka_pickup_smoke_test --viewer --shape cube
"""

from __future__ import annotations

import argparse
import logging
import threading

import numpy as np

from experiments.montessori.franka_panda_equipment import (
    BOARD_FRICTION,
    apply_contact_friction,
    apply_montessori_grasp_contact_parameters,
    equip_panda_for_physical_simulation,
    parse_panda,
)
from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import MontessoriWorld
from semantic_digital_twin.robots.panda import Panda
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.utils import rclpy_installed

logger = logging.getLogger(__name__)

NODE_NAME = "franka_pickup_smoke_test"
"""
Name of the ROS 2 node this script's execution runs against.
"""

MOUNT_STANDOFF_DISTANCE = 0.35
"""
How far past the montessori table's near edge (the short edge nearest the loose-shape
row) the Panda is bolted.

Close enough that every shape in the row (0.40-0.60 m away at this standoff) and the
board (0.65 m) sit well inside the Panda's own ~0.855 m reach; far enough that the
Panda's own base and the table never share a footprint.
"""

MUJOCO_STEP_SIZE = 1e-4
"""
Physics step size, matching ``coraplex_panda_demo/demo.py``'s own exactly.

The Panda's position-servo actuators (see
:mod:`experiments.montessori.franka_panda_equipment`) use the same gains that demo
tunes for this step size; a coarser step under the same gains was observed to make the
arm shake rather than hold still near a commanded pose.
"""

SYNC_RATE_HZ = 100
"""
Rate at which the physically simulated joints' real, physics-driven positions are read
back into the world model.
"""

PLACE_OFFSET_Y = 0.1
"""
How far, along the table's long axis, the shape is placed from where it was picked up --
enough to make an actual move visible, without leaving the table or another shape's
spot.
"""


def _mount_position(montessori: MontessoriWorld) -> Point3:
    """
    Where to bolt the Panda: past the table's near edge, at table height, centered on
    the table's long axis so every shape in the row is within reach either way.

    :param montessori: The Montessori scene the Panda is being mounted next to.
    """
    table_bounding_box = (
        montessori.world.get_body_by_name("table")
        .collision.as_bounding_box_collection_in_frame(montessori.world.root)
        .bounding_box()
    )
    return Point3(
        table_bounding_box.max_x + MOUNT_STANDOFF_DISTANCE,
        0.0,
        table_bounding_box.max_z,
    )


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments selecting whether a MuJoCo viewer window is opened and
    which shape category to pick up.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Open a MuJoCo viewer window; off by default so this runs headless.",
    )
    parser.add_argument(
        "--shape",
        default="cube",
        help="Category of the loose shape to pick up and move (default: cube).",
    )
    return parser.parse_args()


def _shape_with_category(montessori: MontessoriWorld, category: str) -> MontessoriShape:
    """
    The single loose shape of the given category in ``montessori``.

    :param montessori: The Montessori scene to search.
    :param category: The shape category to find, e.g. ``"cube"``.
    """
    [shape] = [
        shape
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category == category
    ]
    return shape


def main() -> None:
    """
    Build the scene, bolt the Panda next to it, and try to pick one shape up and move
    it, reporting whether it actually moved.
    """
    # force: the CRAM/Giskard stack configures the root logger on import, which would
    # otherwise swallow this script's own reporting.
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    arguments = _parse_arguments()

    if not rclpy_installed():
        logger.error("rclpy is not installed; this needs the CRAM/Giskard stack.")
        return

    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    from coraplex.datastructures.dataclasses import Context
    from coraplex.datastructures.enums import (
        ApproachDirection,
        Arms,
        ExecutionType,
        VerticalAlignment,
    )
    from coraplex.datastructures.grasp import GraspDescription
    from coraplex.execution_environment import ExecutionEnvironment
    from coraplex.plans.factories import sequential
    from coraplex.plans.failures import PlanFailure
    from coraplex.robot_plans.actions.core.pick_up import PickUpAction
    from coraplex.robot_plans.actions.core.placing import PlaceAction
    from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.spatial_types.spatial_types import Pose

    if not rclpy.ok():
        rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    spinner.start()

    montessori = MontessoriWorld(shapes_are_movable=True)
    mount_position = _mount_position(montessori)
    montessori.add_robot_stand(mount_position)
    robot = montessori.mount_stationary_robot(
        Panda, parse_panda(), mount_position, mount_yaw=np.pi
    )
    physically_simulated_dofs = equip_panda_for_physical_simulation(robot)
    apply_montessori_grasp_contact_parameters(
        montessori.world.get_semantic_annotations_by_type(MontessoriShape)
    )
    apply_contact_friction([montessori.board.root], BOARD_FRICTION)
    shape = _shape_with_category(montessori, arguments.shape)

    multi_sim = MujocoSim(
        world=montessori.world,
        headless=not arguments.viewer,
        step_size=MUJOCO_STEP_SIZE,
        # None: run as fast as the CPU allows rather than throttled to wall-clock
        # real time. real_time_pacing paces against context.simulation_clock (set
        # below to this simulation's own clock), so the whole pick-and-place still
        # completes correctly, just without waiting on wall-clock real time to do it.
        real_time_factor=None if not arguments.viewer else 1.0,
        physically_simulated_dofs=physically_simulated_dofs,
        sync_rate_hz=SYNC_RATE_HZ,
    )
    context = Context(
        montessori.world,
        robot,
        ros_node=node,
        update_world_model_attachment=False,
    )
    context.simulation_clock = lambda: multi_sim.simulator.current_simulation_time
    arm = robot.get_arms()[0]
    gripper = arm.end_effector

    multi_sim.start_simulation()
    try:
        montessori.world.update_forward_kinematics()
        start_position = shape.root.global_transform.to_position()

        plan = sequential(
            [
                ParkArmsAction(Arms.RIGHT),
                PickUpAction(
                    shape.root,
                    Arms.RIGHT,
                    GraspDescription(
                        ApproachDirection.FRONT,
                        VerticalAlignment.TOP,
                        gripper,
                        rotate_gripper=True,
                    ),
                ),
                PlaceAction(
                    shape.root,
                    Pose.from_xyz_rpy(
                        x=start_position.x,
                        y=start_position.y + PLACE_OFFSET_Y,
                        z=start_position.z,
                        reference_frame=montessori.world.root,
                    ),
                    Arms.RIGHT,
                ),
                ParkArmsAction(Arms.RIGHT),
            ],
            context=context,
        )
        with ExecutionEnvironment(
            execution_type=ExecutionType.SIMULATED,
            # Off: the montessori scene's board (a ~40-50-piece CoACD collision
            # decomposition; see MontessoriWorld) gives the QP solver far more
            # simultaneous distance constraints than this pick-and-place needs, and was
            # observed elsewhere in this codebase's history to stall convergence on a
            # tight-clearance grasp even when the reach itself stays well clear of the
            # board.
            collision_avoidance=False,
            real_time_pacing=True,
            # Fail fast while tuning the grasp: the default budget (2000 ticks per
            # motion mapping) lets a genuinely unreachable/oscillating goal grind for
            # minutes before giving up. A goal that's actually converging reaches
            # is_end_motion() in a small fraction of this regardless.
            max_ticks_per_motion_mapping=300,
        ):
            try:
                plan.perform()
            except PlanFailure as failure:
                logger.error("Pick-and-place did not finish: %s", failure)

        montessori.world.update_forward_kinematics()
        end_position = shape.root.global_transform.to_position()
        moved_horizontally = float(
            np.linalg.norm(
                [
                    float(end_position.x) - float(start_position.x),
                    float(end_position.y) - float(start_position.y),
                ]
            )
        )
        logger.info(
            "%s: (%.3f, %.3f, %.3f) -> (%.3f, %.3f, %.3f); moved %.3f m horizontally "
            "(moved: %s)",
            shape.name.name,
            float(start_position.x),
            float(start_position.y),
            float(start_position.z),
            float(end_position.x),
            float(end_position.y),
            float(end_position.z),
            moved_horizontally,
            moved_horizontally > PLACE_OFFSET_Y / 2,
        )
    finally:
        multi_sim.stop_simulation()
        executor.shutdown()
        spinner.join(timeout=2.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
