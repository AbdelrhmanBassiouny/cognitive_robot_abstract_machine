"""
Build the Montessori shape-sorting world on Tracy's own built-in table and have Tracy's
right arm sort every loose shape into its matching hole -- the same narrative as
:mod:`experiments.montessori.franka_montessori_demo`'s Panda-driven original, ported to
:class:`~semantic_digital_twin.robots.tracy.Tracy`'s dual-UR10-arm,
Robotiq-85-gripper body (see :mod:`~experiments.montessori.tracy_equipment` and
:mod:`~experiments.montessori.tracy_world` for what had to change to fit it: a real ROS
description instead of a borrowed MJCF, and a scene built on Tracy's own table instead of
a table this package builds).

Run with (the ``experiments`` package must be importable, and ``iai_tracy_description``
must be built and sourced)::

    python -m experiments.montessori.tracy_montessori_demo
    python -m experiments.montessori.tracy_montessori_demo --viewer
    python -m experiments.montessori.tracy_montessori_demo --iterations 100

Every run's per-shape results are recorded, one :class:`~experiments.montessori.sorting_results.SortingIterationResult` (with
its :class:`~experiments.montessori.sorting_results.ShapeInsertionResult` rows) per iteration, to a local SQLite database via
ORMatic; see ``--database-uri`` and :data:`DEFAULT_DATABASE_URI`.

.. warning::
    Unlike :mod:`~experiments.montessori.franka_montessori_demo`, no MuJoCo-tuned
    reference exists for Tracy anywhere in this repository yet (see
    :mod:`~experiments.montessori.tracy_equipment`'s own docstring); this demo's
    servo gains and grasp geometry are a first, deliberately simple pass, expected to
    need the same kind of empirical iteration the Panda's own constants document going
    through.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import threading
import time
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from typing_extensions import Optional

from experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_shape_monitor,
)
from experiments.montessori.franka_panda_equipment import (
    BOARD_FRICTION,
    apply_contact_friction,
    apply_montessori_grasp_contact_parameters,
)
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    NoMatchingHoleError,
)
from experiments.montessori.sorting_results import (
    InsertionOutcome,
    ShapeInsertionResult,
    SortingIterationResult,
)
from experiments.montessori.tracy_equipment import (
    equip_tracy_for_physical_simulation,
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.montessori.tracy_world import TracyMontessoriWorld
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.utils import rclpy_installed

if TYPE_CHECKING:
    # coraplex.datastructures.dataclasses and the ROS adapters below all pull in
    # rclpy at module level (see main), so these are only ever imported for type
    # hints, never at runtime.
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )
    from experiments.montessori.insert_shape_action import InsertMontessoriShapeAction

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URI = "sqlite:///tracy_montessori_sorting_results.db"
"""
Database URI used when neither ``--database-uri`` nor
``TRACY_MONTESSORI_SORTING_DATABASE_URI`` is given: a local SQLite file in the current
directory, matching :data:`~experiments.montessori.franka_montessori_demo.DEFAULT_DATABASE_URI`'s
own pattern.
"""

NODE_NAME = "tracy_montessori_demo"
"""
Name of the ROS 2 node this demo's visualization runs against.
"""

TRACY_MOUNT_X = 0.0
TRACY_MOUNT_Y = 0.0
"""
Where Tracy's own root ("table") is bolted, in the scene's root frame; ``0, 0`` keeps
the same origin ``coraplex_tracy_stacking_mujoco``'s own proven-reachable coordinates
(reused by :mod:`~experiments.montessori.tracy_world` for the board and loose-shape row)
were measured against.
"""

MUJOCO_STEP_SIZE = 2e-4
"""
Physics step size, matching :data:`~experiments.montessori.montessori_demo.MUJOCO_STEP_SIZE`:
Tracy is driven by the same kind of generic, unclamped position-hold actuator as the HSR
there (see :mod:`~experiments.montessori.tracy_equipment`), not the Panda's own tuned,
clamped servo (which needed a finer step; see
:data:`~experiments.montessori.franka_montessori_demo.MUJOCO_STEP_SIZE`).
"""

SYNC_RATE_HZ = 100
"""
Rate at which the physically simulated joints' real, physics-driven positions are read
back into the world model; matches :data:`~experiments.montessori.franka_montessori_demo.SYNC_RATE_HZ`'s
own reasoning.
"""

SKIPPED_SHAPE_CATEGORIES = frozenset({MontessoriShapeCategory.DISK})
"""
Shape categories this demo leaves where they are, matching
:data:`~experiments.montessori.franka_montessori_demo.SKIPPED_SHAPE_CATEGORIES`: the disk
is not sorted in either demo.
"""

MAX_INSERTION_ATTEMPTS = 3
"""
Number of times a single shape's insertion is repeated while the attempt never gets as
far as releasing the shape, before giving up on it and logging a warning.
"""

SHAPE_SETTLE_DURATION = 2.0
"""
Real-time seconds a just-released shape is given to physically fall and come to rest
before it is checked whether it made it through its hole.
"""

MINIMUM_PICKUP_DISPLACEMENT = 0.03
"""
Minimum distance (in meters) a shape must have moved between just before its
:class:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction` starts
and right after it finishes, for the pickup to be considered real; see
:data:`~experiments.montessori.franka_montessori_demo.MINIMUM_PICKUP_DISPLACEMENT`'s own
reasoning, which applies unchanged here.
"""


def _build_insert_action(
    shape: MontessoriShape,
    montessori: TracyMontessoriWorld,
    target_horizontal_offset: Optional[Point3] = None,
) -> InsertMontessoriShapeAction:
    """
    Build (without executing) the plan that inserts ``shape`` into its matching hole with
    Tracy's right arm.

    :param shape: The shape to insert; must have a matching hole.
    :param montessori: The Montessori scene, with Tracy already mounted and equipped
        (see :func:`~experiments.montessori.tracy_equipment.equip_tracy_for_physical_simulation`),
        inside a running simulation.
    :param target_horizontal_offset: Horizontal offset to release the shape at; the
        hole's exact center is used if not given.
    """
    from coraplex.datastructures.enums import ApproachDirection, Arms, VerticalAlignment
    from coraplex.datastructures.grasp import GraspDescription
    from coraplex.view_manager import ViewManager
    from experiments.montessori.insert_shape_action import InsertMontessoriShapeAction

    offset = target_horizontal_offset or Point3(0.0, 0.0, 0.0)
    return InsertMontessoriShapeAction(
        montessori_shape=shape,
        board=montessori.board,
        arm=Arms.RIGHT,
        # rotate_gripper left at its default (False): the Panda's own wrist needed it
        # (see franka_montessori_demo._build_insert_action's own comment) because of that
        # arm's particular top-down grasp resolution; Tracy's UR10 wrist and Robotiq-85
        # gripper geometry differ, and there is no observation yet that it needs the same
        # workaround.
        grasp_description=GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.TOP,
            ViewManager.get_end_effector_view(Arms.RIGHT, montessori.robot),
        ),
        target_horizontal_offset=offset,
    )


def _insert_shape(
    action: InsertMontessoriShapeAction,
    montessori: TracyMontessoriWorld,
    context,
) -> bool:
    """
    Run ``action``, then let the shape physically settle under gravity and contacts
    before checking whether it made it through.

    Mirrors :func:`~experiments.montessori.franka_montessori_demo._insert_shape`; see its
    own docstring for why collision avoidance is off and why ``is_body_gripped`` cannot
    be checked directly after pickup instead of :data:`MINIMUM_PICKUP_DISPLACEMENT`.

    :param action: The insertion plan to run, built by :func:`_build_insert_action`.
    :param montessori: The Montessori scene, with Tracy already mounted and equipped,
        inside a running simulation.
    :param context: The CRAM execution context to run the insertion action in.
    :raises BodyUnfetchable: If the shape moved less than :data:`MINIMUM_PICKUP_DISPLACEMENT`
        over the whole insertion, i.e. the grasp silently failed to pick it up at all.
    :return: Whether the shape actually fell through its hole after settling.
    """
    from coraplex.datastructures.enums import ExecutionType
    from coraplex.execution_environment import ExecutionEnvironment
    from coraplex.plans.factories import execute_single
    from coraplex.plans.failures import BodyUnfetchable

    shape = action.montessori_shape
    spawn_position = shape.root.global_transform.to_position()
    with ExecutionEnvironment(
        execution_type=ExecutionType.SIMULATED,
        collision_avoidance=False,
        real_time_pacing=False,
        max_ticks_per_motion_mapping=300,
    ):
        node = execute_single(action, context=context)
        node.perform()

    montessori.world.update_forward_kinematics()
    release_position = shape.root.global_transform.to_position()
    displacement = math.dist(
        (float(spawn_position.x), float(spawn_position.y), float(spawn_position.z)),
        (
            float(release_position.x),
            float(release_position.y),
            float(release_position.z),
        ),
    )
    if displacement < MINIMUM_PICKUP_DISPLACEMENT:
        raise BodyUnfetchable(body=shape.root, arm=action.arm)

    logger.info("Letting %s settle.", shape.name)
    time.sleep(SHAPE_SETTLE_DURATION)
    montessori.world.update_forward_kinematics()

    return action.has_fallen_through_hole()


def _insert_shape_or_none(
    shape: MontessoriShape,
    montessori: TracyMontessoriWorld,
    context,
    attempt: int,
) -> tuple[Optional[bool], InsertMontessoriShapeAction]:
    """
    Attempt one insertion via :func:`_insert_shape`, returning ``None`` instead of
    letting a retryable failure propagate; mirrors
    :func:`~experiments.montessori.franka_montessori_demo._insert_shape_or_none`.

    :param shape: The shape to insert; must have a matching hole.
    :param montessori: The Montessori scene, with Tracy already mounted and equipped,
        inside a running simulation.
    :param context: The CRAM execution context to run the insertion action in.
    :param attempt: This attempt's 1-based index, used only for the log message.
    :return: Whether the shape fell through its hole (``None`` if this attempt failed
        in a retryable way), and the plan this attempt ran, for the caller to record
        regardless of outcome.
    """
    from coraplex.plans.failures import PlanFailure
    from giskardpy.motion_statechart.exceptions import CollisionViolatedError
    from giskardpy.qp.exceptions import QPSolverException
    from semantic_digital_twin.exceptions import PointOccupiedError

    action = _build_insert_action(shape, montessori)
    try:
        return _insert_shape(action, montessori, context), action
    except (
        PointOccupiedError,
        PlanFailure,
        CollisionViolatedError,
        QPSolverException,
    ) as error:
        logger.warning(
            "%s's insertion attempt %d/%d failed (%s); retrying.",
            shape.name,
            attempt,
            MAX_INSERTION_ATTEMPTS,
            error,
        )
        return None, action


def _log_segmind_verdict(
    shape: MontessoriShape, ground_truth_fell_through: Optional[bool], monitor: MontessoriEventMonitor
) -> None:
    """
    Log segmind's own pick-up/insertion verdict for ``shape`` next to the ground truth,
    matching :func:`~experiments.montessori.franka_montessori_demo._log_segmind_verdict`.
    """
    events = monitor.events
    pick_up_detected = any(
        isinstance(event, PickUpEvent) and event.tracked_object is shape.root
        for event in events
    )
    insertion_detected = any(
        isinstance(event, InsertionEvent) and event.tracked_object is shape.root
        for event in events
    )
    logger.info(
        "segmind for %s: pick-up detected=%s, insertion detected=%s "
        "(ground truth fell_through=%s).",
        shape.name,
        pick_up_detected,
        insertion_detected,
        ground_truth_fell_through,
    )


def _insert_all_shapes(
    montessori: TracyMontessoriWorld,
    context,
    max_shapes: Optional[int] = None,
    only_shape: Optional[str] = None,
) -> list[ShapeInsertionResult]:
    """
    Have Tracy's right arm pick up and insert every loose shape that has a matching hole
    into the shape-sorting board; mirrors
    :func:`~experiments.montessori.franka_montessori_demo._insert_all_shapes`.

    :param montessori: The Montessori scene, with Tracy already mounted and equipped,
        inside a running simulation.
    :param context: The CRAM execution context to run every insertion action in.
    :param max_shapes: Stop after this many shapes have actually been attempted.
    :param only_shape: Attempt only the shape whose name (with the trailing ``_shape``
        removed) equals this.
    :return: One :class:`~experiments.montessori.sorting_results.ShapeInsertionResult` per
        actually attempted shape, in attempt order.
    """
    results: list[ShapeInsertionResult] = []
    attempted = 0
    for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape):
        if shape.shape_category in SKIPPED_SHAPE_CATEGORIES:
            logger.info(
                "Skipping %s: %s is not sorted.", shape.name, shape.shape_category
            )
            continue

        try:
            montessori.board.hole_for(shape)
        except NoMatchingHoleError:
            logger.info("Skipping %s: no matching hole.", shape.name)
            continue

        shape_key = shape.name.name.removesuffix("_shape")
        if only_shape is not None and shape_key != only_shape:
            logger.info("Skipping %s: not %s.", shape.name, only_shape)
            continue

        if max_shapes is not None and attempted >= max_shapes:
            logger.info("Reached max_shapes=%d; stopping.", max_shapes)
            break
        attempted += 1

        event_monitor = build_shape_monitor(montessori, shape)
        event_monitor.start()

        fell_through = None
        for attempt in range(1, MAX_INSERTION_ATTEMPTS + 1):
            logger.info(
                "Inserting %s into its matching hole (attempt %d/%d).",
                shape.name,
                attempt,
                MAX_INSERTION_ATTEMPTS,
            )
            fell_through, action = _insert_shape_or_none(
                shape, montessori, context, attempt
            )
            if fell_through is not None:
                break

        event_monitor.stop()
        _log_segmind_verdict(shape, fell_through, event_monitor)

        if fell_through is None:
            logger.warning(
                "%s could not be inserted in %d attempts; moving on to the next shape.",
                shape.name,
                MAX_INSERTION_ATTEMPTS,
            )
            outcome = InsertionOutcome.ATTEMPTS_EXHAUSTED
        elif not fell_through:
            logger.warning(
                "%s did not fall through its hole; it may be resting on the board or "
                "wedged in the opening. Moving on to the next shape.",
                shape.name,
            )
            outcome = InsertionOutcome.DID_NOT_FALL_THROUGH
        else:
            outcome = InsertionOutcome.FELL_THROUGH
        results.append(
            ShapeInsertionResult(shape_key=shape_key, outcome=outcome, plan=action.plan)
        )

    return results


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments selecting whether a MuJoCo viewer window is opened and
    how many shapes to attempt; mirrors
    :func:`~experiments.montessori.franka_montessori_demo._parse_arguments` minus
    ``--world2`` (this demo has only the one, Tracy-table-based layout; see
    :mod:`~experiments.montessori.tracy_world`).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Open a MuJoCo viewer window; off by default so the demo runs headless.",
    )
    parser.add_argument(
        "--max-shapes",
        type=int,
        default=None,
        help=(
            "Stop after this many shapes have been attempted, for fast iteration "
            "while tuning parameters on a single shape. Attempts every shape by "
            "default."
        ),
    )
    parser.add_argument(
        "--only-shape",
        type=str,
        default=None,
        help=(
            "Attempt only the shape with this name (trailing '_shape' removed, e.g. "
            "'square_hole'), skipping every other shape while still spawning them, for "
            "isolating one shape's own tuning. Attempts every shape by default."
        ),
    )
    parser.add_argument(
        "--no-rviz",
        action="store_true",
        help="Don't publish TF/visualization markers to RViz; publishes by default.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help=(
            "Repeat the whole build-world-and-sort cycle this many times, rebuilding "
            "the world and its simulation fresh each time, then log a per-shape "
            "success-rate summary and exit instead of idling. Runs once and keeps the "
            "simulation running afterwards (the original behavior) by default."
        ),
    )
    parser.add_argument(
        "--exit-after-sorting",
        action="store_true",
        help=(
            "Exit as soon as sorting finishes instead of idling afterwards, even with "
            "--iterations 1. Useful for scripted/batched single-iteration runs (e.g. "
            "under an external timeout) that have no --viewer to inspect; idles by "
            "default so a single-iteration run stays inspectable."
        ),
    )
    parser.add_argument(
        "--database-uri",
        default=os.getenv(
            "TRACY_MONTESSORI_SORTING_DATABASE_URI", DEFAULT_DATABASE_URI
        ),
        help=(
            "Database URI every iteration's SortingIterationResult (with its "
            "per-shape ShapeInsertionResult rows) is recorded to via ORMatic, one "
            "commit per iteration. Defaults to a local SQLite file (see "
            "DEFAULT_DATABASE_URI), overridable via TRACY_MONTESSORI_SORTING_DATABASE_URI."
        ),
    )
    return parser.parse_args()


def _build_world_and_sort(
    node, arguments: argparse.Namespace
) -> tuple[
    list[ShapeInsertionResult],
    MujocoSim,
    Optional[TFPublisher],
    Optional[VizMarkerPublisher],
]:
    """
    Build a fresh Montessori world on Tracy's own table, mount and equip Tracy, start its
    physics simulation, and have its right arm sort every loose shape into the board
    once; mirrors :func:`~experiments.montessori.franka_montessori_demo._build_world_and_sort`.

    :param node: The ROS 2 node TF/marker publishing runs against.
    :param arguments: Parsed command-line arguments selecting the viewer, RViz
        publishing, and shape-attempt limits.
    :return: This run's per-shape results (see :func:`_insert_all_shapes`), and the live
        simulation and publishers, left running for the caller to stop once it is done
        with them.
    """
    from coraplex.datastructures.dataclasses import Context
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )

    tracy_world = parse_tracy()
    mount_position, table_top_z = tracy_table_mount_position(
        tracy_world, x=TRACY_MOUNT_X, y=TRACY_MOUNT_Y
    )
    montessori = TracyMontessoriWorld(shapes_are_movable=True, table_top_z=table_top_z)
    robot = montessori.mount_stationary_robot(
        Tracy, tracy_world, mount_position, mount_yaw=0.0
    )
    physically_simulated_dofs = equip_tracy_for_physical_simulation(robot)
    apply_montessori_grasp_contact_parameters(
        montessori.world.get_semantic_annotations_by_type(MontessoriShape)
    )
    apply_contact_friction([montessori.board.root], BOARD_FRICTION)
    logger.info("Built Montessori world with %d bodies.", len(montessori.world.bodies))

    tf_publisher = None
    viz_marker_publisher = None
    if not arguments.no_rviz:
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
        real_time_factor=1.0,
        physically_simulated_dofs=physically_simulated_dofs,
        sync_rate_hz=SYNC_RATE_HZ,
    )
    context = Context(
        montessori.world,
        robot,
        ros_node=node,
        update_world_model_attachment=False,
        evaluate_conditions=False,
    )
    context.simulation_clock = lambda: multi_sim.simulator.current_simulation_time

    multi_sim.start_simulation()
    results = _insert_all_shapes(
        montessori,
        context,
        max_shapes=arguments.max_shapes,
        only_shape=arguments.only_shape,
    )
    return results, multi_sim, tf_publisher, viz_marker_publisher


def _log_iteration_summary(iteration_results: list[SortingIterationResult]) -> None:
    """
    Log a per-shape success-rate summary across every :class:`~experiments.montessori.sorting_results.SortingIterationResult`
    :func:`main` collected; mirrors
    :func:`~experiments.montessori.franka_montessori_demo._log_iteration_summary`.

    :param iteration_results: One entry per iteration :func:`main` ran.
    """
    tallies: dict[str, Counter[InsertionOutcome]] = defaultdict(Counter)
    for iteration_result in iteration_results:
        for shape_result in iteration_result.shape_results:
            tallies[shape_result.shape_key][shape_result.outcome] += 1

    logger.info("=== Summary across %d iteration(s) ===", len(iteration_results))
    total_fell_through = 0
    total_attempted = 0
    for shape_key in sorted(tallies):
        tally = tallies[shape_key]
        attempted = sum(tally.values())
        fell_through = tally[InsertionOutcome.FELL_THROUGH]
        total_fell_through += fell_through
        total_attempted += attempted
        logger.info(
            "%s: %d/%d fell through (%d did not, %d exhausted attempts).",
            shape_key,
            fell_through,
            attempted,
            tally[InsertionOutcome.DID_NOT_FALL_THROUGH],
            tally[InsertionOutcome.ATTEMPTS_EXHAUSTED],
        )

    if total_attempted:
        logger.info(
            "Overall: %d/%d (%.1f%%) fell through across %d iteration(s).",
            total_fell_through,
            total_attempted,
            100.0 * total_fell_through / total_attempted,
            len(iteration_results),
        )


def main() -> None:
    """
    Build the Montessori world on Tracy's own table, bolt Tracy there, visualize it in
    RViz, and have its right arm sort the loose shapes into the board; mirrors
    :func:`~experiments.montessori.franka_montessori_demo.main`.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    arguments = _parse_arguments()

    if not rclpy_installed():
        logger.error("rclpy is not installed; this needs the CRAM/Giskard stack.")
        return

    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    if not rclpy.ok():
        rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    spinner.start()

    keep_simulation_running = (
        arguments.iterations == 1 and not arguments.exit_after_sorting
    )
    iteration_results: list[SortingIterationResult] = []
    multi_sim = None
    tf_publisher = None
    viz_marker_publisher = None
    logger.info("Recording results to '%s'.", arguments.database_uri)
    try:
        for iteration in range(1, arguments.iterations + 1):
            if arguments.iterations > 1:
                logger.info(
                    "=== Starting iteration %d/%d ===", iteration, arguments.iterations
                )
            shape_results, multi_sim, tf_publisher, viz_marker_publisher = (
                _build_world_and_sort(node, arguments)
            )
            iteration_result = SortingIterationResult(
                iteration=iteration, shape_results=shape_results
            )
            iteration_results.append(iteration_result)

            if keep_simulation_running:
                break

            multi_sim.stop_simulation()
            if viz_marker_publisher is not None:
                viz_marker_publisher.stop()
            if tf_publisher is not None:
                tf_publisher.stop()
            multi_sim = tf_publisher = viz_marker_publisher = None

        if keep_simulation_running:
            logger.info("Sorting done; the simulation keeps running.")
            logger.info("Done. Press Ctrl+C to stop.")
            while True:
                time.sleep(0.1)
        else:
            _log_iteration_summary(iteration_results)
    except KeyboardInterrupt:
        pass
    finally:
        if multi_sim is not None:
            multi_sim.stop_simulation()
        if viz_marker_publisher is not None:
            viz_marker_publisher.stop()
        if tf_publisher is not None:
            tf_publisher.stop()
        executor.shutdown()
        spinner.join(timeout=2.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
