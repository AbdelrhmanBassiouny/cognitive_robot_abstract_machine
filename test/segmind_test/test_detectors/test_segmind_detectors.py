import numpy as np
from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.events import (
    ContactEvent,
    GraspEvent,
    LiftEvent,
    LossOfContactEvent,
    LossOfGraspEvent,
    StopLiftEvent,
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
from segmind.detectors.atomic_event_detectors_nodes import (
    RotationDetector,
    StopRotationDetector,
    ContactDetector,
    LiftDetector,
    LossOfContactDetector,
    StopLiftDetector,
    TranslationDetector,
    StopTranslationDetector,
)
from segmind.detectors.base import SegmindContext
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.detectors.grasp_detector_nodes import GraspDetector, LossOfGraspDetector
from segmind.detectors.spatial_relation_detector_nodes import (
    SupportDetector,
    LossOfSupportDetector,
    ContainmentDetector,
    LossOfContainmentDetector,
    InsertionDetector,
    HoleContactDetector,
    LossOfHoleContactDetector,
)
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from segmind.statecharts.segmind_statechart import SegmindStatechart
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

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
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [ContactDetector(), LossOfContactDetector()]
    )
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, ContactEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        z=1, reference_frame=milk.parent_connection.parent
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfContactEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        box1.global_pose.x,
        box1.global_pose.y,
        box1.global_pose.z,
        reference_frame=milk.parent_connection.parent,
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContactEvent)) == 1
    assert len(events_of(segmind_context, LossOfContactEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        box2.global_pose.x,
        box2.global_pose.y,
        box2.global_pose.z,
        reference_frame=milk.parent_connection.parent,
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContactEvent)) == 2
    assert len(events_of(segmind_context, LossOfContactEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        z=1, reference_frame=milk.parent_connection.parent
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfContactEvent)) == 2
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_support_detector(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [SupportDetector(), LossOfSupportDetector()]
    )
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 0.93, reference_frame=milk.parent_connection.parent
    )
    segmind_executor.compile(statechart)
    segmind_executor.tick()
    assert len(events_of(segmind_context, SupportEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        z=1, reference_frame=milk.parent_connection.parent
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        box1.global_pose.x,
        box1.global_pose.y,
        box1.global_pose.z + 0.56,
        reference_frame=milk.parent_connection.parent,
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, SupportEvent)) == 2
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        box2.global_pose.x,
        box2.global_pose.y,
        box2.global_pose.z + 0.56,
        reference_frame=milk.parent_connection.parent,
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, SupportEvent)) == 3
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 2

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        z=1, reference_frame=milk.parent_connection.parent
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 3
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_containment_detector(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [ContainmentDetector(), LossOfContainmentDetector()]
    )
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, ContainmentEvent)) == 0

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        box1.global_pose.x,
        box1.global_pose.y,
        box1.global_pose.z,
        reference_frame=milk.parent_connection.parent,
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContainmentEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        box2.global_pose.x,
        box2.global_pose.y,
        box2.global_pose.z,
        reference_frame=milk.parent_connection.parent,
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, ContainmentEvent)) == 2
    assert len(events_of(segmind_context, LossOfContainmentEvent)) == 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        z=1, reference_frame=milk.parent_connection.parent
    )
    segmind_executor.tick()
    assert len(events_of(segmind_context, LossOfContainmentEvent)) == 2
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_pickup(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [
            PickUpDetector(),
            SupportDetector(),
            TranslationDetector(),
            LossOfSupportDetector(),
        ]
    )
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 0.93, reference_frame=milk.parent_connection.parent
    )

    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 1

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box2.global_pose.x,
            y=box2.global_pose.y,
            z=box2.global_pose.z + 0.56 + i * 0.1,
            reference_frame=milk.parent_connection.parent,
        )
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) >= 1
    assert len(events_of(segmind_context, LossOfSupportEvent)) == 1
    assert len(events_of(segmind_context, PickUpEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_placing(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [
            SupportDetector(),
            TranslationDetector(),
            StopTranslationDetector(),
            PlacingDetector(),
        ]
    )
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box2.global_pose.x,
            y=box2.global_pose.y,
            z=box2.global_pose.z + 0.97 - i * 0.1,
            reference_frame=milk.parent_connection.parent,
        )
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) >= 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=box2.global_pose.x,
        y=box2.global_pose.y,
        z=box2.global_pose.z + 0.56,
        reference_frame=milk.parent_connection.parent,
    )
    for _ in range(5):
        segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 1
    assert len(events_of(segmind_context, StopTranslationEvent)) == 1
    assert len(events_of(segmind_context, PlacingEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_pickup_then_place_back_on_same_surface(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [
            PickUpDetector(),
            PlacingDetector(),
            SupportDetector(),
            LossOfSupportDetector(),
            TranslationDetector(),
            StopTranslationDetector(),
        ]
    )
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=box2.global_pose.x,
        y=box2.global_pose.y,
        z=box2.global_pose.z + 0.56,
        reference_frame=milk.parent_connection.parent,
    )

    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 1

    # Pick the milk up off box2.
    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box2.global_pose.x,
            y=box2.global_pose.y,
            z=box2.global_pose.z + 0.56 + i * 0.1,
            reference_frame=milk.parent_connection.parent,
        )
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
            z=box2.global_pose.z + 0.97 - i * 0.1,
            reference_frame=milk.parent_connection.parent,
        )
        segmind_executor.tick()

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=box2.global_pose.x,
        y=box2.global_pose.y,
        z=box2.global_pose.z + 0.56,
        reference_frame=milk.parent_connection.parent,
    )
    for _ in range(5):
        segmind_executor.tick()

    assert len(events_of(segmind_context, SupportEvent)) == 2
    assert len(events_of(segmind_context, PlacingEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_translation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart([TranslationDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) == 0

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1 + i * 0.1, y=-3, z=0.25, reference_frame=milk.parent_connection.parent
        )
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_stop_translation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [
            SupportDetector(),
            TranslationDetector(),
            StopTranslationDetector(),
            PlacingDetector(),
        ]
    )
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1 + i * 0.1, y=-3, z=0.25, reference_frame=milk.parent_connection.parent
        )
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) == 1

    for _ in range(5):
        segmind_executor.tick()

    assert len(events_of(segmind_context, StopTranslationEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def test_insertion(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [
            ContactDetector(),
            InsertionDetector(),
            LossOfContactDetector(),
            ContainmentDetector(),
        ]
    )

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
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        hole.global_pose.x,
        hole.global_pose.y,
        hole.global_pose.z,
        reference_frame=milk.parent_connection.parent,
    )

    segmind_executor.tick()

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        box2.global_pose.x,
        box2.global_pose.y,
        box2.global_pose.z,
        reference_frame=milk.parent_connection.parent,
    )
    segmind_executor.tick()

    assert len(events_of(segmind_context, InsertionEvent)) == 1
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )


