"""
Build the Montessori shape-sorting world and have a table-mounted Franka Emika Panda
sort every loose shape into its matching hole -- the same narrative as
:mod:`experiments.montessori.montessori_demo`'s HSRB-driven original, but reaching with
its arm alone (see
:meth:`~experiments.montessori.world.MontessoriWorld.mount_stationary_robot`; the Panda
has no mobile base to navigate) and holding each shape by the gripper's own contact
friction throughout the whole run, rather than kinematically teleporting it and settling
it afterwards (see :mod:`experiments.montessori.franka_panda_equipment`).

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.franka_montessori_demo
    python -m experiments.montessori.franka_montessori_demo --viewer
    python -m experiments.montessori.franka_montessori_demo --iterations 100

Every run's per-shape results are recorded, one :class:`~experiments.montessori.sorting_results.SortingIterationResult` (with
its :class:`~experiments.montessori.sorting_results.ShapeInsertionResult` rows) per iteration, to a local SQLite database via
ORMatic; see ``--database-uri`` and :data:`DEFAULT_DATABASE_URI`.

.. note::
    :class:`~experiments.montessori.sorting_results.ShapeInsertionResult` and :class:`~experiments.montessori.sorting_results.SortingIterationResult` must be included
    in ``experiments.orm.ormatic_interface`` before a run can persist anything;
    regenerate it with ``python scripts/regenerate_all_orm.py`` (from the repository
    root, in an environment with ROS 2 installed) if they are not already there.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import logging
import math
import os
import threading
import time
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

import mujoco
import numpy as np
from krrood.ormatic.data_access_objects.helper import to_dao
from krrood.ormatic.utils import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typing_extensions import Optional

from experiments.montessori.event_monitoring import (
    MontessoriEventMonitor,
    build_shape_monitor,
)
from experiments.montessori.franka_panda_equipment import (
    BOARD_FRICTION,
    apply_contact_friction,
    apply_montessori_grasp_contact_parameters,
    equip_panda_for_physical_simulation,
    parse_panda,
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
from experiments.montessori.world import MontessoriWorld
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from semantic_digital_twin.robots.panda import Panda
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

DEFAULT_DATABASE_URI = "sqlite:///franka_montessori_sorting_results.db"
"""
Database URI used when neither ``--database-uri`` nor
``FRANKA_MONTESSORI_SORTING_DATABASE_URI`` is given: a local SQLite file in the current
directory, matching :mod:`experiments.montessori.generate_insertion_experience`'s own
default.
"""

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

MUJOCO_INTEGRATOR = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
"""
Numerical integrator MuJoCo advances the physics with, matching
``coraplex_panda_demo/stacking_scene.xml``'s own ``<option integrator="implicitfast"
/>`` (:class:`~physics_simulators.mujoco_simulator.MujocoSimulator` otherwise falls back
to its own ``RK4`` default regardless of what a scene declares).

RK4's four force evaluations per step measured about four times slower here than
``implicitfast``, with no observed difference in insertion outcomes.
"""

SYNC_RATE_HZ = 100
"""
Rate at which the physically simulated joints' real, physics-driven positions are read
back into the world model.

Kept above the 50 Hz control loop rate (see :attr:`~coraplex.plans.executables.GiskardExecutable._build_pacer`'s
``target_frequency``): lowering it to 30 Hz was tried for the extra Python-side sync
overhead it saves, but produced an unreliable/wedged grasp and, once, a run that never
converged -- the controller needs joint state read back at least as often as it commands.
"""

SKIPPED_SHAPE_CATEGORIES = frozenset({MontessoriShapeCategory.DISK})
"""
Shape categories the demo leaves where they are.

Checked before anything else about a shape, so a listed category is passed over even
where the board has a matching hole for it.
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

