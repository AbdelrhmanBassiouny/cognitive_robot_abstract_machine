import numpy as np
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.events import (
    ContactEvent,
    LossOfContactEvent,
    SupportEvent,
    LossOfSupportEvent,
    LossOfContainmentEvent,
    ContainmentEvent,
    InsertionEvent,
    TranslationEvent,
    StopTranslationEvent,
    PickUpEvent,
    PlacingEvent,
    RotationEvent,
    StopRotationEvent,
)
from segmind.detectors.atomic_event_detectors_nodes import RotationDetector, StopRotationDetector, ContactDetector, \
    LossOfContactDetector, TranslationDetector, StopTranslationDetector
from segmind.detectors.base import SegmindContext
from segmind.detectors.coarse_event_detector_nodes import PickUpDetector, PlacingDetector
from segmind.detectors.spatial_relation_detector_nodes import SupportDetector, LossOfSupportDetector, \
    ContainmentDetector, LossOfContainmentDetector, InsertionDetector
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from segmind.statecharts.segmind_statechart import SegmindStatechart
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_executor(world):
    context = MotionStatechartContext(world=world)
    milk = world.get_body_by_name("milk.stl")
    box1 = world.get_body_by_name("box")
    box2 = world.get_body_by_name("box_2")
    segmind_executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = segmind_executor.context.require_extension(SegmindContext)
    return segmind_executor, segmind_context, milk, box1, box2


