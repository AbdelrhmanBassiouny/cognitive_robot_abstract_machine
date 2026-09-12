"""
Tests for ``build_pick_monitor`` in
:mod:`experiments.tracy_experiments.montessori.event_monitoring`: it wires the pick-half
detectors -- support, translation, grasp, lift and pick-up -- to the tracked body and
the picking gripper, and adds none of the hole-contact, containment or insertion
detectors that need a board model.
"""

from __future__ import annotations

from coraplex.datastructures.enums import Arms
from experiments.montessori.world import mount_stationary_robot
from experiments.tracy_experiments.equipment import (
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.montessori.event_monitoring import (
    _picking_end_effector,
    build_pick_monitor,
)
from segmind.detectors.atomic_event_detectors_nodes import (
    LiftDetector,
    StopLiftDetector,
    StopTranslationDetector,
    TranslationDetector,
)
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.detectors.grasp_detector_nodes import GraspDetector, LossOfGraspDetector
from segmind.detectors.spatial_relation_detector_nodes import (
    ContainmentDetector,
    HoleContactDetector,
    InsertionDetector,
    LossOfContainmentDetector,
    LossOfHoleContactDetector,
    LossOfSupportDetector,
    SupportDetector,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

PICK_HALF_DETECTOR_TYPES = frozenset(
    {
        SupportDetector,
        LossOfSupportDetector,
        TranslationDetector,
        StopTranslationDetector,
        GraspDetector,
        LossOfGraspDetector,
        LiftDetector,
        StopLiftDetector,
        PickUpDetector,
        PlacingDetector,
    }
)
"""
The detector types :func:`build_pick_monitor` is expected to assemble.
"""

BOARD_DEPENDENT_DETECTOR_TYPES = frozenset(
    {
        HoleContactDetector,
        LossOfHoleContactDetector,
        ContainmentDetector,
        LossOfContainmentDetector,
        InsertionDetector,
    }
)
"""
The detector types that need a board model and must be absent from a pick monitor.
"""


def _mounted_tracy() -> tuple[World, Tracy]:
    """
    A world with a single Tracy mounted at the origin.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(
            Body(name=PrefixedName(name="root", prefix="world"))
        )
    tracy_world = parse_tracy()
    mount_position, _ = tracy_table_mount_position(tracy_world, x=0.0, y=0.0)
    robot = mount_stationary_robot(world, Tracy, tracy_world, mount_position)
    return world, robot


def test_build_pick_monitor_assembles_exactly_the_pick_half_detectors():
    world, robot = _mounted_tracy()
    shape = Body(name=PrefixedName("shape"))

    monitor = build_pick_monitor(
        world=world, tracked_body=shape, robot=robot, arm=Arms.LEFT
    )

    assert {
        type(detector) for detector in monitor.detectors
    } == PICK_HALF_DETECTOR_TYPES


def test_build_pick_monitor_adds_no_board_dependent_detectors():
    world, robot = _mounted_tracy()
    shape = Body(name=PrefixedName("shape"))

    monitor = build_pick_monitor(
        world=world, tracked_body=shape, robot=robot, arm=Arms.LEFT
    )

    assert BOARD_DEPENDENT_DETECTOR_TYPES.isdisjoint(
        {type(detector) for detector in monitor.detectors}
    )


def test_every_pick_detector_tracks_the_given_body():
    world, robot = _mounted_tracy()
    shape = Body(name=PrefixedName("shape"))

    monitor = build_pick_monitor(
        world=world, tracked_body=shape, robot=robot, arm=Arms.LEFT
    )

    assert all(detector.tracked_object is shape for detector in monitor.detectors)


def test_grasp_detectors_are_wired_to_the_picking_arms_gripper():
    world, robot = _mounted_tracy()
    shape = Body(name=PrefixedName("shape"))
    end_effector = _picking_end_effector(robot, Arms.LEFT)

    monitor = build_pick_monitor(
        world=world, tracked_body=shape, robot=robot, arm=Arms.LEFT
    )

    grasp_detectors = [
        detector
        for detector in monitor.detectors
        if isinstance(detector, (GraspDetector, LossOfGraspDetector))
    ]
    assert len(grasp_detectors) == 2
    for detector in grasp_detectors:
        assert detector.finger_tips == [
            end_effector.thumb.tip,
            end_effector.finger.tip,
        ]
        assert detector.tool_frame is end_effector.tool_frame
