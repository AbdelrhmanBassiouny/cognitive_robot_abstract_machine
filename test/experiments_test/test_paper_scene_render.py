"""
Picking an answer out of the twin: the things a query answered drawn in one colour out
of the scene as the twin states it, which is what a reader of the paper is shown beside
the query.

The colouring is asserted off the scene the render builds, which needs no graphics at
all; only the two tests that actually draw a picture need a backend that can render with
no window, and those are skipped where the run named none.
"""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest
from coraplex.datastructures.enums import ExecutionType
from typing_extensions import Tuple

from experiments.episodes.episode import Episode, RecordedTrial
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.episodes.recording import open_recording
from experiments.montessori.results_database import ResultsDatabase
from experiments.paper.labels import LABEL_COLOR
from experiments.paper.scene import (
    LOOKING_CLOSELY,
    NothingToDrawError,
    PointOfView,
    SceneRender,
)
from semantic_digital_twin.adapters.multi_sim import (
    GeomVisibilityAndCollisionType,
    MujocoLight,
    MujocoSim,
    MultiSimLight,
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

from experiments.scenarios.trial import TrialOutcome

from .offscreen_rendering import needs_a_renderer

# %% what this test needs to be there

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


def lights_of(world: World) -> list:
    """
    Every light the world itself states.

    :param world: The world to read.
    """
    return [
        stated
        for entity in world.kinematic_structure_entities
        for stated in entity.simulator_additional_properties
        if isinstance(stated, MultiSimLight)
    ]


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


def test_a_body_the_answer_leaves_out_keeps_the_colour_the_twin_states(
    scene_with_two_things: World,
) -> None:
    """
    Told nothing about a fade, a render draws the scene as the twin states it, so a
    reader sees the robot and the table in their own colours with only the answer
    recoloured.
    """
    scene = MujocoSim(
        world=scene_with_two_things,
        headless=True,
        region_appearance=RegionAppearance.TRANSPARENT,
    )
    answered = body_named(scene_with_two_things, ANSWERED_NAME)
    SceneRender(world=scene_with_two_things, highlight=HIGHLIGHT).pick_out(
        scene, [answered]
    )
    assert drawn_colors_of(scene, body_named(scene_with_two_things, OTHER_NAME)) == (
        STATED_COLOR.to_rgba(),
    )


def test_everything_the_answer_does_not_name_is_faded_when_a_fade_is_asked_for(
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


# %% a body the twin states no visual geometry for


@pytest.fixture
def scene_of_shapes_only_collided_with() -> World:
    """
    A world whose two bodies wear a shape they take up space with and none they are seen
    with, which is how the scene the frozen question set is asked of states its objects.
    """
    world = World()
    bodies = []
    for name in (ANSWERED_NAME, OTHER_NAME):
        body = Body(name=PrefixedName(name))
        body.collision = ShapeCollection(
            [Box(scale=Scale(0.2, 0.2, 0.2), color=STATED_COLOR)], reference_frame=body
        )
        bodies.append(body)
    with world.modify_world():
        world.add_body(bodies[0])
        world.add_connection(
            FixedConnection(
                parent=bodies[0],
                child=bodies[1],
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.5
                ),
            )
        )
    return world


@needs_a_renderer
def test_an_answer_the_twin_only_collides_with_is_still_drawn(
    scene_of_shapes_only_collided_with: World,
) -> None:
    """
    A card whose answer is not drawn says nothing, so a body the twin states no visual
    geometry for is drawn with the geometry it takes up space with.
    """
    drawn = render_of(scene_of_shapes_only_collided_with).of(
        [body_named(scene_of_shapes_only_collided_with, ANSWERED_NAME)]
    )
    assert drawn.holds(HIGHLIGHT)


def test_what_the_answer_stands_among_is_drawn_too(
    scene_of_shapes_only_collided_with: World,
) -> None:
    """
    An answer drawn alone in an empty picture says where nothing is, so every body of
    the scene is put in a group a renderer draws, not only the ones the answer names.
    """
    scene = MujocoSim(
        world=scene_of_shapes_only_collided_with,
        headless=True,
        region_appearance=RegionAppearance.TRANSPARENT,
    )
    render_of(scene_of_shapes_only_collided_with).pick_out(
        scene, [body_named(scene_of_shapes_only_collided_with, ANSWERED_NAME)]
    )
    assert all(
        GeomVisibilityAndCollisionType(
            scene.simulator._mj_model.geom_group[geom]
        ).is_drawn
        for entity in scene_of_shapes_only_collided_with.kinematic_structure_entities
        for geom in scene.geoms_of(entity)
    )


# %% lighting the scene


def test_a_world_stating_no_light_is_lit_for_the_picture(
    scene_with_two_things: World,
) -> None:
    """
    A scene nothing lights renders black, so a render that has to place its own camera
    places a light too.
    """
    render_of(scene_with_two_things).of(
        [body_named(scene_with_two_things, ANSWERED_NAME)]
    )
    assert lights_of(scene_with_two_things) == []


def test_a_world_stating_its_own_light_is_left_alone(
    scene_with_two_things: World,
) -> None:
    """
    A world that says how it is lit keeps its own lighting, rather than being lit twice.
    """
    stated = MujocoLight(name="stated_light", body=scene_with_two_things.root)
    scene_with_two_things.root.simulator_additional_properties.append(stated)
    render_of(scene_with_two_things).of(
        [body_named(scene_with_two_things, ANSWERED_NAME)]
    )
    assert lights_of(scene_with_two_things) == [stated]


def test_a_lit_picture_is_brighter_than_an_unlit_one(
    scene_with_two_things: World,
) -> None:
    """
    The light is what makes the answer readable: the same scene rendered without one is
    darker than the same scene rendered with the one the render places.
    """
    answers = [body_named(scene_with_two_things, ANSWERED_NAME)]
    lit = render_of(scene_with_two_things).of(answers)
    scene_with_two_things.root.simulator_additional_properties.append(
        MujocoLight(
            name="feeble_light",
            body=scene_with_two_things.root,
            diffuse=[0.0, 0.0, 0.0],
            specular=[0.0, 0.0, 0.0],
        )
    )
    unlit = render_of(scene_with_two_things).of(answers)
    assert lit.image.mean() > unlit.image.mean()


def test_a_drawn_picture_leaves_no_callback_on_the_world(
    scene_with_two_things: World,
) -> None:
    """
    The scene a picture is drawn from is told about every change of the world through a
    callback, and the render tears the scene down once the picture is taken; a callback
    left behind would keep the scene, and its compiled model, alive for as long as the
    world is, once per picture.
    """
    before = list(scene_with_two_things.state.state_change_callbacks)

    render_of(scene_with_two_things).of(
        [body_named(scene_with_two_things, ANSWERED_NAME)]
    )

    assert scene_with_two_things.state.state_change_callbacks == before


# %% drawing without shadows

FLOOR_NAME = "floor"
"""
The name of the slab the two things stand over, which is where their shadows would fall.
"""


@pytest.fixture
def scene_over_a_floor(scene_with_two_things: World) -> World:
    """
    The two things a little above a wide slab, so a light casting shadows darkens the
    slab beneath them.
    """
    floor = Body(name=PrefixedName(FLOOR_NAME))
    slab = Box(scale=Scale(3.0, 3.0, 0.02), color=STATED_COLOR)
    floor.visual = ShapeCollection([slab], reference_frame=floor)
    floor.collision = ShapeCollection([slab], reference_frame=floor)
    with scene_with_two_things.modify_world():
        scene_with_two_things.add_connection(
            FixedConnection(
                parent=body_named(scene_with_two_things, ANSWERED_NAME),
                child=floor,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.25, z=-0.3
                ),
            )
        )
    return scene_with_two_things


