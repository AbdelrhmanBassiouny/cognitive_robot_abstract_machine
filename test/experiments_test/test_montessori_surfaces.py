"""
Tests for reading the surfaces perception looks at out of the world the robot knows.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
from typing_extensions import List, Tuple

from experiments.montessori.perception import pipeline as pipeline_module
from experiments.montessori.perception.detections import MontessoriBoardDetection
from experiments.montessori.perception.exceptions import (
    BoardMissingFromWorld,
    RegionsDoNotMeet,
    SurfaceHasNothingToMeasure,
)
from experiments.montessori.perception.footprint import Footprint
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
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
    Pose,
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
    assert pipeline.table.region == expected.region
    assert pipeline.table.height == pytest.approx(expected.height)


def test_the_pipeline_takes_the_lid_height_from_the_board_in_the_world():
    montessori = _scene_world()

    pipeline = MontessoriPerceptionPipeline.of_world(
        montessori.world, _table_in(montessori).root
    )

    assert pipeline.lid.height == pytest.approx(
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


# %% which surface a detection belongs to


def _board_outlining(corners: List[Tuple[float, float]]) -> MontessoriBoardDetection:
    """
    A board whose lid was seen covering one outline.

    :param corners: The lid's world-frame ``(x, y)`` corners.
    """
    outline = np.asarray(corners, dtype=np.float32)
    center = outline.mean(axis=0)
    return MontessoriBoardDetection(
        pose=Pose.from_xyz_rpy(float(center[0]), float(center[1]), 0.0),
        footprint=Footprint.from_contour(outline.reshape(-1, 1, 2), 1.0),
        outline=outline.astype(float),
    )


def _surface_at(height: float) -> WorkspaceSurface:
    """
    A surface spanning the unit square at one height.

    :param height: Height of its plane above the world frame's origin, in metres.
    """
    return WorkspaceSurface(
        name=PrefixedName("surface", "test"),
        region=WorkspaceRegion(
            minimum_x=0.0, maximum_x=1.0, minimum_y=0.0, maximum_y=1.0
        ),
        height=height,
    )


def test_an_unbounded_surface_claims_whatever_stands_on_its_plane():
    search = SurfaceSearch(surface=_surface_at(0.8))

    assert search.claims(0.5, 0.5)


def test_a_surface_does_not_claim_what_stands_on_a_surface_above_it():
    board = _board_outlining([(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)])

    search = SurfaceSearch(surface=_surface_at(0.8), supported_surfaces=(board,))

    assert not search.claims(0.5, 0.5)
    assert search.claims(0.2, 0.2)


def test_a_bounded_surface_claims_only_what_stands_within_it():
    board = _board_outlining([(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)])

    search = SurfaceSearch(surface=_surface_at(0.88), boundary=board)

    assert search.claims(0.5, 0.5)
    assert not search.claims(0.2, 0.2)


# %% the stretch of a plane one pass rectifies


def test_a_surface_with_no_boundary_of_its_own_is_searched_wherever_it_reaches():
    surface = _surface_at(0.88)

    search = SurfaceSearch(surface=surface)

    assert search.is_searched
    assert search.region == surface.region


def test_a_surface_seen_only_where_its_boundary_was_is_searched_around_that_boundary():
    board = _board_outlining([(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)])
    surface = _surface_at(0.88)
    overhang = 0.02

    search = SurfaceSearch(surface=surface, boundary=board, overhang=overhang)

    assert search.region.minimum_x <= 0.4 - overhang
    assert search.region.maximum_x >= 0.6 + overhang
    assert search.region.minimum_y <= 0.4 - overhang
    assert search.region.maximum_y >= 0.6 + overhang
    assert search.region.maximum_x - search.region.minimum_x < (
        surface.region.maximum_x - surface.region.minimum_x
    )


def test_a_searched_patch_samples_the_same_world_points_its_whole_surface_would():
    board = _board_outlining([(0.4321, 0.4321), (0.6, 0.4321), (0.6, 0.6), (0.4321, 0.6)])
    surface = _surface_at(0.88)

    search = SurfaceSearch(surface=surface, boundary=board, overhang=0.0197)

    for narrowed, whole in (
        (search.region.minimum_x, surface.region.minimum_x),
        (search.region.minimum_y, surface.region.minimum_y),
    ):
        samples = (narrowed - whole) / surface.region.resolution
        assert samples == pytest.approx(round(samples))


def test_a_boundary_reaching_past_the_surface_is_searched_only_where_the_surface_is():
    board = _board_outlining([(0.9, 0.9), (1.5, 0.9), (1.5, 1.5), (0.9, 1.5)])
    surface = _surface_at(0.88)

    search = SurfaceSearch(surface=surface, boundary=board, overhang=0.02)

    assert search.region.maximum_x == surface.region.maximum_x
    assert search.region.maximum_y == surface.region.maximum_y


def test_a_look_narrowed_to_a_stretch_searches_only_where_the_two_meet():
    surface = _surface_at(0.88)
    stated = WorkspaceRegion(
        minimum_x=0.5, maximum_x=2.0, minimum_y=-1.0, maximum_y=0.75
    )

    search = SurfaceSearch(surface=surface, narrowed_to=stated)

    assert search.is_searched
    assert search.region == surface.region.intersection(stated)


def test_a_look_narrowed_away_from_a_surface_leaves_nothing_of_it_to_search():
    stated = WorkspaceRegion(
        minimum_x=5.0, maximum_x=6.0, minimum_y=5.0, maximum_y=6.0
    )

    search = SurfaceSearch(surface=_surface_at(0.88), narrowed_to=stated)

    assert not search.is_searched
    with pytest.raises(RegionsDoNotMeet):
        search.region
