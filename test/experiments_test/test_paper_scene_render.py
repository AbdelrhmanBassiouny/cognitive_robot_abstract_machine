"""
Picking an answer out of the twin: the things a query answered drawn in one colour and
everything else faded behind them, which is what a reader of the paper is shown beside
the query.

The colouring is asserted off the scene the render builds, which needs no graphics at
all; only the two tests that actually draw a picture need a backend that can render with
no window, and those are skipped where the run named none.
"""

from __future__ import annotations

import os
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest
from typing_extensions import Tuple

from experiments.paper.scene import (
    NothingToDrawError,
    PointOfView,
    SceneRender,
)
from semantic_digital_twin.adapters.multi_sim import (
    MUJOCO_RENDERING_BACKEND_VARIABLE,
    MujocoRenderingBackend,
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
from semantic_digital_twin.world_description.world_entity import Body

# %% what this test needs to be there


def can_draw_without_a_screen() -> bool:
    """
    Whether this run named a backend MuJoCo can draw offscreen through.

    MuJoCo locks its backend at the moment it is imported, so a run that has to draw
    without a window names one in the environment it starts from; a run that named none
    falls back to the windowed backend and aborts the render.
    """
    return os.environ.get(MUJOCO_RENDERING_BACKEND_VARIABLE, "").lower() in tuple(
        MujocoRenderingBackend
    )


needs_a_renderer = pytest.mark.skipif(
    not can_draw_without_a_screen(),
    reason="%s names no offscreen backend, so nothing can be drawn"
    % MUJOCO_RENDERING_BACKEND_VARIABLE,
)

# %% a scene with two things standing in it

ANSWERED_NAME = "answered_thing"
"""
The name of the body a query's answer names.
"""

OTHER_NAME = "other_thing"
"""
The name of the body standing beside it, which the same answer does not name.
"""

STATED_COLOR = Color(0.2, 0.4, 0.9, 1.0)
"""
The colour both bodies state in the twin, so that a drawn colour matching neither the
highlight nor the fade is recognizably the one the render left alone.
"""

HIGHLIGHT = Color(1.0, 0.0, 0.0, 1.0)
"""
The colour this test's renders pick an answer out in.
"""

FADED = Color(0.0, 1.0, 0.0, 0.2)
"""
The colour this test's renders draw everything else in.
"""


def standing_box(name: str) -> Body:
    """
    One box of the scene, worn as both what is seen of it and what it takes up.

    It takes up space as well as being seen because the camera a render places itself is
    framed around what the world's bodies occupy.

    :param name: What the body is called.
    """
    body = Body(name=PrefixedName(name))
    box = Box(scale=Scale(0.2, 0.2, 0.2), color=STATED_COLOR)
    body.visual = ShapeCollection([box], reference_frame=body)
    body.collision = ShapeCollection([box], reference_frame=body)
    return body


@pytest.fixture
def scene_with_two_things() -> World:
    """
    A world holding two boxes a little apart, one of which an answer names.
    """
    world = World()
    answered = standing_box(ANSWERED_NAME)
    other = standing_box(OTHER_NAME)
    with world.modify_world():
        world.add_body(answered)
        world.add_connection(
            FixedConnection(
                parent=answered,
                child=other,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.5
                ),
            )
        )
    return world


def render_of(world: World) -> SceneRender:
    """
    The render this test picks answers out with.

    :param world: The world it draws.
    """
    return SceneRender(world=world, highlight=HIGHLIGHT, faded=FADED)


def body_named(world: World, name: str) -> Body:
    """
    One of the world's two bodies.

    :param world: The world to read.
    :param name: Which body is wanted.
    """
    return world.get_body_by_name(name)


def drawn_colors_of(scene: MujocoSim, body: Body) -> Tuple[Tuple[float, ...], ...]:
    """
    The colour the scene draws each of a body's geoms in.

    :param scene: The scene to read.
    :param body: The body whose geoms are read.
    """
    return tuple(
        tuple(scene.simulator._mj_model.geom_rgba[geom])
        for geom in scene.geoms_of(body)
    )


# %% which things a picture picks out