@needs_a_renderer
def test_a_picture_is_drawn_without_shadows_unless_they_are_asked_for(
    scene_over_a_floor: World,
) -> None:
    """
    A shadow across the table reads as something standing there, so a picture is drawn
    without them: the same scene lit the same way is brighter than it is with the
    shadows the lights would cast.
    """
    answers = [body_named(scene_over_a_floor, ANSWERED_NAME)]
    shadowed = SceneRender(world=scene_over_a_floor, shadows=True).of(answers)
    plain = SceneRender(world=scene_over_a_floor).of(answers)
    assert plain.image.mean() > shadowed.image.mean()


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
def test_a_name_is_written_above_the_thing_it_names(
    scene_with_two_things: World,
) -> None:
    """
    A name written across a thing hides it, so it is written a little above it and
    joined to it by a line, and the name is what the twin calls the thing.
    """
    answered = body_named(scene_with_two_things, ANSWERED_NAME)

    drawn = render_of(scene_with_two_things).of([answered])

    [placed] = drawn.labels
    assert placed.label.text == answered.name.name
    assert placed.bottom < placed.label.thing[1]
    assert drawn.holds(LABEL_COLOR)


@needs_a_renderer
def test_a_render_asked_not_to_write_names_writes_none(
    scene_with_two_things: World,
) -> None:
    drawn = SceneRender(
        world=scene_with_two_things, highlight=HIGHLIGHT, label_answers=False
    ).of([body_named(scene_with_two_things, ANSWERED_NAME)])
    assert drawn.labels == ()
    assert not drawn.holds(LABEL_COLOR)


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


def heading_of(point_of_view: PointOfView) -> np.ndarray:
    """
    The way a point of view faces along the ground, as a unit vector.

    :param point_of_view: The point of view to read.
    """
    facing = point_of_view.pose.to_np()[:3, 0] * np.array([1.0, 1.0, 0.0])
    return facing / np.linalg.norm(facing)


