"""
Tests for :func:`~experiments.tracy_experiments.montessori.montessori_actions.build_sorting_actions`,
the pick/place action sequence builder shared by
:mod:`~experiments.tracy_experiments.montessori.montessori_demo_mujoco` and
:mod:`~experiments.tracy_experiments.montessori.montessori_demo_real`.
"""

from dataclasses import dataclass

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from experiments.montessori.semantics import (
    CubeShape,
    DiskShape,
    MontessoriShape,
    NoMatchingHoleError,
)
from experiments.montessori.world import MontessoriWorld
from experiments.tracy_experiments.montessori.montessori_actions import (
    SKIPPED_SHAPE_CATEGORIES,
    build_sorting_actions,
)
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose
from semantic_digital_twin.world_description.world_entity import Body

from .dataset.synthetic_fixed_arm_robot import SyntheticFixedArmRobot

MOUNT_POSITION = Point3(0.25, 0.0, 0.5)


@dataclass
class _RecordedPickUp:
    """Stands in for ``PickUpAction``/``PickUpActionMujoco``, recording its own arguments."""

    object_designator: Body
    arm: Arms
    grasp_description: GraspDescription


@dataclass
class _RecordedPlace:
    """Stands in for ``PlaceAction``/``PlaceActionMujoco``, recording its own arguments."""

    object_designator: Body
    target_location: Pose
    arm: Arms


class _NoHoleBoard:
    """A board mimic whose ``hole_for`` never finds a match, for the skip-path tests."""

    name = PrefixedName("stub_board")

    def hole_for(self, montessori_shape):
        raise NoMatchingHoleError(montessori_shape=montessori_shape, board=self)


class _SingleShapeWorld:
    """A world mimic exposing exactly one fixed list of shapes, for the skip-path tests."""

    def __init__(self, shapes):
        self._shapes = shapes

    def get_semantic_annotations_by_type(self, annotation_type):
        return self._shapes


def _montessori_with_mounted_fixed_arm_robot() -> MontessoriWorld:
    montessori = MontessoriWorld()
    montessori.add_robot_stand(MOUNT_POSITION)
    robot_world = URDFParser.from_file(
        SyntheticFixedArmRobot.get_ros_file_path()
    ).parse()
    montessori.mount_stationary_robot(
        SyntheticFixedArmRobot, robot_world, MOUNT_POSITION
    )
    montessori.world.update_forward_kinematics()
    return montessori


def _sortable_shapes(world, board) -> list:
    """
    Every shape :func:`build_sorting_actions` is expected to build a pick/place pair
    for: not one of :data:`SKIPPED_SHAPE_CATEGORIES`, and with a hole ``board`` actually
    has (both read straight from the same production data the function under test
    consumes, not a separately hardcoded count).
    """
    sortable = []
    for shape in world.get_semantic_annotations_by_type(MontessoriShape):
        if shape.shape_category in SKIPPED_SHAPE_CATEGORIES:
            continue
        try:
            board.hole_for(shape)
        except NoMatchingHoleError:
            continue
        sortable.append(shape)
    return sortable


def test_build_sorting_actions_builds_one_pick_and_place_pair_per_sortable_shape():
    montessori = _montessori_with_mounted_fixed_arm_robot()
    world = montessori.world
    sortable = _sortable_shapes(world, montessori.board)
    # The default scene spawns both a skipped-category shape (disk) and a shape with no
    # matching hole (sphere), so this also exercises that not every shape in the world
    # ends up sortable.
    assert len(sortable) < len(
        list(world.get_semantic_annotations_by_type(MontessoriShape))
    )

    actions = build_sorting_actions(
        world,
        montessori.board,
        montessori.robot,
        Arms.RIGHT,
        pick_up_action=_RecordedPickUp,
        place_action=_RecordedPlace,
    )

    assert len(actions) == 2 * len(sortable)
    for shape, pick, place in zip(sortable, actions[0::2], actions[1::2]):
        assert isinstance(pick, _RecordedPickUp)
        assert isinstance(place, _RecordedPlace)
        assert pick.object_designator is shape.root
        assert place.object_designator is shape.root
        assert pick.arm is Arms.RIGHT
        assert place.arm is Arms.RIGHT


def test_build_sorting_actions_skips_a_shape_with_no_matching_hole():
    shape = CubeShape(
        name=PrefixedName("orphan"), root=Body(name=PrefixedName("orphan_body"))
    )

    actions = build_sorting_actions(
        _SingleShapeWorld([shape]),
        _NoHoleBoard(),
        robot=None,
        arm=Arms.RIGHT,
        pick_up_action=_RecordedPickUp,
        place_action=_RecordedPlace,
    )

    assert actions == []


def test_build_sorting_actions_skips_a_skipped_shape_category():
    shape = DiskShape(
        name=PrefixedName("disk"), root=Body(name=PrefixedName("disk_body"))
    )

    actions = build_sorting_actions(
        _SingleShapeWorld([shape]),
        board=_NoHoleBoard(),
        robot=None,
        arm=Arms.RIGHT,
        pick_up_action=_RecordedPickUp,
        place_action=_RecordedPlace,
    )

    assert actions == []