def _build_hole_region_world():
    """
    A standalone world (not the shared session-scoped apartment fixture, so nothing here
    can leak into other tests) with a movable ``shape`` body, a hole ``Aperture`` whose
    root is a ``Region`` at the world origin, an extra candidate ``Region`` next to that
    hole's own root (standing in for a taller volume spanning a real hole's full
    opening), and a separate ``landing_region`` standing in for the pocket a shape
    settles into once it has fallen through -- the same two-body relationship
    ``test_insertion`` already exercises with a real ``Body`` hole and ``box2``.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))

        shape = Body(
            name=PrefixedName("shape"),
            collision=ShapeCollection([Box(scale=Scale(0.3, 0.3, 0.3))]),
            visual=ShapeCollection([Box(scale=Scale(0.3, 0.3, 0.3))]),
        )
        shape_connection = Connection6DoF.create_with_dofs(
            world=world, parent=world.root, child=shape
        )
        world.add_connection(shape_connection)

        hole_root = Region(
            name=PrefixedName("hole_root"),
            area=ShapeCollection([Box(scale=Scale(1, 1, 0.3))]),
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=hole_root,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    0, 0, 0, reference_frame=world.root
                ),
            )
        )
        hole = Aperture(name=PrefixedName("hole"), root=hole_root)
        world.add_semantic_annotation(hole)

        extra_candidate = Region(
            name=PrefixedName("hole_extra_candidate"),
            area=ShapeCollection([Box(scale=Scale(1, 1, 0.3))]),
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=extra_candidate,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    3, 3, 3, reference_frame=world.root
                ),
            )
        )

        landing_region = Region(
            name=PrefixedName("landing_region"),
            area=ShapeCollection([Box(scale=Scale(1, 1, 1))]),
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=landing_region,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    0, 0, -1, reference_frame=world.root
                ),
            )
        )

    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        10, 10, 10, reference_frame=world.root
    )

    return world, shape, hole, hole_root, extra_candidate, landing_region


def test_insertion_through_region_rooted_hole():
    world, shape, hole, hole_root, extra_candidate, landing_region = (
        _build_hole_region_world()
    )
    context = MotionStatechartContext(world=world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = executor.context.require_extension(SegmindContext)

    statechart = SegmindStatechart().build_statechart(
        [
            HoleContactDetector(tracked_object=shape),
            LossOfHoleContactDetector(tracked_object=shape),
            ContainmentDetector(
                tracked_object=shape, additional_candidates=[landing_region]
            ),
            InsertionDetector(tracked_object=shape),
        ]
    )
    executor.compile(statechart)
    executor.tick()

    assert len(events_of(segmind_context, InsertionEvent)) == 0

    # Overlap the hole's own root -> a ContactEvent against hole_root.
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, 0, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    contact_events = events_of(segmind_context, ContactEvent)
    assert len(contact_events) == 1
    assert contact_events[0].with_object is hole_root

    # Move into the landing region -> a ContainmentEvent, correlated with the earlier
    # hole contact into an InsertionEvent.
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, -1, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    insertion_events = events_of(segmind_context, InsertionEvent)
    assert len(insertion_events) == 1
    assert insertion_events[0].with_object is hole_root
    assert insertion_events[0].through_hole is hole
    assert insertion_events[0].inserted_into_objects == [landing_region]


def test_hole_contact_detector_additional_candidate():
    """
    A shape overlapping only a hole's extra candidate region (not its own, often much
    thinner, root) still registers as touching that hole's own root -- the case
    :attr:`HoleContactDetector.additional_candidates` exists for.
    """
    world, shape, hole, hole_root, extra_candidate, landing_region = (
        _build_hole_region_world()
    )
    context = MotionStatechartContext(world=world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = executor.context.require_extension(SegmindContext)

    statechart = SegmindStatechart().build_statechart(
        [
            HoleContactDetector(
                tracked_object=shape, additional_candidates={hole: extra_candidate}
            ),
            LossOfHoleContactDetector(
                tracked_object=shape, additional_candidates={hole: extra_candidate}
            ),
        ]
    )
    executor.compile(statechart)
    executor.tick()

    assert len(events_of(segmind_context, ContactEvent)) == 0

    # Overlap only the extra candidate, nowhere near the hole's own thin root.
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        3, 3, 3, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    contact_events = events_of(segmind_context, ContactEvent)
    assert len(contact_events) == 1
    assert contact_events[0].with_object is hole_root

    # Move away from both -> the contact recorded against the hole's own root is lost.
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        10, 10, 10, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    loss_events = events_of(segmind_context, LossOfContactEvent)
    assert len(loss_events) == 1
    assert loss_events[0].with_object is hole_root


def _build_grasp_world():
    """
    A standalone world with a movable ``shape`` body and a synthetic two-fingered
    gripper: ``left_finger``/``right_finger`` (both real collidable bodies, co-located
    with ``shape``'s own grasp position so both register contact at once -- geometric
    finger placement isn't the concern here, the detector logic is) and a massless
    ``tool_frame`` body at the same position, standing in for a gripper's tool center
    point the way ``Tracy``'s own ``tool_frame`` link has no collision geometry either
    (see :mod:`segmind.detectors.grasp_detector_nodes`'s own docstring).
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))

        shape = Body(
            name=PrefixedName("shape"),
            collision=ShapeCollection([Box(scale=Scale(0.05, 0.05, 0.05))]),
            visual=ShapeCollection([Box(scale=Scale(0.05, 0.05, 0.05))]),
        )
        shape_connection = Connection6DoF.create_with_dofs(
            world=world, parent=world.root, child=shape
        )
        world.add_connection(shape_connection)

        left_finger = Body(
            name=PrefixedName("left_finger"),
            collision=ShapeCollection([Box(scale=Scale(0.1, 0.1, 0.1))]),
            visual=ShapeCollection([Box(scale=Scale(0.1, 0.1, 0.1))]),
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=left_finger,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    0, 0, 0, reference_frame=world.root
                ),
            )
        )

        right_finger = Body(
            name=PrefixedName("right_finger"),
            collision=ShapeCollection([Box(scale=Scale(0.1, 0.1, 0.1))]),
            visual=ShapeCollection([Box(scale=Scale(0.1, 0.1, 0.1))]),
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=right_finger,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    0, 0, 0, reference_frame=world.root
                ),
            )
        )

        tool_frame = Body(name=PrefixedName("tool_frame"))
        tool_frame_connection = Connection6DoF.create_with_dofs(
            world=world, parent=world.root, child=tool_frame
        )
        world.add_connection(tool_frame_connection)

    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        10, 10, 10, reference_frame=world.root
    )
    tool_frame.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, 0, reference_frame=world.root
    )

    return world, shape, left_finger, right_finger, tool_frame


