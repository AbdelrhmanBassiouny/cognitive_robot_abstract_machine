"""
The object drawn where it was and where it ended up, in one view.

The panel that says what an event did to the scene. A timeline says a translation was
reported; this says the object went from here to there, which is what a reader needs to
see that the answer is about a real change and not a label on a chart.
"""

from __future__ import annotations

import numpy as np
import pytest
from coraplex.datastructures.enums import ExecutionType
from segmind.datastructures.events import (
    PickUpEvent,
    SupportEvent,
    TranslationEvent,
)

from experiments.episodes.episode import Episode, RecordedTrial, Tick
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.scene import SceneRender
from experiments.paper.pose_change import (
    GHOST_COLOR,
    EventStatesNoPoseChangeError,
    PoseChange,
    PoseChangeRender,
)
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import Connection6DoF
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import Body

from .offscreen_rendering import needs_a_renderer
from .test_paper_scene_render import ANSWERED_NAME, OTHER_NAME, standing_box

# %% a scene holding one loose piece


@pytest.fixture
def scene_with_a_loose_piece() -> World:
    """
    A world holding a box that stands somewhere and a loose one hanging from it.

    The loose one hangs from a connection that carries a pose, which is what a piece the
    run can move looks like in the twin and what lets a render stand it somewhere else.
    """
    world = World()
    stands = standing_box(ANSWERED_NAME)
    loose = standing_box(OTHER_NAME)
    with world.modify_world():
        world.add_body(stands)
        world.add_connection(
            Connection6DoF.create_with_dofs(world=world, parent=stands, child=loose)
        )
    return world


def loose_piece(world: World) -> Body:
    """
    The piece of the scene a render can stand somewhere else.

    :param world: The world to read.
    """
    return world.get_body_by_name(OTHER_NAME)


# %% where the object went

STOOD_AT = 0.5
"""
Where along the world's x-axis the object stood before it moved, in metres.

Clear of the box it hangs from, so that what the render draws of it where it used to be
is not hidden behind that box.
"""

ENDED_AT = -0.5
"""
Where along the world's x-axis the object ended up, in metres.

The other side of the box it hangs from, so the two poses do not cover each other.
"""

MOVED_AT = 3.0
"""
Seconds into the trial the object moved.
"""


def moved(subject: Body) -> TranslationEvent:
    """
    The translation the monitor reported of the given object.

    :param subject: The object that moved.
    """
    return TranslationEvent(
        tracked_object=subject,
        start_pose=Pose.from_xyz_rpy(x=STOOD_AT),
        current_pose=Pose.from_xyz_rpy(x=ENDED_AT),
    )


# %% reading a change of pose off what was reported