The simulation keeps running throughout (see :mod:`~experiments.montessori.franka_panda_equipment`);
this is a settling wait, not a separate physics pass.
"""

MINIMUM_PICKUP_DISPLACEMENT = 0.03
"""
Minimum distance (in meters) a shape must have moved between just before its
:class:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction` starts
and right after it finishes, for the pickup to be considered real (see
:func:`_insert_shape`).

A grasp that silently fails to actually close on the shape (rather than raising) has
been observed to let the rest of the action run to completion anyway, with the shape
left exactly where it started the whole time -- indistinguishable, without this check,
from a shape that really was picked up, carried to the hole, and simply didn't fall
through. A real pickup lifts the shape and carries it toward the hole, decimeters away,
so this threshold only needs to rule out the shape having simply not moved at all.
"""

TCP_POSITION_THRESHOLD = 0.007
"""
Position tolerance in meters used for every
:class:`~coraplex.robot_plans.motions.gripper.MoveToolCenterPointMotion` in this demo
(see :attr:`~coraplex.datastructures.dataclasses.MotionToleranceConfig.default_tcp_posit
ion_threshold`), in place of Giskard's own tighter default (0.005m).

A physically simulated, PD-tracked arm settles with some residual error rather than
converging exactly onto a goal; the tight default was observed to have the arm hover and
make small corrections near the placing pose for a long time before the goal finally
registered as reached, rather than actually improving placement accuracy. 0.01 cut that
hovering down, but also let one release land far enough off to miss and tumble a shape
that had never missed before; splitting the difference between the two.
"""

TCP_ORIENTATION_THRESHOLD = 0.03
"""
Orientation tolerance in rad used for every
:class:`~coraplex.robot_plans.motions.gripper.MoveToolCenterPointMotion` in this demo
(see :attr:`~coraplex.datastructures.dataclasses.MotionToleranceConfig.tool_orientation_
threshold`), loosened for the same reason as :data:`TCP_POSITION_THRESHOLD`.
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


def _build_insert_action(
    shape: MontessoriShape,
    montessori: MontessoriWorld,
    target_horizontal_offset: Optional[Point3] = None,
) -> InsertMontessoriShapeAction:
    """
    Build (without executing) the plan that inserts ``shape`` into its matching hole.

    Built once per attempt, before :func:`_insert_shape` runs it, so a caller keeps a
    reference to the attempted plan even if that run raises (see
    :func:`_insert_shape_or_none`).

    :param shape: The shape to insert; must have a matching hole.
    :param montessori: The Montessori scene, with the Panda already mounted and
        equipped (see :func:`~experiments.montessori.franka_panda_equipment.equip_panda_for_physical_simulation`),
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


def _insert_shape(
    action: InsertMontessoriShapeAction,
    montessori: MontessoriWorld,
    context,
) -> bool:
    """
    Run ``action``, then let the shape physically settle under gravity and contacts
    before checking whether it made it through.

    Runs with Giskard's collision avoidance off, matching
    :func:`~experiments.montessori.montessori_demo._insert_shape`'s own reasoning for
    the HSRB: the board's CoACD collision decomposition gives the QP solver far more
    simultaneous distance constraints than this pick-and-place needs.

    :param action: The insertion plan to run, built by :func:`_build_insert_action`.
    :param montessori: The Montessori scene, with the Panda already mounted and
        equipped (see :func:`~experiments.montessori.franka_panda_equipment.equip_panda_for_physical_simulation`),
        inside a running simulation.
    :param context: The CRAM execution context to run the insertion action in.
    :raises BodyUnfetchable: If the shape moved less than :data:`MINIMUM_PICKUP_DISPLACEMENT`
        over the whole insertion, i.e. the grasp silently failed to pick it up at all.

        ``is_body_gripped`` can't be checked directly after pickup instead: doing so needs
        either a real mid-plan checkpoint (``CodeNode`` doesn't work -- its callback fires
        during plan *construction*, not at its position in real execution order) or
        splitting the pickup and place halves into two separate ``execute_single`` calls,
        which breaks :class:`~coraplex.robot_plans.actions.core.placing.PlaceAction`'s own
        lookup of the grasp it should place with -- resolved via
        ``plan_node.get_previous_node_by_designator_type(PickUpAction)`` within a single
        plan graph, so a fresh, separate plan for the place half never finds it, silently
        falling back to a generic (not our real top-down) grasp. Checking ``evaluate_conditions=True``
        (making :attr:`~coraplex.robot_plans.actions.core.placing.PlaceAction.pre_condition`,
        which already does this ``is_body_gripped`` check, run) was tried too, but that
        re-enables ``ReachAction``/``PickUpAction``'s ``IsObjectReachableBy`` precondition
        along with it, which hung for 5+ minutes on the very first pickup.
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
        # A full insertion (pick, place, three ParkArms) was observed to need
        # roughly 1250 ticks total across its 12 motion mappings; this budget stays
        # a comfortable multiple of that per mapping while bounding a stuck motion
        # to a fraction of the default (2000 * 12 ticks).
        max_ticks_per_motion_mapping=300,
    ):
        node = execute_single(action, context=context)
        # Temporary diagnostic: simulated-time span of the whole pick+place action, as
        # a proxy for how much the arm hovers/corrects near its Cartesian goals rather
        # than converging directly onto them.
        insertion_start_time = context.simulation_clock()
        node.perform()
        insertion_duration = context.simulation_clock() - insertion_start_time
        logger.info(
            "%s insertion action took %.3fs of simulated time.",
            shape.name,
            insertion_duration,
        )

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

    # Temporary diagnostic: where the shape actually is right after physical
    # release, before settling has a chance to slide/tip it further.
    hole = montessori.board.hole_for(shape)
    hole_position = hole.root.global_transform.to_position()
    release_position = shape.root.global_transform.to_position()
    logger.info(
        "%s released at (%.4f, %.4f, %.4f); hole center at (%.4f, %.4f, %.4f).",
        shape.name,
        float(release_position.x),
        float(release_position.y),
        float(release_position.z),
        float(hole_position.x),
        float(hole_position.y),
        float(hole_position.z),
    )

    logger.info("Letting %s settle.", shape.name)
    # Temporary diagnostic: sample position through the settle window instead of
    # only before/after, to tell a real physics freeze apart from a stale
    # world-model/visualization read.
    sample_count = 10
    sample_interval = SHAPE_SETTLE_DURATION / sample_count
    for sample_index in range(sample_count):
        time.sleep(sample_interval)
        montessori.world.update_forward_kinematics()
        sample_position = shape.root.global_transform.to_position()
        logger.info(
            "%s settle sample %d/%d: (%.4f, %.4f, %.4f)",
            shape.name,
            sample_index + 1,
            sample_count,
            float(sample_position.x),
            float(sample_position.y),
            float(sample_position.z),
        )

    return action.has_fallen_through_hole()


def _insert_shape_or_none(
    shape: MontessoriShape,
    montessori: MontessoriWorld,
    context,
    attempt: int,
) -> tuple[Optional[bool], InsertMontessoriShapeAction]:
    """
    Attempt one insertion via :func:`_insert_shape`, returning ``None`` instead of
    letting a retryable failure propagate.

    :param shape: The shape to insert; must have a matching hole.
    :param montessori: The Montessori scene, with the Panda already mounted and
        equipped, inside a running simulation.
    :param context: The CRAM execution context to run the insertion action in.
    :param attempt: This attempt's 1-based index, used only for the log message.
    :return: Whether the shape fell through its hole (``None`` if this attempt failed in
        a retryable way), and the plan this attempt ran, for the caller to record
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
    Log segmind's own pick-up/insertion verdict for ``shape`` next to the ground truth
    :meth:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction.has_fallen_through_hole`
    already computed for it, for comparison while segmind's detectors are still new to
    this scene.

    :param shape: The shape ``monitor`` was tracking.
    :param ground_truth_fell_through: What :func:`_insert_shape` determined by direct
        geometry, or ``None`` if the attempt never got far enough to check.
    :param monitor: The stopped event monitor that tracked ``shape``.
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
        "DEBUG segmind raw events for %s: %s",
        shape.name,
        [(type(e).__name__, getattr(e, "with_object", None), e.timestamp) for e in events],
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
    montessori: MontessoriWorld,
    context,
    max_shapes: Optional[int] = None,
    only_shape: Optional[str] = None,
) -> list[ShapeInsertionResult]:
    """
    Have the Panda pick up and insert every loose shape that has a matching hole into
    the shape-sorting board, skipping any that don't (e.g. the sphere) and any whose
    category is listed in :data:`SKIPPED_SHAPE_CATEGORIES`.

    Each shape gets one insertion, whether or not it actually drops through: a shape left
    resting on the board is reported and left there. Only an attempt that never ran --
    the grasp or the motion failed before the shape was released -- is repeated, up to
    :data:`MAX_INSERTION_ATTEMPTS` times, since it says nothing about the shape either
    way. Such a retry picks the shape up from wherever it physically ended up, which is
    not necessarily where it started.

    :param montessori: The Montessori scene, with the Panda already mounted and
        equipped, inside a running simulation.
    :param context: The CRAM execution context to run every insertion action in.
    :param max_shapes: Stop after this many shapes have actually been attempted
        (skipped shapes don't count), for fast iteration while tuning parameters on a
        single shape. ``None`` attempts every shape.
    :param only_shape: Attempt only the shape whose name (with the trailing ``_shape``
        removed, e.g. ``"square_hole"``) equals this, skipping every other shape. Every
        other shape still sits in the world (unlike a lower :attr:`max_shapes`, which
        never even reaches them), so the scene matches a full run; only the robot's
        insertion attempts are limited, for isolating one shape's own tuning without a
        full run's time cost.
    :return: One :class:`~experiments.montessori.sorting_results.ShapeInsertionResult` per actually attempted shape, in
        attempt order; a skipped shape has no entry.
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
    how many shapes to attempt.
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
        "--world2",
        action="store_true",
        help=(
            "Use experiments.montessori.world2's layout (board directly ahead of the "
            "robot, loose shapes on a separate stand to its side) instead of the "
            "default single-table layout."
        ),
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
        "--start-iteration",
        type=int,
        default=1,
        help=(
            "1-based index recorded on the first iteration's SortingIterationResult, "
            "counting up from there; only the recorded index is affected, not how "
            "many iterations actually run. Lets a caller that restarts this process "
            "every few iterations keep recorded iteration numbers globally unique "
            "and increasing across restarts instead of every restart re-numbering "
            "from 1."
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
            "FRANKA_MONTESSORI_SORTING_DATABASE_URI", DEFAULT_DATABASE_URI
        ),
        help=(
            "Database URI every iteration's SortingIterationResult (with its "
            "per-shape ShapeInsertionResult rows) is recorded to via ORMatic, one "
            "commit per iteration. Defaults to a local SQLite file (see "
            "DEFAULT_DATABASE_URI), overridable via FRANKA_MONTESSORI_SORTING_DATABASE_URI."
        ),
    )
    return parser.parse_args()


def _open_results_session(database_uri: str) -> Session:
    """
    Open a SQLAlchemy session against ``database_uri``, creating
    :class:`~experiments.montessori.sorting_results.SortingIterationResult` and
    :class:`~experiments.montessori.sorting_results.ShapeInsertionResult`'s tables first
    if they don't already exist.

    :param database_uri: Database to write recorded results to; see
        :data:`DEFAULT_DATABASE_URI`.
    """
    import experiments.orm.ormatic_interface as ormatic_interface

    engine = create_engine(database_uri)
    ormatic_interface.Base.metadata.create_all(engine)
    return sessionmaker(engine)()


def _build_world_and_sort(
    node, arguments: argparse.Namespace
) -> tuple[
    list[ShapeInsertionResult],
    MujocoSim,
    Optional[TFPublisher],
    Optional[VizMarkerPublisher],
]:
    """
    Build a fresh Montessori world, bolt and equip the Panda next to it, start its
    physics simulation, and have it sort every loose shape into the board once.

    :param node: The ROS 2 node TF/marker publishing runs against.
    :param arguments: Parsed command-line arguments selecting the world layout, viewer,
        RViz publishing, and shape-attempt limits.
    :return: This run's per-shape results (see :func:`_insert_all_shapes`), and the live
        simulation and publishers, left running for the caller to stop once it is done
        with them.
    """
    from coraplex.datastructures.dataclasses import Context, MotionToleranceConfig
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )

    if arguments.world2:
        from experiments.montessori.world2 import MontessoriWorld2, ROBOT_MOUNT_POSITION

        montessori = MontessoriWorld2(shapes_are_movable=True)
        mount_position = ROBOT_MOUNT_POSITION
    else:
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
        # None: run as fast as the CPU allows rather than throttled to wall-clock
        # real time, matching franka_pickup_smoke_test.py's own reasoning;
        # real_time_pacing paces against context.simulation_clock (set below to this
        # simulation's own clock) so the sorting still completes correctly. --viewer
        # stays real-time so the run is actually watchable.
        real_time_factor=None if not arguments.viewer else 1.0,
        physically_simulated_dofs=physically_simulated_dofs,
        sync_rate_hz=SYNC_RATE_HZ,
        integrator=MUJOCO_INTEGRATOR,
    )
    context = Context(
        montessori.world,
        robot,
        ros_node=node,
        update_world_model_attachment=False,
        # IsObjectReachableBy (PickUpAction/ReachAction's pre_condition) runs a full
        # simulated IK/collision-avoidance reach on a deep-copied world; re-enabling
        # evaluate_conditions to get PlaceAction's own gripped-check for free was tried,
        # but that check is still too unreliable even with the shapes' now-more-central
        # table row -- it hung for 5+ minutes on the very first pickup. Our own
        # is_body_gripped check in _insert_shape covers the same thing without it.
        evaluate_conditions=False,
        motion_tolerances=MotionToleranceConfig(
            default_tcp_position_threshold=TCP_POSITION_THRESHOLD,
            tool_orientation_threshold=TCP_ORIENTATION_THRESHOLD,
        ),
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


def _reclaim_native_heap_fragmentation() -> None:
    """
    Collect Python cycles, then ask glibc to release freed-but-unreturned heap back to
    the OS.

    Each rebuilt world's MuJoCo model/data and Bullet collision shapes (see
    :class:`~semantic_digital_twin.collision_checking.pybullet_collision_detector.BulletCollisionDetector`)
    free their native allocations correctly, but glibc's allocator keeps the
    resulting holes in its own arenas rather than returning them to the OS, so RSS
    climbs by ~150-230MB per iteration of a long ``--iterations`` run until the
    process is OOM-killed even though no Python object leaks. ``malloc_trim`` reclaims
    that fragmented-but-freed memory; ``gc.collect()`` runs first so any Python-level
    garbage is freed (and its native backing memory released) before trimming.
    """
    gc.collect()
    ctypes.CDLL(None).malloc_trim(0)


def _log_iteration_summary(iteration_results: list[SortingIterationResult]) -> None:
    """
    Log a per-shape success-rate summary across every
    :class:`~experiments.montessori.sorting_results.SortingIterationResult` :func:`main`
    collected, once its :attr:`~argparse.Namespace.iterations` finish.

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
    Build the Montessori world, bolt the Panda next to it, visualize it in RViz, and
    have it sort the loose shapes into the board.

    Runs once and keeps the live simulation running until interrupted by default; with
    :attr:`~argparse.Namespace.iterations` greater than one, or with
    :attr:`~argparse.Namespace.exit_after_sorting` set, instead exits as soon as
    sorting finishes (rebuilding the whole world and rerunning the sort between
    iterations, then logging a per-shape success-rate summary, if there is more than
    one). Every iteration's :class:`~experiments.montessori.sorting_results.SortingIterationResult` is recorded to
    :attr:`~argparse.Namespace.database_uri` as it finishes (see
    :func:`_open_results_session`), one commit per iteration, so a run interrupted
    partway through still leaves every completed iteration persisted.
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

    if not rclpy.ok():
        rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    spinner.start()

    # keep_simulation_running: matches the original single-run behavior of leaving the
    # simulation live for inspection (e.g. via --viewer) once sorting finishes, rather
    # than immediately tearing it down to rebuild for a next iteration; only sensible
    # when there is no next iteration to rebuild for, and skipped outright by
    # --exit-after-sorting for scripted single-iteration runs.
    keep_simulation_running = (
        arguments.iterations == 1 and not arguments.exit_after_sorting
    )
    iteration_results: list[SortingIterationResult] = []
    multi_sim = None
    tf_publisher = None
    viz_marker_publisher = None
#    results_session = _open_results_session(arguments.database_uri)
    logger.info("Recording results to '%s'.", arguments.database_uri)
    try:
        for iteration in range(
            arguments.start_iteration,
            arguments.start_iteration + arguments.iterations,
        ):
            if arguments.iterations > 1:
                logger.info(
                    "=== Starting iteration %d/%d ===",
                    iteration,
                    arguments.start_iteration + arguments.iterations - 1,
                )
            shape_results, multi_sim, tf_publisher, viz_marker_publisher = (
                _build_world_and_sort(node, arguments)
            )
            iteration_result = SortingIterationResult(
                iteration=iteration, shape_results=shape_results
            )
            iteration_results.append(iteration_result)
            #results_session.add(to_dao(iteration_result))
            #results_session.commit()

            if keep_simulation_running:
                break

            multi_sim.stop_simulation()
            if viz_marker_publisher is not None:
                viz_marker_publisher.stop()
            if tf_publisher is not None:
                tf_publisher.stop()
            multi_sim = tf_publisher = viz_marker_publisher = None
            _reclaim_native_heap_fragmentation()

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
        #results_session.close()
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
