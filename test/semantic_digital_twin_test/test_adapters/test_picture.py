"""
A picture of a world drawn from the geometry it states: what is drawn where, in which
colour, and which pixel shows what.
"""

from __future__ import annotations

import os
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest

from semantic_digital_twin.adapters.multi_sim import (
    MUJOCO_RENDERING_BACKEND_VARIABLE,
    MujocoCamera,
    MujocoRenderingBackend,
    MujocoSim,
    RegionAppearance,
)
from semantic_digital_twin.adapters.picture import (
    EGL_DEVICE_VARIABLE,
    NOTHING_SHOWN,
    OFFSCREEN_PLATFORM_VARIABLE,
    AsStated,
    OffscreenPlatform,
    Lighting,
    Recolored,
    Softened,
    is_uncolored,
    Viewpoint,
    IndexPaint,
    WorldPicture,
    stated_color_of,
)
from pyrender.platforms.egl import query_devices
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.geometry import Box, Color, Mesh, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Region

# %% a world with a box in front of a slab

NEAR_NAME = "near_box"
"""
The name of the box standing nearest the camera.
"""

FAR_NAME = "far_slab"
"""
The name of the slab standing behind it, wide enough to fill the picture.
"""

REGION_NAME = "around_the_box"
"""
The name of the region drawn around the near box.
"""

NEAR_COLOR = Color(1.0, 0.0, 0.0, 1.0)
"""
What the near box states it looks like.
"""

FAR_COLOR = Color(0.0, 0.0, 1.0, 1.0)
"""
What the far slab states it looks like.
"""

REGION_COLOR = Color(0.0, 1.0, 0.0, 1.0)
"""
What the region states it looks like.
"""

RECOLORED = Color(1.0, 1.0, 0.0, 1.0)
"""
A colour nothing in the world states.
"""

SEE_THROUGH = Color(1.0, 1.0, 0.0, 0.5)
"""
A colour that leaves what stands behind it showing.
"""

PICTURE_WIDTH = 160
"""
Width of the pictures these tests draw, in pixels.
"""

PICTURE_HEIGHT = 120
"""
Height of the pictures these tests draw, in pixels.
"""


def box_named(name: str, size: float, color: Color) -> Body:
    """
    A body seen as one box.

    :param name: What the body is called.
    :param size: The box's edge, in metres.
    :param color: What it looks like.
    """
    body = Body(name=PrefixedName(name))
    body.visual = ShapeCollection(
        [Box(scale=Scale(size, size, size), color=color)], reference_frame=body
    )
    return body


@pytest.fixture
def world_with_a_box_before_a_slab() -> World:
    """
    A small box standing a metre in front of a wide slab, with a region drawn around the
    box.
    """
    world = World()
    near = box_named(NEAR_NAME, 0.2, NEAR_COLOR)
    far = box_named(FAR_NAME, 4.0, FAR_COLOR)
    region = Region(name=PrefixedName(REGION_NAME))
    region.area = ShapeCollection(
        [Box(scale=Scale(0.4, 0.4, 0.4), color=REGION_COLOR)], reference_frame=region
    )
    with world.modify_world():
        world.add_body(near)
        world.add_connection(
            FixedConnection(
                parent=near,
                child=far,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-3.0
                ),
            )
        )
        world.add_connection(
            FixedConnection(
                parent=near,
                child=region,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(),
            )
        )
    return world


def looking_at_the_box() -> Viewpoint:
    """
    A viewpoint a metre in front of the near box, looking straight at it.
    """
    return Viewpoint.looking_from(
        position=(1.0, 0.0, 0.0),
        at=(0.0, 0.0, 0.0),
        field_of_view=60.0,
        width=PICTURE_WIDTH,
        height=PICTURE_HEIGHT,
    )


def named(world: World, name: str) -> Body:
    """
    One of the world's bodies.

    :param world: The world to read.
    :param name: What the body is called.
    """
    return world.get_body_by_name(name)


