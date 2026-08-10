import numpy as np
from giskardpy.motion_statechart.context import MotionStatechartContext

from experiments.montessori.event_monitoring import build_shape_monitor
from experiments.montessori.semantics import MontessoriShape, ShapeSortingHole
from experiments.montessori.world import MontessoriWorld, TABLE_POSITION, TABLE_SCALE
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from segmind.detectors.base import SegmindContext
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix


def _shape_and_hole(montessori: MontessoriWorld, key: str):
    shape = next(
        s
        for s in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if s.name.name == f"{key}_shape"
    )
    hole = next(
        h
        for h in montessori.world.get_semantic_annotations_by_type(ShapeSortingHole)
        if h.name.name == key
    )
    return shape, hole


def test_detect_holes_returns_every_shape_sorting_hole_not_the_loose_shapes():
    montessori = MontessoriWorld(shapes_are_movable=True)
    context = MotionStatechartContext(world=montessori.world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = context.require_extension(SegmindContext)

    executor.detect_holes()

    assert set(segmind_context.holes) == set(
        montessori.world.get_semantic_annotations_by_type(ShapeSortingHole)
    )


def test_shape_falling_through_its_hole_is_detected_as_pick_up_and_insertion():
    """
    Moves the square hole's cube shape off the table, over its hole, and down through
    it to rest, ticking a :class:`MontessoriEventMonitor` by hand throughout (rather
    than starting its background thread) for a fully deterministic sequence of events.
    """
    montessori = MontessoriWorld(shapes_are_movable=True)
    shape, hole = _shape_and_hole(montessori, "square_hole")
    monitor = build_shape_monitor(montessori, shape)

    table_top_z = float(TABLE_POSITION.z) + TABLE_SCALE.z / 2
    resting_low_z = shape.root.collision.combined_mesh.bounds[0][2]
    start_position = shape.root.global_transform.to_position()
    hole_position = hole.root.global_transform.to_position()

    def move_to(x: float, y: float, z: float) -> None:
        shape.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x, y, z)
        monitor.tick()

    # Settle on the table first, so there is a real SupportEvent(table) to be lost.
    for _ in range(5):
        monitor.tick()

    # Lift the shape off the table and carry it to hover above the hole.
    for t in np.linspace(0.0, 1.0, 6):
        move_to(
            float(start_position.x) + t * (float(hole_position.x) - float(start_position.x)),
            float(start_position.y) + t * (float(hole_position.y) - float(start_position.y)),
            float(start_position.z) + t * (float(hole_position.z) + 0.05 - float(start_position.z)),
        )

    # Lower it through the hole down to its resting position on the table.
    for z in np.linspace(float(hole_position.z) + 0.05, table_top_z - resting_low_z, 10):
        move_to(float(hole_position.x), float(hole_position.y), float(z))

    # Let StopTranslationDetector's pose window (see MotionDetector.window_size)
    # register the shape as stationary again.
    for _ in range(8):
        monitor.tick()

    pick_up_events = [
        event for event in monitor.events
        if isinstance(event, PickUpEvent) and event.tracked_object is shape.root
    ]
    insertion_events = [
        event for event in monitor.events
        if isinstance(event, InsertionEvent) and event.tracked_object is shape.root
    ]

    assert len(pick_up_events) == 1
    assert len(insertion_events) == 1
    assert insertion_events[0].through_hole is hole