def test_grasp_and_loss_of_grasp_detector():
    world, shape, left_finger, right_finger, tool_frame = _build_grasp_world()
    context = MotionStatechartContext(world=world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = executor.context.require_extension(SegmindContext)

    finger_tips = [left_finger, right_finger]
    statechart = SegmindStatechart().build_statechart(
        [
            GraspDetector(
                tracked_object=shape, finger_tips=finger_tips, tool_frame=tool_frame
            ),
            LossOfGraspDetector(
                tracked_object=shape, finger_tips=finger_tips, tool_frame=tool_frame
            ),
        ]
    )
    executor.compile(statechart)
    executor.tick()

    assert len(events_of(segmind_context, GraspEvent)) == 0
    assert shape not in segmind_context.latest_grasp

    # Touch both fingers, right at the tool center point.
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, 0, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    grasp_events = events_of(segmind_context, GraspEvent)
    assert len(grasp_events) == 1
    assert grasp_events[0].with_object is tool_frame
    assert shape in segmind_context.latest_grasp

    # Move away from both fingers and the tool center point.
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        10, 10, 10, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    loss_events = events_of(segmind_context, LossOfGraspEvent)
    assert len(loss_events) == 1
    assert loss_events[0].with_object is tool_frame
    assert shape not in segmind_context.latest_grasp


def test_grasp_detector_requires_tcp_proximity():
    """
    Contact with both fingers alone isn't enough -- the object also has to be close to
    the tool center point, not just resting against a finger somewhere far from it.
    """
    world, shape, left_finger, right_finger, tool_frame = _build_grasp_world()
    context = MotionStatechartContext(world=world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = executor.context.require_extension(SegmindContext)

    # Move the tool center point far away from where the fingers (and the shape) are.
    tool_frame.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        10, 10, 10, reference_frame=tool_frame.parent_connection.parent
    )

    statechart = SegmindStatechart().build_statechart(
        [
            GraspDetector(
                tracked_object=shape,
                finger_tips=[left_finger, right_finger],
                tool_frame=tool_frame,
            )
        ]
    )
    executor.compile(statechart)
    executor.tick()

    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, 0, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    assert len(events_of(segmind_context, GraspEvent)) == 0


def test_lift_detector_requires_grasp():
    world, shape, left_finger, right_finger, tool_frame = _build_grasp_world()
    context = MotionStatechartContext(world=world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = executor.context.require_extension(SegmindContext)

    statechart = SegmindStatechart().build_statechart(
        [LiftDetector(tracked_object=shape)]
    )
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, 0, reference_frame=shape.parent_connection.parent
    )
    executor.compile(statechart)
    executor.tick()

    # Rises well past distance_threshold each tick, but is never marked as grasped.
    for i in range(5):
        shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            z=i * 0.1, reference_frame=shape.parent_connection.parent
        )
        executor.tick()

    assert len(events_of(segmind_context, LiftEvent)) == 0

    segmind_context.latest_grasp.add(shape)
    for i in range(5, 10):
        shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            z=i * 0.1, reference_frame=shape.parent_connection.parent
        )
        executor.tick()

    assert len(events_of(segmind_context, LiftEvent)) == 1