def middle_of(mask: np.ndarray) -> bool:
    """
    Whether a mask covers the middle pixel of the picture.

    :param mask: The mask to read.
    """
    return bool(mask[PICTURE_HEIGHT // 2, PICTURE_WIDTH // 2])


# %% what each pixel shows


def test_the_nearest_thing_is_what_a_pixel_shows(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    The box stands in front of the slab, so the middle of the picture shows the box and
    the corners, which the box does not reach, show the slab.
    """
    picture = WorldPicture(world=world_with_a_box_before_a_slab).taken_from(
        looking_at_the_box()
    )
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    far = named(world_with_a_box_before_a_slab, FAR_NAME)
    assert middle_of(picture.mask_of(near))
    assert not middle_of(picture.mask_of(far))
    assert picture.mask_of(far)[0, 0]
    assert picture.entities == (near, far)


def test_a_pixel_showing_nothing_says_so_and_wears_the_background(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    Looking away from everything, the picture shows nothing anywhere: no entity, no
    depth, and the background colour.
    """
    background = Color(0.0, 0.0, 0.0, 1.0)
    picture = WorldPicture(
        world=world_with_a_box_before_a_slab, background=background
    ).taken_from(
        Viewpoint.looking_from(
            position=(1.0, 0.0, 0.0),
            at=(2.0, 0.0, 0.0),
            width=PICTURE_WIDTH,
            height=PICTURE_HEIGHT,
        )
    )
    assert np.all(picture.shown == NOTHING_SHOWN)
    assert np.all(picture.depth == 0.0)
    assert np.all(picture.colors == 0)


def test_a_thing_the_picture_was_not_drawn_of_is_nowhere_in_it(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    A region hidden from the picture has an empty mask rather than being looked up in a
    picture that never held it.
    """
    picture = WorldPicture(world=world_with_a_box_before_a_slab).taken_from(
        looking_at_the_box()
    )
    region = world_with_a_box_before_a_slab.get_kinematic_structure_entity_by_name(
        REGION_NAME
    )
    assert not np.any(picture.mask_of(region))


def test_the_depth_is_the_distance_to_what_the_pixel_shows(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    The camera stands a metre from the box's centre, so the middle pixel is 0.9 m from
    its near face.
    """
    picture = WorldPicture(world=world_with_a_box_before_a_slab).taken_from(
        looking_at_the_box()
    )
    assert picture.depth[PICTURE_HEIGHT // 2, PICTURE_WIDTH // 2] == pytest.approx(
        0.9, abs=1e-3
    )


# %% see-through things


def test_a_see_through_thing_is_found_where_it_is_nearest_and_so_is_what_it_covers(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    A region drawn see-through around the box covers the middle of the picture, and the
    box behind it is still found there rather than hidden by it.
    """
    picture = WorldPicture(
        world=world_with_a_box_before_a_slab,
        region_appearance=RegionAppearance.TRANSPARENT,
    ).taken_from(looking_at_the_box())
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    region = world_with_a_box_before_a_slab.get_kinematic_structure_entity_by_name(
        REGION_NAME
    )
    assert middle_of(picture.mask_of(region))
    assert middle_of(picture.mask_of(near))
    assert picture.entities == (
        near,
        named(world_with_a_box_before_a_slab, FAR_NAME),
        region,
    )


def test_what_stands_behind_a_see_through_thing_shows_through_it(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    The box recoloured half see-through leaves the blue slab tinting the middle of the
    picture, where a solid box would leave none of the slab's blue.
    """
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    see_through = WorldPicture(
        world=world_with_a_box_before_a_slab,
        appearance=Recolored({near: SEE_THROUGH}),
    ).taken_from(looking_at_the_box())
    solid = WorldPicture(
        world=world_with_a_box_before_a_slab,
        appearance=Recolored({near: RECOLORED}),
    ).taken_from(looking_at_the_box())
    middle = (PICTURE_HEIGHT // 2, PICTURE_WIDTH // 2)
    assert see_through.colors[middle][2] > solid.colors[middle][2]


# %% what each thing is drawn in


def test_a_recoloured_thing_is_drawn_in_its_colour_and_the_rest_as_stated(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    The recolouring reaches the picture: the middle pixel, showing the box, is the
    recolouring's hue and a corner, showing the slab, is the slab's own.
    """
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    picture = WorldPicture(
        world=world_with_a_box_before_a_slab,
        appearance=Recolored({near: RECOLORED}),
        lighting=Lighting(ambient=1.0, lights=()),
    ).taken_from(looking_at_the_box())
    middle = picture.colors[PICTURE_HEIGHT // 2, PICTURE_WIDTH // 2]
    corner = picture.colors[0, 0]
    assert tuple(middle) == pytest.approx(
        tuple(np.array(RECOLORED.to_rgb()) * 255), abs=2
    )
    assert tuple(corner) == pytest.approx(
        tuple(np.array(FAR_COLOR.to_rgb()) * 255), abs=2
    )


def test_recolouring_a_picture_leaves_the_world_as_it_was(
    world_with_a_box_before_a_slab: World,
) -> None:
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    WorldPicture(
        world=world_with_a_box_before_a_slab, appearance=Recolored({near: RECOLORED})
    ).taken_from(looking_at_the_box())
    assert [shape.color for shape in near.visual.shapes] == [NEAR_COLOR]


def test_a_softened_picture_draws_each_stated_colour_softened(
    world_with_a_box_before_a_slab: World,
) -> None:
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    softened = Softened()
    assert softened.color_of(near, near.visual.shapes[0]) == NEAR_COLOR.softened()


def test_a_mesh_carrying_its_own_colours_is_not_softened(tmp_path: Path) -> None:
    """
    A mesh file states its own colours, which a softening leaves as the file has them;
    only a colour the world states for the mesh is softened.
    """
    mesh_file = tmp_path / "part.stl"
    Box(scale=Scale(0.1, 0.1, 0.1)).mesh.export(str(mesh_file))
    as_the_file_has_it = Mesh(filename=str(mesh_file))
    stated = Mesh(filename=str(mesh_file), color=NEAR_COLOR)
    body = Body(name=PrefixedName("part"))
    assert stated_color_of(as_the_file_has_it) is None
    assert Softened().color_of(body, as_the_file_has_it) is None
    assert Softened().color_of(body, stated) == NEAR_COLOR.softened()


def test_a_mesh_nothing_colours_is_drawn_in_the_colour_given_for_one(
    tmp_path: Path,
) -> None:
    """
    A mesh out of a file that states no colours, which the world leaves at the default
    colour too, is drawn in the colour a softening is given for such a mesh, as it is; a
    mesh the world colours is not.
    """
    mesh_file = tmp_path / "part.stl"
    Box(scale=Scale(0.1, 0.1, 0.1)).mesh.export(str(mesh_file))
    uncolored = Mesh(filename=str(mesh_file))
    stated = Mesh(filename=str(mesh_file), color=NEAR_COLOR)
    body = Body(name=PrefixedName("part"))
    softened = Softened(uncolored=FAR_COLOR)
    assert is_uncolored(uncolored)
    assert not is_uncolored(stated)
    assert softened.color_of(body, uncolored) == FAR_COLOR
    assert softened.color_of(body, stated) == NEAR_COLOR.softened()


def test_as_stated_draws_nothing_differently(
    world_with_a_box_before_a_slab: World,
) -> None:
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    assert AsStated().color_of(near, near.visual.shapes[0]) is None


# %% a held piece is drawn where it hangs


def test_a_piece_hung_below_a_body_is_drawn_where_it_hangs(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    A piece held in a gripper hangs below the gripper's body on a free connection; the
    picture draws it where the connection puts it, which no simulation of the world
    would allow.
    """
    world = world_with_a_box_before_a_slab
    near = named(world, NEAR_NAME)
    held = box_named("held", 0.1, RECOLORED)
    with world.modify_world():
        world.add_connection(
            Connection6DoF.create_with_dofs(world=world, parent=near, child=held)
        )
    held.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=0.5, reference_frame=near
    )
    picture = WorldPicture(world=world).taken_from(looking_at_the_box())
    assert middle_of(picture.mask_of(held))
    assert picture.depth[PICTURE_HEIGHT // 2, PICTURE_WIDTH // 2] == pytest.approx(
        0.45, abs=1e-3
    )


# %% where things fall in the picture


def test_a_point_in_front_of_the_camera_falls_in_the_middle_of_the_picture() -> None:
    viewpoint = looking_at_the_box()
    [pixel] = viewpoint.project(np.array([[0.0, 0.0, 0.0]]))
    assert pixel == pytest.approx([PICTURE_WIDTH / 2, PICTURE_HEIGHT / 2])


def test_a_point_to_the_left_and_above_falls_left_of_and_above_the_middle() -> None:
    """
    Looking down negative x from a metre out, the world's negative y is to the left of
    the picture and its positive z up it.
    """
    viewpoint = looking_at_the_box()
    [pixel] = viewpoint.project(np.array([[0.0, -0.2, 0.2]]))
    assert pixel[0] < PICTURE_WIDTH / 2
    assert pixel[1] < PICTURE_HEIGHT / 2


def test_a_projected_point_lands_on_the_thing_it_is_the_middle_of(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    The projection agrees with the drawing: the box's centre projects onto a pixel that
    shows the box.
    """
    viewpoint = Viewpoint.looking_from(
        position=(1.0, 0.4, 0.3),
        at=(0.0, 0.0, 0.0),
        width=PICTURE_WIDTH,
        height=PICTURE_HEIGHT,
    )
    picture = WorldPicture(world=world_with_a_box_before_a_slab).taken_from(viewpoint)
    near = named(world_with_a_box_before_a_slab, NEAR_NAME)
    [pixel] = viewpoint.project(np.array([[0.0, 0.0, 0.0]]))
    column, row = np.round(pixel).astype(int)
    assert picture.mask_of(near)[row, column]


def test_a_stated_camera_is_looked_through_where_its_body_stands(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    A camera the world hangs on a body stands where the body stands, turned as the
    camera is turned on it.
    """
    far = named(world_with_a_box_before_a_slab, FAR_NAME)
    camera = MujocoCamera(
        name="stated",
        body=far,
        position=[0.1, 0.0, 0.0],
        quaternion=[1.0, 0.0, 0.0, 0.0],
        fovy=30.0,
        resolution=[PICTURE_WIDTH, PICTURE_HEIGHT],
    )
    viewpoint = Viewpoint.through(camera, world_with_a_box_before_a_slab)
    assert viewpoint.pose[:3, 3] == pytest.approx([-2.9, 0.0, 0.0])
    assert viewpoint.pose[:3, :3] == pytest.approx(np.eye(3))
    assert viewpoint.field_of_view == camera.fovy
    assert (viewpoint.width, viewpoint.height) == (PICTURE_WIDTH, PICTURE_HEIGHT)


# %% the device the picture is drawn on


@pytest.mark.skipif(
    os.environ.get(OFFSCREEN_PLATFORM_VARIABLE) != OffscreenPlatform.EGL,
    reason="only a run drawing through EGL picks a device",
)
def test_a_picture_names_the_device_it_was_drawn_on(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    Once a picture is drawn, the device the drawing library was told to draw on is one
    of the devices the machine lists.
    """
    WorldPicture(world=world_with_a_box_before_a_slab).taken_from(looking_at_the_box())
    named = int(os.environ[EGL_DEVICE_VARIABLE])
    assert 0 <= named < len(query_devices())


def test_pictures_of_two_sizes_come_out_at_their_sizes(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    One renderer draws every picture of the process, resized to each.
    """
    taken = WorldPicture(world=world_with_a_box_before_a_slab)
    small = taken.taken_from(looking_at_the_box())
    large = taken.taken_from(
        Viewpoint.looking_from(
            position=(1.0, 0.0, 0.0),
            at=(0.0, 0.0, 0.0),
            width=2 * PICTURE_WIDTH,
            height=2 * PICTURE_HEIGHT,
        )
    )
    assert small.colors.shape == (PICTURE_HEIGHT, PICTURE_WIDTH, 3)
    assert large.colors.shape == (2 * PICTURE_HEIGHT, 2 * PICTURE_WIDTH, 3)
    assert (
        large.depth.shape
        == large.shown.shape
        == (2 * PICTURE_HEIGHT, 2 * PICTURE_WIDTH)
    )


@pytest.mark.skipif(
    os.environ.get(MUJOCO_RENDERING_BACKEND_VARIABLE) != MujocoRenderingBackend.EGL,
    reason="only a run whose simulator draws through EGL shares a display with the pictures",
)
def test_a_simulator_still_draws_after_a_picture_was_taken(
    world_with_a_box_before_a_slab: World,
) -> None:
    """
    A picture and a simulator draw on the same device, so a picture must leave the
    device's display, which the simulator opened first, standing for the simulator's
    next render.
    """

    def captured_by_a_simulator() -> np.ndarray:
        scene = MujocoSim(world=world_with_a_box_before_a_slab, headless=True)
        scene.simulator.start(simulate_in_thread=False, render_in_thread=False)
        try:
            return scene.simulator.capture_rgb(
                height=PICTURE_HEIGHT, width=PICTURE_WIDTH
            ).result
        finally:
            scene.stop_simulation()

    before = captured_by_a_simulator()
    WorldPicture(world=world_with_a_box_before_a_slab).taken_from(looking_at_the_box())
    after = captured_by_a_simulator()
    assert np.array_equal(after, before)


# %% the picture as a file


def test_a_written_picture_is_the_picture(
    world_with_a_box_before_a_slab: World, tmp_path: Path
) -> None:
    picture = WorldPicture(world=world_with_a_box_before_a_slab).taken_from(
        looking_at_the_box()
    )
    written = picture.write(tmp_path / "pictures" / "box.png")
    assert np.array_equal(imageio.imread(written), picture.colors)


# %% indices written as colours


@pytest.mark.parametrize("count", [1, 255, 256, 65535])
def test_every_index_painted_as_a_colour_is_read_back(count: int) -> None:
    paint = IndexPaint(count=count)
    indices = np.arange(0, count + 1)
    painted = np.array([[paint.color_of(index) for index in indices]], dtype=np.uint8)
    assert np.array_equal(paint.indices_of(painted)[0], indices)


@pytest.mark.parametrize("count", [255, 65535])
def test_the_average_of_two_colours_reads_as_nobodys(count: int) -> None:
    """
    A pixel on the edge between two things holds the average of their colours, which
    must not read as a third thing.
    """
    paint = IndexPaint(count=count)
    first = np.array(paint.color_of(1), dtype=float)
    second = np.array(paint.color_of(count), dtype=float)
    averaged = np.array([[np.round((first + second) / 2)]], dtype=np.uint8)
    assert paint.indices_of(averaged)[0, 0] == 0
