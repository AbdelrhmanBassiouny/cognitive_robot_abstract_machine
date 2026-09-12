"""
The shape-sorting board stated in the entity query language: what its lid measures, how
tall it stands, and each hole's shape, size and place on the lid -- read back as the
layout a look fits over a picture.
"""

from __future__ import annotations

import math
from dataclasses import fields

import pytest

from experiments.montessori.board_description import (
    DescribedBoard,
    StatedBoardAttribute,
    StatedHoleAttribute,
)
from experiments.montessori.exceptions import BoardDescriptionIncomplete
from experiments.montessori.hole_geometry import BoardHoleLayout, HoleFootprint
from experiments.montessori.planar_geometry import PlanarPoint, PlanarSize
from experiments.montessori.semantics import (
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.world import BOARD_SCALE
from krrood.entity_query_language.factories import a
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

HOLE_SIZE_TOLERANCE = 0.001
"""
How far, in metres, a hole outlined from its stated shape may reach past the mesh's own
outline of it: the mesh cuts corners the ideal shapes do not.
"""

# %% a hole outlined from its description


def test_a_described_hole_is_its_shape_turned_where_it_stands_on_the_lid():
    size = PlanarSize(0.02, 0.04)

    hole = HoleFootprint.of_description(
        MontessoriShapeCategory.RECTANGULAR_PRISM,
        size=size,
        center=PlanarPoint(0.01, -0.03),
        turn=math.pi / 2,
    )

    assert (hole.size.x, hole.size.y) == pytest.approx((size.y, size.x))
    assert hole.center == PlanarPoint(0.01, -0.03)
    assert hole.turn == pytest.approx(math.pi / 2)


# %% the board described from its mesh


def test_a_board_described_from_its_mesh_reads_back_as_the_mesh_layout():
    mesh = BoardHoleLayout.of_board_mesh()

    read_back = DescribedBoard.of_statement(
        DescribedBoard.of_layout(mesh, height=float(BOARD_SCALE.z)).statement()
    )

    assert [hole.category for hole in read_back.layout.holes] == [
        hole.category for hole in mesh.holes
    ]
    for described, measured in zip(read_back.layout.holes, mesh.holes):
        assert (described.center.x, described.center.y) == pytest.approx(
            (measured.center.x, measured.center.y)
        )
        assert (described.size.x, described.size.y) == pytest.approx(
            (measured.size.x, measured.size.y), abs=HOLE_SIZE_TOLERANCE
        )
    assert (read_back.layout.size.x, read_back.layout.size.y) == pytest.approx(
        (mesh.size.x, mesh.size.y)
    )
    assert read_back.height == float(BOARD_SCALE.z)


# %% the vocabulary a description is written in


@pytest.mark.parametrize(
    "annotation, attributes",
    [
        (ShapeSortingBoard, StatedBoardAttribute),
        (ShapeSortingHole, StatedHoleAttribute),
    ],
    ids=["board", "hole"],
)
def test_every_stated_attribute_is_a_field_of_the_annotation_it_describes(
    annotation, attributes
):
    field_names = {field_.name for field_ in fields(annotation)}

    assert {str(attribute) for attribute in attributes} <= field_names


# %% a described board stood in a world


def test_a_described_board_stands_in_a_world_with_its_stated_holes_where_it_was_found():
    described = DescribedBoard.of_layout(
        BoardHoleLayout.of_board_mesh(), height=float(BOARD_SCALE.z)
    )
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("root", "test")))
    center, yaw, lid_height = PlanarPoint(0.8, 0.1), math.radians(30.0), 0.96

    stood = described.stand_in(
        world,
        Pose.from_xyz_rpy(center.x, center.y, lid_height, yaw=yaw),
        prefix="test",
    )

    assert world.get_semantic_annotations_by_type(ShapeSortingBoard) == [stood]
    assert (stood.lid_size, stood.height) == (described.lid_size, described.height)
    assert [
        (
            hole.shape_category,
            hole.footprint_size,
            hole.position_on_lid,
            hole.turn_on_lid,
        )
        for hole in stood.apertures
    ] == [
        (
            hole.shape_category,
            hole.footprint_size,
            hole.position_on_lid,
            hole.turn_on_lid,
        )
        for hole in described.holes
    ]
    for hole, placed in zip(stood.apertures, described.layout.placed(center, yaw)):
        stands_at = hole.root.global_transform.to_position().to_np()
        assert (float(stands_at[0]), float(stands_at[1])) == pytest.approx(
            (placed.center.x, placed.center.y)
        )
    assert WorkspaceSurface.of(stood, world.root).height == pytest.approx(lid_height)


# %% what a description must say


def test_a_hole_stated_without_its_place_on_the_lid_describes_no_board():
    statement = a(ShapeSortingBoard)(
        lid_size=PlanarSize(0.11, 0.28),
        height=0.08,
        apertures=[
            a(ShapeSortingHole)(
                shape_category=MontessoriShapeCategory.CUBE,
                footprint_size=PlanarSize(0.03, 0.03),
            )
        ],
    )

    with pytest.raises(BoardDescriptionIncomplete):
        DescribedBoard.of_statement(statement)
