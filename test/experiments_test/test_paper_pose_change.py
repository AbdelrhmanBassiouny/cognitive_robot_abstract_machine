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
from experiments.paper.pose_change import (
    GHOST_COLOR,
    GHOST_OPACITY,
    EventStatesNoPoseChangeError,
    PoseChange,
    PoseChangeRender,
)
from experiments.paper.scene import SceneRender
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import Connection6DoF
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


@needs_a_renderer
def test_both_poses_are_drawn_in_one_picture(scene_with_a_loose_piece: World) -> None:
    """
    The point of the panel is the two poses in one view, so one picture holds the object
    where it ended up and the object where it was, each in its own colour.

    Drawn with the earlier pose let through fully, so that what it is drawn in is the
    colour itself rather than a mixture of it and what it covers.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    drawn = PoseChangeRender(world=scene_with_a_loose_piece, ghost_opacity=1.0).of(
        PoseChange.of(moved(subject))
    )
    assert drawn.holds(ANSWER_COLOR)
    assert drawn.holds(GHOST_COLOR)


@needs_a_renderer
def test_the_earlier_pose_is_let_through_rather_than_painted_on(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A ghost that covered what it stands in front of would read as the object itself, so
    the earlier pose is mixed with the scene rather than laid solidly over it.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    change = PoseChange.of(moved(subject))

    def drawn_with(opacity: float) -> np.ndarray:
        return (
            PoseChangeRender(world=scene_with_a_loose_piece, ghost_opacity=opacity)
            .of(change)
            .image
        )

    faint = drawn_with(GHOST_OPACITY)
    assert not np.array_equal(faint, drawn_with(1.0))
    assert not np.array_equal(faint, drawn_with(0.0))


@needs_a_renderer
def test_the_twin_is_left_exactly_as_it_was(scene_with_a_loose_piece: World) -> None:
    """
    Drawing where an object used to be means putting it back there for the length of one
    render, so the world the next query is answered from has to come out unchanged.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    stood_at = subject.parent_connection.origin.to_np().copy()

    PoseChangeRender(world=scene_with_a_loose_piece).of(PoseChange.of(moved(subject)))

    assert np.array_equal(subject.parent_connection.origin.to_np(), stood_at)


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


@needs_a_renderer
def test_both_poses_are_drawn_from_the_same_viewpoint(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A ghost is only readable as the same object moved if the two are drawn from one
    place, so an object that ended up exactly where it started is drawn exactly as the
    scene itself is.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    render = PoseChangeRender(world=scene_with_a_loose_piece, ghost=ANSWER_COLOR)
    stands_at = render.standing_pose(subject)

    ghosted = render.of(PoseChange(subject=subject, before=stands_at, after=stands_at))
    plain = SceneRender(world=scene_with_a_loose_piece, label_answers=False).of(
        [subject]
    )

    assert np.array_equal(ghosted.image, plain.image)
