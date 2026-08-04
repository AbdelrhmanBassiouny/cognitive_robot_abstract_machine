"""
Build the Montessori shape-sorting world and have a table-mounted Franka Emika Panda
sort every loose shape into its matching hole -- the same narrative as
:mod:`experiments.montessori.montessori_demo`'s HSRB-driven original, but reaching with
its arm alone (see :meth:`~experiments.montessori.world.MontessoriWorld.mount_stationary_robot`;
the Panda has no mobile base to navigate) and holding each shape by the gripper's own
contact friction throughout the whole run, rather than kinematically teleporting it and
settling it afterwards (see :mod:`experiments.montessori.franka_panda_equipment`).

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.franka_montessori_demo
    python -m experiments.montessori.franka_montessori_demo --viewer
"""

from __future__ import annotations

import argparse
import logging
import random
import threading
import time

import numpy as np
from typing_extensions import Optional

from experiments.montessori.franka_panda_equipment import (
    apply_grasp_contact_parameters,
    equip_panda_for_physical_simulation,
    parse_panda,
)
from experiments.montessori.semantics import MontessoriShape, NoMatchingHoleError
from experiments.montessori.world import MontessoriWorld
from semantic_digital_twin.robots.panda import Panda
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.utils import rclpy_installed

logger = logging.getLogger(__name__)

NODE_NAME = "franka_montessori_demo"
"""
Name of the ROS 2 node this demo's visualization runs against.
"""

MOUNT_STANDOFF_DISTANCE = 0.35
"""
How far past the montessori table's near edge (the short edge nearest the loose-shape
row) the Panda is bolted.

Close enough that every shape in the row and the shape-sorting board sit well inside the
Panda's own ~0.855 m reach from a single, unmoving stance; far enough that the Panda's
own base and the table never share a footprint.
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

MAX_INSERTION_ATTEMPTS = 3
"""
Number of times a single shape's insertion is repeated while the attempt never gets as
far as releasing the shape, before giving up on it and logging a warning.
"""

RETRY_HORIZONTAL_JITTER = 0.003
"""
Maximum magnitude, along either axis, of the random horizontal offset an insertion's drop
point is jittered by.

Releasing every shape at the exact same offset over its hole gives the physics engine no
new information about how it first contacts the hole's edge, so a repeated insertion is
prone to failing the same way again.
"""

SHAPE_SETTLE_DURATION = 2.0
"""
Real-time seconds a just-released shape is given to physically fall and come to rest
before it is checked whether it made it through its hole.

The simulation keeps running throughout (see :mod:`~experiments.montessori.franka_panda_equipment`);
this is a settling wait, not a separate physics pass.
"""


def _mount_position(montessori: MontessoriWorld) -> Point3:
    """
    Where to bolt the Panda: past the table's near edge, at table height, centered on
    the table's long axis so every shape in the row and the board are within reach
    either way.

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


def _random_horizontal_jitter() -> Point3:
    """
    A random ``(x, y, 0)`` offset within :data:`RETRY_HORIZONTAL_JITTER` of the origin,
    so an insertion releases its shape at an actually different drop point.
    """
    return Point3(
        random.uniform(-RETRY_HORIZONTAL_JITTER, RETRY_HORIZONTAL_JITTER),
        random.uniform(-RETRY_HORIZONTAL_JITTER, RETRY_HORIZONTAL_JITTER),
        0.0,
    )


def _insert_shape(
    shape: MontessoriShape,
    montessori: MontessoriWorld,
    context,
    target_horizontal_offset: Optional[Point3] = None,
) -> bool:
    """
    Have the Panda pick up and insert a single loose shape into its matching hole once,
    then let it physically settle under gravity and contacts before checking whether it
    made it through.

    Runs with Giskard's collision avoidance off, matching
    :func:`~experiments.montessori.montessori_demo._insert_shape`'s own reasoning for
    the HSRB: the board's CoACD collision decomposition gives the QP solver far more
    simultaneous distance constraints than this pick-and-place needs.

    :param shape: The shape to insert; must have a matching hole.
    :param montessori: The Montessori scene, with the Panda already mounted and
        equipped (see :func:`~experiments.montessori.franka_panda_equipment.equip_panda_for_physical_simulation`),
        inside a running simulation.
    :param context: The CRAM execution context to run the insertion action in.
    :param target_horizontal_offset: Horizontal offset to release the shape at; a
        random :func:`_random_horizontal_jitter` is used if not given.
    :return: Whether the shape actually fell through its hole after settling.
    """
    from coraplex.datastructures.enums import (
        ApproachDirection,
        Arms,
        ExecutionType,
        VerticalAlignment,
    )
    from coraplex.datastructures.grasp import GraspDescription
    from coraplex.execution_environment import ExecutionEnvironment
    from coraplex.plans.factories import execute_single
    from coraplex.view_manager import ViewManager
    from experiments.montessori.insert_shape_action import InsertMontessoriShapeAction

    offset = target_horizontal_offset or _random_horizontal_jitter()
    action = InsertMontessoriShapeAction(
        montessori_shape=shape,
        board=montessori.board,
        arm=Arms.RIGHT,
        # rotate_gripper: the Panda's wrist otherwise resolves the top-down grasp to a
        # 45-degree orientation from which its Cartesian descent never converges;
        # rotating it a quarter turn lines the fingers up with the shape (unnecessary
        # for the HSR, whose gripper geometry differs, so the action does not do this by
        # default).
        grasp_description=GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.TOP,
            ViewManager.get_end_effector_view(Arms.RIGHT, montessori.robot),
            rotate_gripper=True,
        ),
        target_horizontal_offset=offset,
    )
    with ExecutionEnvironment(
        execution_type=ExecutionType.SIMULATED,
        collision_avoidance=False,
        real_time_pacing=True,
    ):
        node = execute_single(action, context=context)
        node.perform()

    logger.info("Letting %s settle.", shape.name)
    time.sleep(SHAPE_SETTLE_DURATION)
    montessori.world.update_forward_kinematics()

    return action.has_fallen_through_hole()


