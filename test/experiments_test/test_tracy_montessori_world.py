"""
Tests for :mod:`experiments.tracy_experiments.montessori.world`: the loose shapes on
Tracy's table are built as the set the scene is told stands there, and the board stands
where the scene is told to stand it, its holes and drawers with it.
"""

from __future__ import annotations

import pytest

from experiments.montessori.pieces import (
    FULL_SIZE_PIECES,
    SMALLER_PIECES,
    KnownPieceSet,
)
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.tracy_experiments.montessori.world import (
    BOARD_POSITION_TRACY,
    TracyMontessoriWorld,
)
from semantic_digital_twin.semantic_annotations.semantic_annotations import Drawer
from semantic_digital_twin.spatial_types.spatial_types import Point3

TABLE_TOP_Z = 0.855
"""
An arbitrary height for Tracy's table top.
"""

ELSEWHERE = Point3(1.045, 0.159, 0.0)
"""
An arbitrary place to stand the board at, other than the default.
"""


def _shapes(scene: TracyMontessoriWorld) -> list[MontessoriShape]:
    scene.world.update_forward_kinematics()
    return scene.world.get_semantic_annotations_by_type(MontessoriShape)


@pytest.mark.parametrize("pieces", [FULL_SIZE_PIECES, SMALLER_PIECES])
def test_every_loose_shape_is_built_as_the_set_the_scene_is_told_stands_there(pieces):
    scene = TracyMontessoriWorld(table_top_z=TABLE_TOP_Z, pieces=pieces)

    shapes = _shapes(scene)

    assert {shape.shape_category for shape in shapes} == set(pieces.by_category)
    for shape in shapes:
        piece = pieces.by_category[shape.shape_category]
        assert shape.cross_section_size == pytest.approx(piece.cross_section_size)
        bounds = shape.root.collision.combined_mesh.bounds
        assert bounds[1][2] - bounds[0][2] == pytest.approx(piece.height)
        assert shape.root.collision[0].color == piece.color


def _hole_names(scene: TracyMontessoriWorld) -> list:
    return sorted(
        hole.name
        for hole in ShapeSortingBoard.held_by(scene.world).apertures
        if isinstance(hole, ShapeSortingHole)
    )


def test_a_scene_told_a_part_of_the_set_builds_only_those_pieces():
    """
    A run with one piece on the table hands the scene a set of one; the board still has
    a hole for every category, and a hole without a piece in the set stays empty.
    """
    a_cube_alone = KnownPieceSet(
        pieces=(SMALLER_PIECES.by_category[MontessoriShapeCategory.CUBE],)
    )

    scene = TracyMontessoriWorld(table_top_z=TABLE_TOP_Z, pieces=a_cube_alone)

    assert [shape.shape_category for shape in _shapes(scene)] == [
        MontessoriShapeCategory.CUBE
    ]
    assert _hole_names(scene) == _hole_names(
        TracyMontessoriWorld(table_top_z=TABLE_TOP_Z)
    )


def test_the_board_stands_where_the_scene_is_told_with_its_holes_and_drawers():
    default = TracyMontessoriWorld(table_top_z=TABLE_TOP_Z)
    moved = TracyMontessoriWorld(table_top_z=TABLE_TOP_Z, board_position=ELSEWHERE)
    default.world.update_forward_kinematics()
    moved.world.update_forward_kinematics()
    shift = [
        float(ELSEWHERE.x) - float(BOARD_POSITION_TRACY.x),
        float(ELSEWHERE.y) - float(BOARD_POSITION_TRACY.y),
        0.0,
    ]

    def position_of(scene: TracyMontessoriWorld, name: str) -> list[float]:
        entity = next(
            entity
            for entity in scene.world.kinematic_structure_entities
            if entity.name.name == name
        )
        return [
            float(value)
            for value in scene.world.compute_forward_kinematics_np(
                scene.world.root, entity
            )[:3, 3]
        ]

    assert position_of(moved, "board")[:2] == pytest.approx(
        [float(ELSEWHERE.x), float(ELSEWHERE.y)]
    )
    names = [hole.name.name for hole in default.board.apertures] + [
        drawer.name.name
        for drawer in default.world.get_semantic_annotations_by_type(Drawer)
    ]
    assert names
    for name in names:
        assert position_of(moved, name) == pytest.approx(
            [a + b for a, b in zip(position_of(default, name), shift)]
        )