def test_a_point_of_view_stood_behind_a_box_still_faces_the_way_it_faced(
    scene_with_two_things: World,
) -> None:
    """
    Left and right are only left and right from somewhere, so moving the looker to where
    the box is in view must not turn it.
    """
    looker = PointOfView(
        body=scene_with_two_things.root,
        pose=HomogeneousTransformationMatrix.from_xyz_rpy(x=0.1, y=0.2, yaw=0.7),
    )
    box = SceneRender(world=scene_with_two_things).bounds()

    stood = looker.stood_behind(box)

    assert heading_of(stood) == pytest.approx(heading_of(looker))


def test_a_point_of_view_stood_behind_a_box_looks_down_on_it_from_behind(
    scene_with_two_things: World,
) -> None:
    """
    The looker stands back from the box along the way it faces, above it, and looks at
    its centre, so the whole box is in front of it and below it.
    """
    looker = PointOfView(
        body=scene_with_two_things.root,
        pose=HomogeneousTransformationMatrix.from_xyz_rpy(yaw=0.7),
    )
    box = SceneRender(world=scene_with_two_things).bounds()

    stood = looker.stood_behind(box)

    pose = stood.pose.to_np()
    towards_the_centre = box.mean(axis=0) - pose[:3, 3]
    assert pose[:3, 0] == pytest.approx(
        towards_the_centre / np.linalg.norm(towards_the_centre)
    )
    assert pose[2, 3] > box[1, 2]
    assert np.dot(heading_of(looker), towards_the_centre) > 0


def test_a_point_of_view_stood_behind_a_box_narrows_its_view_to_the_box(
    scene_with_two_things: World,
) -> None:
    """
    Stood back far enough to see over an arm, the looker would leave the box a few
    pixels across at its usual view, so the view is narrowed to fill the picture with
    it.
    """
    looker = PointOfView(body=scene_with_two_things.root)
    box = SceneRender(world=scene_with_two_things).bounds()

    stood = looker.stood_behind(box)

    assert stood.field_of_view == LOOKING_CLOSELY
    assert stood.field_of_view < looker.field_of_view


def test_a_point_of_view_stands_where_its_pose_puts_it(
    scene_with_two_things: World,
) -> None:
    """
    A question asked from a place rather than from a body is drawn from that place, so
    the camera stands where the pose says rather than at the body it hangs on.
    """
    stood_at = HomogeneousTransformationMatrix.from_xyz_rpy(x=0.3, y=-0.2, z=1.1)
    camera = PointOfView(
        body=body_named(scene_with_two_things, ANSWERED_NAME), pose=stood_at
    ).camera()
    assert camera.position == pytest.approx(stood_at.to_position().to_np()[:3].tolist())


# %% framing the picture on what matters


def test_a_render_frames_the_whole_world_by_default(
    scene_with_two_things: World,
) -> None:
    """
    Told nothing about what matters, a picture shows everything the world holds.
    """
    render = render_of(scene_with_two_things)
    whole = render.bounds()
    assert whole.shape == (2, 3)


def test_a_render_can_be_framed_on_the_things_that_matter(
    scene_with_two_things: World,
) -> None:
    """
    A real scene stands on a floor far wider than the table its work happens on, and a
    camera placed around all of it leaves the answer a few pixels across.

    Framed on the bodies that matter, the picture is of those.
    """
    answered = body_named(scene_with_two_things, ANSWERED_NAME)
    framed = SceneRender(world=scene_with_two_things, framed_on=(answered,)).bounds()
    whole = render_of(scene_with_two_things).bounds()

    assert np.all(framed[0] >= whole[0])
    assert np.all(framed[1] <= whole[1])
    assert np.any(framed[1] - framed[0] < whole[1] - whole[0])


def test_framing_on_one_body_covers_that_body(
    scene_with_two_things: World,
) -> None:
    """
    The point of framing is that what it is framed on is inside the picture, so the box
    the camera is placed around holds where that body stands.
    """
    answered = body_named(scene_with_two_things, ANSWERED_NAME)
    framed = SceneRender(world=scene_with_two_things, framed_on=(answered,)).bounds()

    stands_at = scene_with_two_things.compute_forward_kinematics_np(
        scene_with_two_things.root, answered
    )[:3, 3]
    assert np.all(framed[0] <= stands_at)
    assert np.all(stands_at <= framed[1])


# %% the scene of a world read back from the database


@needs_a_renderer
def test_a_world_read_back_from_the_database_is_drawn(
    scene_with_two_things: World, tmp_path: Path
) -> None:
    """
    A card is drawn from the world an episode kept, which is read back from the database
    by a later process, so what came back has to build a simulation as the original did.
    """
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))
    episode = Episode(scenario_name="drawn", execution_type=ExecutionType.SIMULATED)
    episode.world = scene_with_two_things
    recording = open_recording(database)
    recording.record(
        RecordedTrial(episode=episode, outcome=TrialOutcome.SUCCEEDED, duration=1.0)
    )
    recording.close()
    [trial] = LongTermMemory(database).recall_every_trial()

    drawn = render_of(trial.episode.world).of(
        [body_named(trial.episode.world, ANSWERED_NAME)]
    )

    assert drawn.write(tmp_path / "read_back.png").is_file()