def test_stop_lift_detector():
    world, shape, left_finger, right_finger, tool_frame = _build_grasp_world()
    context = MotionStatechartContext(world=world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = executor.context.require_extension(SegmindContext)

    statechart = SegmindStatechart().build_statechart(
        [LiftDetector(tracked_object=shape), StopLiftDetector(tracked_object=shape)]
    )
    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, 0, reference_frame=shape.parent_connection.parent
    )
    executor.compile(statechart)
    segmind_context.latest_grasp.add(shape)
    executor.tick()

    for i in range(5):
        shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            z=i * 0.1, reference_frame=shape.parent_connection.parent
        )
        executor.tick()

    assert len(events_of(segmind_context, LiftEvent)) == 1

    # Stop rising.
    for _ in range(5):
        executor.tick()

    assert len(events_of(segmind_context, StopLiftEvent)) == 1


def test_rotation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart([RotationDetector()])
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert (
        len(
            [
                i
                for i in segmind_context.logger.get_events()
                if isinstance(i, RotationEvent)
            ]
        )
        == 0
    )

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            roll=i * 0.1, reference_frame=milk.parent_connection.parent
        )
        segmind_executor.tick()

    assert (
        len(
            [
                i
                for i in segmind_context.logger.get_events()
                if isinstance(i, RotationEvent)
            ]
        )
        >= 1
    )


