"""
How much of a region a simulator draws.

A region names a volume of space rather than a thing standing in it, so drawing its area
as ordinary geometry puts something in the picture that nothing in the world holds --
which a camera rendering the world then reports as an object.
"""

from __future__ import annotations

import os
import tempfile

import mujoco
import numpy as np
import pytest
from typing_extensions import Iterator, Tuple

from semantic_digital_twin.adapters.multi_sim import (
    MujocoBuilder,
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
from semantic_digital_twin.world_description.world_entity import Body, Region

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


def built_as(world: World, appearance: RegionAppearance) -> mujoco.MjModel:
    """
    The MuJoCo model a world builds when its regions are drawn that much.

    :param world: The world to build.
    :param appearance: How much of every region is drawn.
    """
    with tempfile.TemporaryDirectory() as directory:
        scene = os.path.join(directory, "scene.xml")
        MujocoBuilder(region_appearance=appearance).build_world(
            world=world, file_path=scene
        )
        return mujoco.MjModel.from_xml_path(scene)


def geoms_of(model: mujoco.MjModel, name: str) -> Tuple[int, ...]:
    """
    The geoms a model draws the named entity with.

    :param model: The model to read.
    :param name: The name of the body or region the geoms hang on.
    """
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    return tuple(geom for geom in range(model.ngeom) if model.geom_bodyid[geom] == body)


def one_geom_of(model: mujoco.MjModel, name: str) -> int:
    """
    The one geom a model draws the named entity with.

    :param model: The model to read.
    :param name: The name of the body or region the geom hangs on.
    :raises AssertionError: If the model draws it with any other number of geoms.
    """
    geoms = geoms_of(model, name)
    assert len(geoms) == 1, f"expected one geom of {name}, found {len(geoms)}"
    return geoms[0]


# %% what a region is drawn at


def test_a_region_is_drawn_see_through(world_with_a_region: World) -> None:
    """
    A region is drawn at a share of the opacity it states, so what stands inside it is
    seen through it.
    """
    model = built_as(world_with_a_region, RegionAppearance.TRANSPARENT)
    drawn = model.geom_rgba[one_geom_of(model, REGION_NAME)]
    assert drawn[3] == pytest.approx(
        REGION_COLOR.A * RegionAppearance.TRANSPARENT.opacity
    )
    assert np.allclose(drawn[:3], REGION_COLOR.to_rgb())


def test_a_hidden_region_is_not_drawn_at_all(world_with_a_region: World) -> None:
    """
    A region nobody asked to see leaves nothing in the model to be seen.
    """
    model = built_as(world_with_a_region, RegionAppearance.HIDDEN)
    assert geoms_of(model, REGION_NAME) == ()


def test_a_hidden_region_is_still_a_body_of_the_model(
    world_with_a_region: World,
) -> None:
    """
    Only the drawing of a region is dropped, not the frame it names: what the world
    hangs off a region still has a body to hang off.
    """
    model = built_as(world_with_a_region, RegionAppearance.HIDDEN)
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, REGION_NAME) >= 0


def test_a_thing_keeps_the_opacity_it_states(world_with_a_region: World) -> None:
    """
    Only a region is faded: a body's own geometry is drawn as the world states it,
    however much of a region is drawn.
    """
    for appearance in RegionAppearance:
        model = built_as(world_with_a_region, appearance)
        assert np.allclose(
            model.geom_rgba[one_geom_of(model, THING_NAME)], THING_COLOR.to_rgba()
        )
