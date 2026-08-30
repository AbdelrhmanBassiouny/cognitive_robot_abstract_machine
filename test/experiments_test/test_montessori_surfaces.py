"""
Tests for reading the surfaces perception looks at out of the world the robot knows.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from experiments.montessori.perception import pipeline as pipeline_module
from experiments.montessori.perception.exceptions import (
    BoardMissingFromWorld,
    SurfaceHasNothingToMeasure,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori import world as montessori_world
from experiments.montessori.world import (
    BOARD_POSITION,
    BOARD_SCALE,
    TABLE_POSITION,
    TABLE_SCALE,
    MontessoriWorld,
)
from experiments.tracy_experiments import equipment as tracy_equipment
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

# %% building a world to read a surface out of


def _world_rooted_at(body: Body) -> World:
    """
    A world whose only content, and whose own root, is one body.

    :param body: The body to build the world around.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
    return world


def _table_in(montessori: MontessoriWorld) -> Table:
    """
    The table the Montessori scene is set up on.

    :param montessori: The scene to read the table out of.
    """
    [table] = montessori.world.get_semantic_annotations_by_type(Table)
    return table


def _scene_world() -> MontessoriWorld:
    """
    A Montessori scene with its transforms resolved, ready for a surface to be read.
    """
    montessori = MontessoriWorld()
    montessori.world.update_forward_kinematics()
    return montessori


def test_a_surface_spans_the_table_the_world_describes():
    montessori = _scene_world()

    surface = WorkspaceSurface.of_body(
        _table_in(montessori).root, montessori.world.root
    )

    assert surface.region.minimum_x == pytest.approx(
        float(TABLE_POSITION.x) - TABLE_SCALE.x / 2
    )
    assert surface.region.maximum_x == pytest.approx(
        float(TABLE_POSITION.x) + TABLE_SCALE.x / 2
    )
    assert surface.region.minimum_y == pytest.approx(
        float(TABLE_POSITION.y) - TABLE_SCALE.y / 2
    )
    assert surface.region.maximum_y == pytest.approx(
        float(TABLE_POSITION.y) + TABLE_SCALE.y / 2
    )


def test_a_surface_lies_at_the_top_of_the_body_it_is_read_from():
    montessori = _scene_world()

    surface = WorkspaceSurface.of_body(
        _table_in(montessori).root, montessori.world.root
    )

    assert surface.height == pytest.approx(float(TABLE_POSITION.z) + TABLE_SCALE.z / 2)


def test_a_surface_ignores_the_legs_that_hold_it_up():
    top_scale = Scale(0.8, 0.8, 0.02)
    top_center_z = 0.7
    foot_scale = Scale(0.06, 0.06, top_center_z)
    foot_reach = 0.6
    table = Body(
        name=PrefixedName("splay_footed_table", "test"),
        collision=ShapeCollection(
            [
                Box(
                    scale=top_scale,
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(z=top_center_z),
                )
            ]
            + [
                Box(
                    scale=foot_scale,
                    origin=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=sign_x * foot_reach,
                        y=sign_y * foot_reach,
                        z=top_center_z / 2,
                    ),
                )
                for sign_x in (-1, 1)
                for sign_y in (-1, 1)
            ]
        ),
    )

    surface = WorkspaceSurface.of_body(table, _world_rooted_at(table).root)

    assert surface.region.maximum_x == pytest.approx(top_scale.x / 2)
    assert surface.region.maximum_y == pytest.approx(top_scale.y / 2)
    assert surface.height == pytest.approx(top_center_z + top_scale.z / 2)


def test_a_surface_follows_the_region_the_world_declares_for_it():
    root = Body(name=PrefixedName("root", "test"))
    counter_top = Body(
        name=PrefixedName("counter", "test"),
        collision=ShapeCollection([Box(scale=Scale(2.0, 2.0, 0.05))]),
    )
    declared_scale = Scale(0.4, 0.6, 0.01)
    declared_at = Point3(1.0, 2.0, 0.5)
    declared = Region(
        name=PrefixedName("declared_surface", "test"),
        area=ShapeCollection([Box(scale=declared_scale)]),
    )
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        for child, position in (
            (counter_top, Point3(0.0, 0.0, 0.0)),
            (declared, declared_at),
        ):
            world.add_connection(
                FixedConnection(
                    parent=root,
                    child=child,
                    parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=position.x, y=position.y, z=position.z
                    ),
                )
            )
    world.update_forward_kinematics()
    counter = Table(
        name=PrefixedName("counter", "test"),
        root=counter_top,
        supporting_surface=declared,
    )

    surface = WorkspaceSurface.of(counter, world.root)

    assert surface.region.minimum_x == pytest.approx(
        float(declared_at.x) - declared_scale.x / 2
    )
    assert surface.region.maximum_y == pytest.approx(
        float(declared_at.y) + declared_scale.y / 2
    )
    assert surface.height == pytest.approx(float(declared_at.z) + declared_scale.z / 2)


def test_a_surface_with_nothing_to_measure_is_refused():
    bare = Body(name=PrefixedName("bare", "test"))

    with pytest.raises(SurfaceHasNothingToMeasure):
        WorkspaceSurface.of_body(bare, _world_rooted_at(bare).root)


def test_the_pipeline_takes_its_workspace_from_the_table_in_the_world():
    montessori = _scene_world()
    table = _table_in(montessori).root

    pipeline = MontessoriPerceptionPipeline.of_world(montessori.world, table)

    expected = WorkspaceSurface.of_body(table, montessori.world.root)
    assert pipeline.region == expected.region
    assert pipeline.table_height == pytest.approx(expected.height)


def test_the_pipeline_takes_the_lid_height_from_the_board_in_the_world():
    montessori = _scene_world()

    pipeline = MontessoriPerceptionPipeline.of_world(
        montessori.world, _table_in(montessori).root
    )

    assert pipeline.lid_height == pytest.approx(
        float(BOARD_POSITION.z) + BOARD_SCALE.z / 2
    )


def test_a_world_without_a_board_is_refused():
    lone_table = Body(
        name=PrefixedName("lone_table", "test"),
        collision=ShapeCollection([Box(scale=Scale(1.0, 1.0, 0.02))]),
    )

    with pytest.raises(BoardMissingFromWorld):
        MontessoriPerceptionPipeline.of_world(_world_rooted_at(lone_table), lone_table)


def test_the_node_takes_no_scene_constant_from_another_module():
    node_source = Path(pipeline_module.__file__).with_name("node.py")

    imported = {
        statement.module
        for statement in ast.walk(ast.parse(node_source.read_text()))
        if isinstance(statement, ast.ImportFrom)
    }

    assert montessori_world.__name__ not in imported
    assert tracy_equipment.__name__ not in imported