def test_the_answer_is_drawn_in_the_highlight_colour(
    scene_with_two_things: World,
) -> None:
    """
    Every geom of a body the answer names is drawn in the highlight.
    """
    scene = MujocoSim(
        world=scene_with_two_things,
        headless=True,
        region_appearance=RegionAppearance.TRANSPARENT,
    )
    answered = body_named(scene_with_two_things, ANSWERED_NAME)
    render_of(scene_with_two_things).pick_out(scene, [answered])
    assert drawn_colors_of(scene, answered) == (HIGHLIGHT.to_rgba(),)


def test_everything_the_answer_does_not_name_is_faded(
    scene_with_two_things: World,
) -> None:
    """
    A body the answer leaves out is drawn in the fade, whatever colour it states.
    """
    scene = MujocoSim(
        world=scene_with_two_things,
        headless=True,
        region_appearance=RegionAppearance.TRANSPARENT,
    )
    answered = body_named(scene_with_two_things, ANSWERED_NAME)
    render_of(scene_with_two_things).pick_out(scene, [answered])
    assert drawn_colors_of(scene, body_named(scene_with_two_things, OTHER_NAME)) == (
        FADED.to_rgba(),
    )


def test_an_answer_naming_nothing_fades_the_whole_scene(
    scene_with_two_things: World,
) -> None:
    """
    A query nothing in the twin answers leaves a picture with nothing picked out of it,
    rather than one drawn as though every body were the answer.
    """
    scene = MujocoSim(
        world=scene_with_two_things,
        headless=True,
        region_appearance=RegionAppearance.TRANSPARENT,
    )
    render_of(scene_with_two_things).pick_out(scene, [])
    for name in (ANSWERED_NAME, OTHER_NAME):
        assert drawn_colors_of(scene, body_named(scene_with_two_things, name)) == (
            FADED.to_rgba(),
        )


def test_picking_an_answer_out_leaves_the_twin_alone(
    scene_with_two_things: World,
) -> None:
    """
    Only the drawing is recoloured: the bodies keep the colour the twin states, so the
    next query over the same world is not answered against a recoloured scene.
    """
    scene = MujocoSim(
        world=scene_with_two_things,
        headless=True,
        region_appearance=RegionAppearance.TRANSPARENT,
    )
    answered = body_named(scene_with_two_things, ANSWERED_NAME)
    render_of(scene_with_two_things).pick_out(scene, [answered])
    assert [shape.color for shape in answered.visual] == [STATED_COLOR]


# %% asking for a picture of nothing


def test_a_world_holding_no_geometry_cannot_be_framed() -> None:
    """
    An overview camera is placed around what the world holds, so a world holding nothing
    says so rather than drawing an empty picture from an arbitrary place.
    """
    with pytest.raises(NothingToDrawError):
        SceneRender(world=World()).of([])


# %% the picture itself


@needs_a_renderer
def test_the_written_picture_holds_more_than_one_colour(
    scene_with_two_things: World, tmp_path: Path
) -> None:
    """
    The picture that is written is a drawing of the scene: it holds the highlight, the
    fade and the background, not the one flat colour a failed render would leave.
    """
    written = (
        render_of(scene_with_two_things)
        .of([body_named(scene_with_two_things, ANSWERED_NAME)])
        .write(tmp_path / "scene.png")
    )
    assert written.is_file()
    drawn = imageio.imread(written)
    assert len(np.unique(drawn.reshape(-1, drawn.shape[-1]), axis=0)) > 1


@needs_a_renderer
def test_the_answer_is_visible_in_the_picture_that_was_drawn(
    scene_with_two_things: World,
) -> None:
    """
    The highlight reaches the picture rather than only the model: the body the answer
    names is drawn, in the colour it was picked out in.
    """
    drawn = render_of(scene_with_two_things).of(
        [body_named(scene_with_two_things, ANSWERED_NAME)]
    )
    assert drawn.holds(HIGHLIGHT)


@needs_a_renderer
def test_a_picture_taken_from_a_body_sees_what_stands_in_front_of_it(
    scene_with_two_things: World,
) -> None:
    """
    A spatial question is asked from somewhere, so its picture is taken from that body's
    own frame: what the picture shows is what stands in front of the looker, which the
    body it looks from does not.
    """
    looker = body_named(scene_with_two_things, ANSWERED_NAME)
    seen = body_named(scene_with_two_things, OTHER_NAME)
    drawn = SceneRender(
        world=scene_with_two_things,
        camera=PointOfView(body=looker).camera(),
        highlight=HIGHLIGHT,
        faded=FADED,
    ).of([seen])
    assert drawn.holds(HIGHLIGHT)