def test_a_motion_event_states_the_change_of_pose_itself(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A reported motion already says where the object started and where it got to, so the
    panel is drawn from the event rather than from a second reading of the run.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    change = PoseChange.of(moved(subject))
    assert change.subject is subject
    assert change.before.to_np()[0, 3] == STOOD_AT
    assert change.after.to_np()[0, 3] == ENDED_AT


def test_an_event_that_states_no_motion_cannot_be_drawn_as_one(
    scene_with_a_loose_piece: World,
) -> None:
    """
    An event that is not a motion says nothing about where its object was, which is a
    state to report rather than a pair of empty poses to draw.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    with pytest.raises(EventStatesNoPoseChangeError):
        PoseChange.of(SupportEvent(tracked_object=subject))


# %% reading it off the run instead


def trial_that_reported(*events) -> RecordedTrial:
    """
    A trial whose monitor reported the given events, all in one tick.

    :param events: What the monitor saw.
    """
    return RecordedTrial(
        episode=Episode(
            scenario_name="shape_sorting", execution_type=ExecutionType.SIMULATED
        ),
        outcome=TrialOutcome.SUCCEEDED,
        duration=12.0,
        ticks=[Tick(moment=MOVED_AT, events=list(events))],
    )


def test_an_event_that_is_not_a_motion_is_drawn_from_the_motions_around_it(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A pick-up says the object is held, not where it went; where it went is what the
    motions of the same object reported while it was being picked up say.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    picked_up = PickUpEvent(tracked_object=subject)
    trial = trial_that_reported(picked_up, moved(subject))

    change = PoseChange.around(picked_up, trial)

    assert change.before.to_np()[0, 3] == STOOD_AT
    assert change.after.to_np()[0, 3] == ENDED_AT


def test_an_object_the_run_never_saw_move_has_no_change_to_draw(
    scene_with_a_loose_piece: World,
) -> None:
    """
    Nothing moved means there is no before and after, so the card leaves the panel out
    rather than drawing the object twice in the same place.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    picked_up = PickUpEvent(tracked_object=subject)
    assert PoseChange.around(picked_up, trial_that_reported(picked_up)) is None


def test_the_motions_read_off_the_run_are_the_ones_about_that_object(
    scene_with_a_loose_piece: World,
) -> None:
    """
    Another object moving in the same tick says nothing about where this one went.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    another = scene_with_a_loose_piece.get_body_by_name(ANSWERED_NAME)
    picked_up = PickUpEvent(tracked_object=subject)
    trial = trial_that_reported(picked_up, moved(another))

    assert PoseChange.around(picked_up, trial) is None


# %% drawing both poses in one view


SOLID_GHOST = Color(GHOST_COLOR.R, GHOST_COLOR.G, GHOST_COLOR.B, 1.0)
"""
The ghost's own colour with nothing let through it, which is what a picture can be
checked for by colour.
"""


@needs_a_renderer
def test_both_poses_are_drawn_in_one_picture(scene_with_a_loose_piece: World) -> None:
    """
    The point of the panel is the two poses in one view, so one picture holds the object
    where it ended up and the object where it was, each in its own colour.

    Drawn with nothing let through the earlier pose, so that what it is drawn in is the
    colour itself rather than a mixture of it and what is behind it.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    drawn = PoseChangeRender(world=scene_with_a_loose_piece, ghost=SOLID_GHOST).of(
        PoseChange.of(moved(subject))
    )
    assert drawn.holds(ANSWER_COLOR)
    assert drawn.holds(SOLID_GHOST)


@needs_a_renderer
def test_the_earlier_pose_is_see_through(scene_with_a_loose_piece: World) -> None:
    """
    A ghost that hid whatever it stands in front of would read as the object itself, so
    it is drawn see-through -- which is a property of the body in the scene rather than
    of a picture laid over one, and so shows up as a different picture entirely.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    change = PoseChange.of(moved(subject))

    see_through = PoseChangeRender(world=scene_with_a_loose_piece).of(change)
    solid = PoseChangeRender(world=scene_with_a_loose_piece, ghost=SOLID_GHOST).of(
        change
    )

    assert not np.array_equal(see_through.image, solid.image)


def test_the_ghost_is_a_body_of_the_scene_wearing_the_objects_own_shapes(
    scene_with_a_loose_piece: World,
) -> None:
    """
    The earlier pose is a thing standing in the scene rather than a picture laid over
    one, which is what lets the renderer light it and hide it behind whatever is in
    front of it.

    It wears the object's own shapes, so what stands there is the piece itself.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    render = PoseChangeRender(world=scene_with_a_loose_piece)

    ghost = render.stand_a_ghost_at(
        subject, Pose.from_xyz_rpy(x=STOOD_AT).to_homogeneous_matrix()
    )

    assert ghost in scene_with_a_loose_piece.kinematic_structure_entities
    assert len(ghost.visual.shapes) == len(subject.visual.shapes)
    assert all(
        theirs is not ours
        for theirs, ours in zip(ghost.visual.shapes, subject.visual.shapes)
    )


def test_the_ghost_is_taken_back_out_of_the_scene(
    scene_with_a_loose_piece: World,
) -> None:
    """
    The next question is answered from the world the run recorded, so the scene cannot
    be left with a spare piece standing in it.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    render = PoseChangeRender(world=scene_with_a_loose_piece)
    ghost = render.stand_a_ghost_at(
        subject, Pose.from_xyz_rpy(x=STOOD_AT).to_homogeneous_matrix()
    )

    render.take_the_ghost_away(ghost)

    assert ghost not in scene_with_a_loose_piece.kinematic_structure_entities


@needs_a_renderer
def test_the_render_leaves_nothing_hanging_on_the_world(
    scene_with_a_loose_piece: World,
) -> None:
    """
    The camera and the light both poses are drawn under are placed for the one panel and
    taken off again, so a second card of the same world is drawn the same way.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    stood_in_it = list(scene_with_a_loose_piece.kinematic_structure_entities)
    hanging = {
        entity.name: len(entity.simulator_additional_properties)
        for entity in stood_in_it
    }

    PoseChangeRender(world=scene_with_a_loose_piece).of(PoseChange.of(moved(subject)))

    assert {
        entity.name: len(entity.simulator_additional_properties)
        for entity in stood_in_it
    } == hanging


def test_the_panel_is_framed_on_the_move_rather_than_the_whole_world(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A picture framed on everything the world holds leaves a piece on a table a few
    pixels across, which says nothing about where it went.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    render = PoseChangeRender(world=scene_with_a_loose_piece)
    ghost = render.stand_a_ghost_at(
        subject, Pose.from_xyz_rpy(x=STOOD_AT).to_homogeneous_matrix()
    )

    assert render.framed_on(subject, ghost) == (subject, ghost)

    framed = SceneRender(
        world=scene_with_a_loose_piece, framed_on=render.framed_on(subject, ghost)
    ).bounds()
    for stands in (subject, ghost):
        at = scene_with_a_loose_piece.compute_forward_kinematics_np(
            scene_with_a_loose_piece.root, stands
        )[:3, 3]
        assert np.all(framed[0] <= at) and np.all(at <= framed[1])