def events_of(segmind_context, event_type):
    return [e for e in segmind_context.logger.get_events() if isinstance(e, event_type)]

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_contact_detector(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart([ContactDetector(),LossOfContactDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, ContactEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(z=1, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfContactEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(box1.global_pose.x, box1.global_pose.y, box1.global_pose.z, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContactEvent)) == 1
    assert len(events_of(segmind_context, LossOfContactEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(box2.global_pose.x, box2.global_pose.y, box2.global_pose.z, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContactEvent)) == 2
    assert len(events_of(segmind_context, LossOfContactEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(z=1, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfContactEvent)) == 2
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)

def test_support_detector(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart([SupportDetector(), LossOfSupportDetector()])
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 0.93, reference_frame=milk.parent_connection.parent)
    segmind_executor.compile(statechart)
    segmind_executor.tick()
    assert len(events_of(segmind_context, SupportEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(z=1, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(box1.global_pose.x, box1.global_pose.y,
                                                                                 box1.global_pose.z + 0.56, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, SupportEvent)) == 2
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(box2.global_pose.x, box2.global_pose.y,
                                                                                 box2.global_pose.z + 0.56, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, SupportEvent)) == 3
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 2

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(z=1, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 3
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)

def test_containment_detector(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart([ContainmentDetector(), LossOfContainmentDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, ContainmentEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(box1.global_pose.x, box1.global_pose.y,
                                                                                 box1.global_pose.z, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContainmentEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(box2.global_pose.x, box2.global_pose.y,
                                                                                 box2.global_pose.z, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContainmentEvent)) == 2
    assert len(events_of(segmind_context, LossOfContainmentEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(z=1, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfContainmentEvent)) == 2
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)

def test_pickup(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart([PickUpDetector(), SupportDetector(), TranslationDetector(), LossOfSupportDetector()])
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 0.93, reference_frame=milk.parent_connection.parent)

    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 1

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box2.global_pose.x,
            y=box2.global_pose.y,
            z=box2.global_pose.z + 0.56 + i * 0.1, reference_frame=milk.parent_connection.parent)
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) >= 1
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 1
    assert len(events_of(segmind_context, PickUpEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)

def test_placing(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [SupportDetector(), TranslationDetector(), StopTranslationDetector(), PlacingDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box2.global_pose.x,
            y=box2.global_pose.y,
            z=box2.global_pose.z + 0.97 - i * 0.1, reference_frame=milk.parent_connection.parent)
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) >= 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=box2.global_pose.x,
        y=box2.global_pose.y,
        z=box2.global_pose.z + 0.56, reference_frame=milk.parent_connection.parent)
    for _ in range(5):
        segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 1
    assert len(events_of(segmind_context, StopTranslationEvent)) == 1
    assert len(events_of(segmind_context, PlacingEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)

def test_pickup_then_place_back_on_same_surface(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [PickUpDetector(), PlacingDetector(), SupportDetector(), LossOfSupportDetector(),
         TranslationDetector(), StopTranslationDetector()])
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=box2.global_pose.x, y=box2.global_pose.y, z=box2.global_pose.z + 0.56, reference_frame=milk.parent_connection.parent)

    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 1

    # Pick the milk up off box2.
    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box2.global_pose.x,
            y=box2.global_pose.y,
            z=box2.global_pose.z + 0.56 + i * 0.1, reference_frame=milk.parent_connection.parent)
        segmind_executor.tick()

    assert len(events_of(segmind_context, LossOfSupportEvent)) == 1
    assert len(events_of(segmind_context, PickUpEvent)) == 1

    for _ in range(5):
        segmind_executor.tick()

    # Place the milk back down onto the very same surface (box2) it was picked up from.
    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box2.global_pose.x,
            y=box2.global_pose.y,
            z=box2.global_pose.z + 0.97 - i * 0.1, reference_frame=milk.parent_connection.parent)
        segmind_executor.tick()

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=box2.global_pose.x,
        y=box2.global_pose.y,
        z=box2.global_pose.z + 0.56, reference_frame=milk.parent_connection.parent)
    for _ in range(5):
        segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 2
    assert len(events_of(segmind_context, PlacingEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)


def test_translation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [TranslationDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) == 0

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1 + i * 0.1, y=-3, z=0.25, reference_frame=milk.parent_connection.parent)
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)


def test_stop_translation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [SupportDetector(), TranslationDetector(), StopTranslationDetector(), PlacingDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1 + i * 0.1, y=-3, z=0.25, reference_frame=milk.parent_connection.parent)
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) == 1

    for _ in range(5):
        segmind_executor.tick()

    assert len(events_of(segmind_context, StopTranslationEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)


def test_insertion(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [ContactDetector(), InsertionDetector(), LossOfContactDetector(), ContainmentDetector()])

    with segmind_executor.context.world.modify_world():
        hole = Body(
            name=PrefixedName("box_hole"),
            collision=ShapeCollection([Box(scale=Scale(1, 1, 1))]),
            visual=ShapeCollection([Box(scale=Scale(1, 1, 1))]),
        )
        hole_connection = FixedConnection(
            parent=segmind_executor.context.world.root,
            child=hole,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                2, 2, 2, reference_frame=segmind_executor.context.world.root
            ),
        )
        segmind_executor.context.world.add_connection(hole_connection)
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, InsertionEvent)) == 0
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(hole.global_pose.x, hole.global_pose.y,
                                                                                 hole.global_pose.z, reference_frame=milk.parent_connection.parent)

    segmind_executor.tick()

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(box2.global_pose.x,box2.global_pose.y,box2.global_pose.z, reference_frame=milk.parent_connection.parent)
    segmind_executor.tick()

    assert len(events_of(segmind_context, InsertionEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)


def test_rotation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [RotationDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()


    assert len([i for i in segmind_context.logger.get_events() if isinstance(i, RotationEvent)]) == 0

    for i in range(5):
        milk.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(
                roll=i * 0.1, reference_frame=milk.parent_connection.parent
            )
        )
        segmind_executor.tick()

    assert len([i for i in segmind_context.logger.get_events() if isinstance(i, RotationEvent)]) >= 1


def test_stop_rotation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [RotationDetector(), StopRotationDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len([i for i in segmind_context.logger.get_events() if isinstance(i, RotationEvent)]) == 0

    for i in range(5):
        milk.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(
                roll=i * 0.1, reference_frame=milk.parent_connection.parent
            )
        )
        segmind_executor.tick()
    assert len([i for i in segmind_context.logger.get_events() if isinstance(i, RotationEvent)]) >= 1

    for _ in range(5):
        segmind_executor.tick()
    assert len([i for i in segmind_context.logger.get_events() if isinstance(i, StopRotationEvent)]) >= 1


# %% a change of place nobody reported


def _place_milk_at(segmind_executor, milk, x: float) -> None:
    """
    Stand the milk at the given x on the apartment's floor plane, facing as it was.
    """
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=x, y=-3, z=0.25, reference_frame=segmind_executor.context.world.root
    )


def _restore_milk(segmind_executor, milk) -> None:
    """
    Put the milk back where the shared fixture keeps it.
    """
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=segmind_executor.context.world.root
    )


def _translation_watch(_simple_apartment_setup):
    """
    An executor watching the milk for translations and their ends, ticked once so the
    milk has been seen where it rests.
    """
    segmind_executor, segmind_context, milk, _, _ = _build_executor(
        _simple_apartment_setup
    )
    segmind_executor.compile(
        SegmindStatechart().build_statechart(
            [TranslationDetector(), StopTranslationDetector()]
        )
    )
    _place_milk_at(segmind_executor, milk, x=1.0)
    segmind_executor.tick()
    return segmind_executor, segmind_context, milk


