"""
How much of a region a simulator draws.

A region names a volume of space rather than a thing standing in it, so drawing its area
as ordinary geometry puts something in the picture that nothing in the world holds --
which a camera rendering the world then reports as an object.
"""

from __future__ import annotations

import mujoco
import numpy as np
import pytest
from typing_extensions import Tuple

from semantic_digital_twin.adapters.multi_sim import (
    MujocoSim,
    RegionAppearance,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
    Region,
)

# %% a world holding one thing and one named volume of space

THING_COLOR = Color(1.0, 0.0, 0.0, 1.0)
"""
The colour of the body the world holds.
"""

REGION_COLOR = Color(0.0, 1.0, 0.0, 0.8)
"""
The colour of the region the world names, stated already a little see-through so that
what a region is drawn at is read as a share of its own opacity rather than as a value
of its own.
"""

THING_NAME = "thing"
"""
The name of the body the world holds, which its geom is named after.
"""

REGION_NAME = "named_volume"
"""
The name of the region the world names, which its geom is named after.
"""

RECOLORED = Color(0.0, 0.0, 1.0, 0.5)
"""
A colour nothing in the world states, so that a geom wearing it can only have been
recolored.
"""


@pytest.fixture
def world_with_a_region() -> World:
    """
    A world holding one body and one region, each wearing one box.
    """
    world = World()
    thing = Body(name=PrefixedName(THING_NAME))
    thing.visual = ShapeCollection(
        [Box(scale=Scale(0.1, 0.1, 0.1), color=THING_COLOR)], reference_frame=thing
    )
    region = Region(name=PrefixedName(REGION_NAME))
    region.area = ShapeCollection(
        [Box(scale=Scale(0.2, 0.2, 0.2), color=REGION_COLOR)], reference_frame=region
    )
    with world.modify_world():
        world.add_body(thing)
        world.add_connection(
            FixedConnection(
                parent=thing,
                child=region,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=0.5
                ),
            )
        )
    return world


def built_as(world: World, appearance: RegionAppearance) -> MujocoSim:
    """
    The MuJoCo scene a world builds when its regions are drawn that much.

    :param world: The world to build.
    :param appearance: How much of every region is drawn.
    """
    return MujocoSim(world=world, headless=True, region_appearance=appearance)


def thing_of(world: World) -> KinematicStructureEntity:
    """
    The body the world holds.

    :param world: The world to read.
    """
    return world.get_kinematic_structure_entity_by_name(THING_NAME)


def region_of(world: World) -> KinematicStructureEntity:
    """
    The region the world names.

    :param world: The world to read.
    """
    return world.get_kinematic_structure_entity_by_name(REGION_NAME)


def one_geom_of(scene: MujocoSim, entity: KinematicStructureEntity) -> int:
    """
    The one geom a scene draws the given entity with.

    :param scene: The scene to read.
    :param entity: The body or region the geom hangs on.
    :raises AssertionError: If the scene draws it with any other number of geoms.
    """
    geoms = scene.geoms_of(entity)
    assert len(geoms) == 1, f"expected one geom of {entity.name}, found {len(geoms)}"
    return geoms[0]


def drawn_colors_of(
    scene: MujocoSim, entity: KinematicStructureEntity
) -> Tuple[Tuple[float, ...], ...]:
    """
    The colour the scene draws each of an entity's geoms in.

    :param scene: The scene to read.
    :param entity: The body or region whose geoms are read.
    """
    return tuple(
        tuple(scene.simulator._mj_model.geom_rgba[geom])
        for geom in scene.geoms_of(entity)
    )


# %% what a region is drawn at


def test_a_region_is_drawn_see_through(world_with_a_region: World) -> None:
    """
    A region is drawn at a share of the opacity it states, so what stands inside it is
    seen through it.
    """
    scene = built_as(world_with_a_region, RegionAppearance.TRANSPARENT)
    drawn = scene.simulator._mj_model.geom_rgba[
        one_geom_of(scene, region_of(world_with_a_region))
    ]
    assert drawn[3] == pytest.approx(
        REGION_COLOR.A * RegionAppearance.TRANSPARENT.opacity
    )
    assert np.allclose(drawn[:3], REGION_COLOR.to_rgb())


def test_a_hidden_region_is_not_drawn_at_all(world_with_a_region: World) -> None:
    """
    A region nobody asked to see leaves nothing in the model to be seen.
    """
    scene = built_as(world_with_a_region, RegionAppearance.HIDDEN)
    assert scene.geoms_of(region_of(world_with_a_region)) == ()


def test_a_hidden_region_is_still_a_body_of_the_model(
    world_with_a_region: World,
) -> None:
    """
    Only the drawing of a region is dropped, not the frame it names: what the world
    hangs off a region still has a body to hang off.
    """
    scene = built_as(world_with_a_region, RegionAppearance.HIDDEN)
    assert (
        mujoco.mj_name2id(
            scene.simulator._mj_model, mujoco.mjtObj.mjOBJ_BODY, REGION_NAME
        )
        >= 0
    )


def test_a_thing_keeps_the_opacity_it_states(world_with_a_region: World) -> None:
    """
    Only a region is faded: a body's own geometry is drawn as the world states it,
    however much of a region is drawn.
    """
    for appearance in RegionAppearance:
        scene = built_as(world_with_a_region, appearance)
        assert drawn_colors_of(scene, thing_of(world_with_a_region)) == (
            THING_COLOR.to_rgba(),
        )


# %% drawing one entity in another colour


def test_recoloring_an_entity_changes_every_geom_of_it(
    world_with_a_region: World,
) -> None:
    """
    A recolored entity is drawn in the colour it was given, opacity and all.
    """
    scene = built_as(world_with_a_region, RegionAppearance.TRANSPARENT)
    scene.recolor(thing_of(world_with_a_region), RECOLORED)
    assert drawn_colors_of(scene, thing_of(world_with_a_region)) == (
        RECOLORED.to_rgba(),
    )


def test_recoloring_an_entity_leaves_every_other_one_alone(
    world_with_a_region: World,
) -> None:
    """
    Recoloring singles one entity out: nothing else the scene draws changes.
    """
    scene = built_as(world_with_a_region, RegionAppearance.TRANSPARENT)
    before = drawn_colors_of(scene, region_of(world_with_a_region))
    scene.recolor(thing_of(world_with_a_region), RECOLORED)
    assert drawn_colors_of(scene, region_of(world_with_a_region)) == before


def test_recoloring_does_not_change_the_world_the_scene_mirrors(
    world_with_a_region: World,
) -> None:
    """
    Only the drawing changes: the twin keeps the colour it states, so the same world
    renders unchanged into the next scene built from it.
    """
    scene = built_as(world_with_a_region, RegionAppearance.TRANSPARENT)
    scene.recolor(thing_of(world_with_a_region), RECOLORED)
    assert [shape.color for shape in thing_of(world_with_a_region).visual] == [
        THING_COLOR
    ]