def test_stop_rotation(_simple_apartment_setup):
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [RotationDetector(), StopRotationDetector()]
    )
    segmind_executor.compile(statechart)
    segmind_executor.tick()

    assert (
        len(
            [
                i
                for i in segmind_context.logger.get_events()
                if isinstance(i, RotationEvent)
            ]
        )
        == 0
    )

    for i in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            roll=i * 0.1, reference_frame=milk.parent_connection.parent
        )
        segmind_executor.tick()
    assert (
        len(
            [
                i
                for i in segmind_context.logger.get_events()
                if isinstance(i, RotationEvent)
            ]
        )
        >= 1
    )

    for _ in range(5):
        segmind_executor.tick()
    assert (
        len(
            [
                i
                for i in segmind_context.logger.get_events()
                if isinstance(i, StopRotationEvent)
            ]
        )
        >= 1
    )


def test_slow_motion_with_all_motion_detectors(_simple_apartment_setup):
    """
    Runs every motion detector in one statechart on an object that drifts slowly.

    Each step stays below distance_threshold and rotation_threshold; only the
    displacement accumulated across the whole window exceeds them. Detecting this
    therefore requires every detector to hold a pose window that spans window_size
    ticks. While the window lived on the shared context, all four detectors appended to
    it on every tick, so it only ever spanned a single tick and drift this slow was
    never reported.
    """
    segmind_executor, segmind_context, milk, box1, box2 = _build_executor(
        _simple_apartment_setup
    )
    statechart = SegmindStatechart().build_statechart(
        [
            TranslationDetector(),
            StopTranslationDetector(),
            RotationDetector(),
            StopRotationDetector(),
        ]
    )
    segmind_executor.compile(statechart)

    # Move the object to its start pose and let the pose windows settle, so that the events
    # triggered by that jump are not mistaken for the slow drift below.
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=1, y=-3, z=0.25, reference_frame=milk.parent_connection.parent
    )
    for _ in range(8):
        segmind_executor.tick()

    translations = len(events_of(segmind_context, TranslationEvent))
    rotations = len(events_of(segmind_context, RotationEvent))

    # Per tick this is 0.002m and 0.04rad, both below their detection thresholds. Across the
    # window it accumulates to more than 0.005m and 0.1rad, so it has to be reported.
    for i in range(1, 9):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1 + i * 0.002,
            y=-3,
            z=0.25,
            roll=i * 0.04,
            reference_frame=milk.parent_connection.parent,
        )
        segmind_executor.tick()

    assert len(events_of(segmind_context, TranslationEvent)) > translations
    assert len(events_of(segmind_context, RotationEvent)) > rotations

    for _ in range(8):
        segmind_executor.tick()

    assert len(events_of(segmind_context, StopTranslationEvent)) >= 1
    assert len(events_of(segmind_context, StopRotationEvent)) >= 1

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=milk.parent_connection.parent
    )