def _insert_shape_or_none(
    shape: MontessoriShape,
    montessori: MontessoriWorld,
    context,
    attempt: int,
) -> Optional[bool]:
    """
    Attempt one insertion via :func:`_insert_shape`, returning ``None`` instead of
    letting a retryable failure propagate.

    :param shape: The shape to insert; must have a matching hole.
    :param montessori: The Montessori scene, with the Panda already mounted and
        equipped, inside a running simulation.
    :param context: The CRAM execution context to run the insertion action in.
    :param attempt: This attempt's 1-based index, used only for the log message.
    :return: Whether the shape fell through its hole, or ``None`` if this attempt
        failed in a retryable way.
    """
    from coraplex.plans.failures import PlanFailure
    from giskardpy.motion_statechart.exceptions import CollisionViolatedError
    from semantic_digital_twin.exceptions import PointOccupiedError

    try:
        return _insert_shape(shape, montessori, context)
    except (PointOccupiedError, PlanFailure, CollisionViolatedError) as error:
        logger.warning(
            "%s's insertion attempt %d/%d failed (%s); retrying.",
            shape.name,
            attempt,
            MAX_INSERTION_ATTEMPTS,
            error,
        )
        return None


def _insert_all_shapes(montessori: MontessoriWorld, context) -> None:
    """
    Have the Panda pick up and insert every loose shape that has a matching hole into
    the shape-sorting board, skipping any that don't (e.g. the sphere).

    Each shape gets one insertion, whether or not it actually drops through: a shape left
    resting on the board is reported and left there. Only an attempt that never ran --
    the grasp or the motion failed before the shape was released -- is repeated, up to
    :data:`MAX_INSERTION_ATTEMPTS` times, since it says nothing about the shape either
    way. Such a retry picks the shape up from wherever it physically ended up, which is
    not necessarily where it started.

    :param montessori: The Montessori scene, with the Panda already mounted and
        equipped, inside a running simulation.
    :param context: The CRAM execution context to run every insertion action in.
    """
    for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape):
        try:
            montessori.board.hole_for(shape)
        except NoMatchingHoleError:
            logger.info("Skipping %s: no matching hole.", shape.name)
            continue

        fell_through = None
        for attempt in range(1, MAX_INSERTION_ATTEMPTS + 1):
            logger.info(
                "Inserting %s into its matching hole (attempt %d/%d).",
                shape.name,
                attempt,
                MAX_INSERTION_ATTEMPTS,
            )
            fell_through = _insert_shape_or_none(shape, montessori, context, attempt)
            if fell_through is not None:
                break

        if fell_through is None:
            logger.warning(
                "%s could not be inserted in %d attempts; moving on to the next shape.",
                shape.name,
                MAX_INSERTION_ATTEMPTS,
            )
        elif not fell_through:
            logger.warning(
                "%s did not fall through its hole; it may be resting on the board or "
                "wedged in the opening. Moving on to the next shape.",
                shape.name,
            )


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments selecting whether a MuJoCo viewer window is opened.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Open a MuJoCo viewer window; off by default so the demo runs headless.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Build the Montessori world, bolt the Panda next to it, visualize it in RViz, have
    it sort the loose shapes into the board, and keep the live simulation running until
    interrupted.
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
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )

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
    apply_grasp_contact_parameters(
        shape.root
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
    )
    logger.info("Built Montessori world with %d bodies.", len(montessori.world.bodies))

    tf_publisher = TFPublisher(node=node, _world=montessori.world)
    viz_marker_publisher = VizMarkerPublisher(_world=montessori.world, node=node)
    logger.info(
        "Visualizing the Montessori world on topic '%s'.",
        viz_marker_publisher.topic_name,
    )

    multi_sim = MujocoSim(
        world=montessori.world,
        headless=not arguments.viewer,
        step_size=MUJOCO_STEP_SIZE,
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

    multi_sim.start_simulation()
    try:
        _insert_all_shapes(montessori, context)
        logger.info("Sorting done; the simulation keeps running.")
        logger.info("Done. Press Ctrl+C to stop.")
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        multi_sim.stop_simulation()
        viz_marker_publisher.stop()
        tf_publisher.stop()
        executor.shutdown()
        spinner.join(timeout=2.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