def test_a_sudden_change_of_place_is_a_translation_from_where_the_body_rested(
    _simple_apartment_setup,
):
    """
    A body seen at rest and then seen somewhere else has moved, whether or not the
    window has ticks enough to have seen it move: the translation runs from where it
    rested to where it is.
    """
    segmind_executor, segmind_context, milk = _translation_watch(
        _simple_apartment_setup
    )
    rested_at = milk.numeric_global_pose

    _place_milk_at(segmind_executor, milk, x=1.1)
    segmind_executor.tick()

    [event] = events_of(segmind_context, TranslationEvent)
    assert np.allclose(event.start_pose.to_position().to_np()[:3], rested_at.position)
    assert np.allclose(
        event.current_pose.to_position().to_np()[:3], milk.numeric_global_pose.position
    )
    _restore_milk(segmind_executor, milk)


def test_a_body_seen_where_it_rests_is_not_translated(_simple_apartment_setup):
    segmind_executor, segmind_context, milk = _translation_watch(
        _simple_apartment_setup
    )

    for _ in range(6):
        segmind_executor.tick()

    assert events_of(segmind_context, TranslationEvent) == []
    _restore_milk(segmind_executor, milk)


def test_a_change_of_place_a_translation_under_way_claims_is_not_reported_again(
    _simple_apartment_setup,
):
    """
    A jump while the body is already being reported moving is that motion going on, not
    a second one.
    """
    segmind_executor, segmind_context, milk = _translation_watch(
        _simple_apartment_setup
    )
    _place_milk_at(segmind_executor, milk, x=1.1)
    segmind_executor.tick()
    assert len(events_of(segmind_context, TranslationEvent)) == 1

    _place_milk_at(segmind_executor, milk, x=1.3)
    segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) == 1
    _restore_milk(segmind_executor, milk)


def test_a_change_of_place_after_a_translation_ended_runs_from_where_it_ended(
    _simple_apartment_setup,
):
    """
    Where a reported translation ended is where the body rests from then on, so a later
    change of place is measured from there rather than from where the body first stood,
    which the earlier translation already accounted for.
    """
    segmind_executor, segmind_context, milk = _translation_watch(
        _simple_apartment_setup
    )
    _place_milk_at(segmind_executor, milk, x=1.1)
    for _ in range(8):
        segmind_executor.tick()
    [stopped] = events_of(segmind_context, StopTranslationEvent)
    assert len(events_of(segmind_context, TranslationEvent)) == 1

    _place_milk_at(segmind_executor, milk, x=1.3)
    segmind_executor.tick()

    [_, later] = events_of(segmind_context, TranslationEvent)
    assert np.allclose(
        later.start_pose.to_position().to_np(),
        stopped.current_pose.to_position().to_np(),
    )
    _restore_milk(segmind_executor, milk)


def test_slow_motion_with_all_motion_detectors(_simple_apartment_setup):
    """
    Runs every motion detector in one statechart on an object that drifts slowly.

    Each step stays below distance_threshold and rotation_threshold; only the displacement
    accumulated across the whole window exceeds them. Detecting this therefore requires every
    detector to hold a pose window that spans window_size ticks. While the window lived on the
    shared context, all four detectors appended to it on every tick, so it only ever spanned a
    single tick and drift this slow was never reported.
    """
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(_simple_apartment_setup)
    statechart = SegmindStatechart().build_statechart(
        [TranslationDetector(), StopTranslationDetector(), RotationDetector(), StopRotationDetector()])
    segmind_executor.compile(statechart)

    # Move the object to its start pose and let the pose windows settle, so that the events
    # triggered by that jump are not mistaken for the slow drift below.
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(x=1, y=-3, z=0.25, reference_frame=milk.parent_connection.parent)
    for _ in range(8):
        segmind_executor.tick()

    translations = len(events_of(segmind_context, TranslationEvent))
    rotations = len(events_of(segmind_context, RotationEvent))

    # Per tick this is 0.002m and 0.04rad, both below their detection thresholds. Across the
    # window it accumulates to more than 0.005m and 0.1rad, so it has to be reported.
    for i in range(1, 9):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1 + i * 0.002, y=-3, z=0.25, roll=i * 0.04, reference_frame=milk.parent_connection.parent)
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) > translations
    assert len(events_of(segmind_context, RotationEvent)) > rotations

    for _ in range(8):
        segmind_executor.tick()

    assert len(events_of(segmind_context, StopTranslationEvent)) >= 1
    assert len(events_of(segmind_context, StopRotationEvent)) >= 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(-1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent)

