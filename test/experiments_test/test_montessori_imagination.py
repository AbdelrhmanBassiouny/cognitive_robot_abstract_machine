"""
Tests for the world a look's own findings stand in: what a finding becomes there, that
the world the look was taken in is left as it was, and that what a statement rejects is
taken out again.
"""

from __future__ import annotations

import pytest

from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import CubeShape, MontessoriShape
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

CUBE = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
"""
The piece every test below stands somewhere.
"""

SEEN_AT = (0.58, 0.15, 0.75)
"""
Where it is seen, in metres, which is a place on the table of the rendered scene.
"""

SEEN_AGAIN_AT = (0.62, 0.21, 0.75)
"""
Where a later look finds the same piece, a few centimetres from where it was.
"""


@pytest.fixture
def world_with_a_table() -> World:
    """
    A world holding one body, standing in for the world a look is taken in.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("table", "world_the_look_was_taken_in")))
    return world


def seen_at(x: float, y: float, z: float, reference_frame=None) -> Pose:
    """
    A pose standing for where a look reported something.

    :param x: Position along the world frame's x-axis, in metres.
    :param y: Position along the world frame's y-axis, in metres.
    :param z: Position along the world frame's z-axis, in metres.
    :param reference_frame: The frame the look reports its findings in.
    """
    return Pose.from_xyz_rpy(x, y, z, reference_frame=reference_frame)


# %% what a finding becomes


def test_a_finding_stands_in_the_world_as_the_piece_it_was_recognised_as():
    imagined = ImaginedWorld.copied_from(None)

    shape = imagined.spawn(CUBE, seen_at(*SEEN_AT))

    assert isinstance(shape, CubeShape)
    assert shape.shape_category == CUBE.category


def test_a_finding_stands_where_it_was_seen():
    imagined = ImaginedWorld.copied_from(None)

    shape = imagined.spawn(CUBE, seen_at(*SEEN_AT))

    assert shape.root.global_pose.to_position().to_np()[:3] == pytest.approx(
        SEEN_AT, abs=1e-9
    )


def test_a_findings_body_is_the_piece_as_it_was_measured():
    """
    A body standing for what was seen carries the piece's own measured outline and
    height, so a relation reading its geometry reads the piece rather than a stand-in.
    """
    imagined = ImaginedWorld.copied_from(None)

    shape = imagined.spawn(CUBE, seen_at(*SEEN_AT))

    lower, upper = shape.root.collision.combined_mesh.bounds
    assert float(upper[2] - lower[2]) == pytest.approx(CUBE.height, abs=1e-6)


def test_a_finding_is_something_the_world_holds_as_a_semantic_annotation():
    imagined = ImaginedWorld.copied_from(None)

    shape = imagined.spawn(CUBE, seen_at(*SEEN_AT))

    assert imagined.world.get_semantic_annotations_by_type(MontessoriShape) == [shape]


def test_a_finding_can_be_placed_somewhere_else_by_a_later_look():
    """
    A look measures where a piece is, never that it cannot move, so a later look that
    finds it elsewhere re-places it rather than needing a different world.
    """
    imagined = ImaginedWorld.copied_from(None)
    shape = imagined.spawn(CUBE, seen_at(*SEEN_AT))
    connection = shape.root.parent_connection

    connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        *SEEN_AGAIN_AT, reference_frame=connection.parent
    )

    assert shape.root.global_pose.to_position().to_np()[:3] == pytest.approx(
        SEEN_AGAIN_AT, abs=1e-9
    )
    assert shape.root.parent_connection is connection


# %% the world the look was taken in


def test_the_world_the_look_was_taken_in_is_left_as_it_was(world_with_a_table: World):
    """
    A look reasons about what it might have found, so what it spawns may never reach the
    world the robot is actually acting in.
    """
    held_before = len(world_with_a_table.kinematic_structure_entities)

    imagined = ImaginedWorld.copied_from(world_with_a_table)
    imagined.spawn(CUBE, seen_at(*SEEN_AT))

    assert len(world_with_a_table.kinematic_structure_entities) == held_before
    assert world_with_a_table.get_semantic_annotations_by_type(MontessoriShape) == []


def test_a_finding_hangs_from_the_copys_own_frame_rather_than_the_one_it_was_copied_from(
    world_with_a_table: World,
):
    """
    A pose keeps naming the frame the look reported it in, and the copy holds a frame of
    that name of its own, so the body is placed against the copy's counterpart.
    """
    table = world_with_a_table.root
    imagined = ImaginedWorld.copied_from(world_with_a_table, reference_frame=table)

    shape = imagined.spawn(CUBE, seen_at(*SEEN_AT, reference_frame=table))

    assert shape.root.parent_connection.parent.name == table.name
    assert shape.root.parent_connection.parent is not table


# %% taking a finding back out


def test_a_rejected_finding_is_taken_out_of_the_world_again():
    imagined = ImaginedWorld.copied_from(None)
    rejected = imagined.spawn(CUBE, seen_at(*SEEN_AT))
    kept = imagined.spawn(CUBE, seen_at(0.58, 0.35, 0.75))

    imagined.remove(rejected)

    assert imagined.world.get_semantic_annotations_by_type(MontessoriShape) == [kept]
    assert rejected.root not in imagined.world.kinematic_structure_entities


def test_two_findings_of_one_piece_are_two_things_the_world_holds():
    """
    Two pieces of the same kind stand in the same world at once, so what a finding is
    called cannot be what the piece is called.
    """
    imagined = ImaginedWorld.copied_from(None)

    first = imagined.spawn(CUBE, seen_at(*SEEN_AT))
    second = imagined.spawn(CUBE, seen_at(0.58, 0.35, 0.75))

    assert first.name != second.name
    assert len(imagined.world.get_semantic_annotations_by_type(MontessoriShape)) == 2
