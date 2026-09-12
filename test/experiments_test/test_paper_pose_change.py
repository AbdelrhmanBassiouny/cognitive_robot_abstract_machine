"""
The object drawn where it was and where it ended up, in one view.

The panel that says what an event did to the scene. A timeline says a translation was
reported; this says the object went from here to there, which is what a reader needs to
see that the answer is about a real change and not a label on a chart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pytest
from coraplex.datastructures.enums import ExecutionType
from segmind.datastructures.events import (
    PickUpEvent,
    StopTranslationEvent,
    SupportEvent,
    TranslationEvent,
)

from experiments.episodes.episode import Episode, RecordedTrial, Tick
from experiments.episodes.trace import JointPositions
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.scene import SceneRender
from experiments.paper.pose_change import (
    GHOST_COLOR,
    EventStatesNoPoseChangeError,
    ACROSS_ELEVATION,
    ModelChangesUnannounced,
    MotionStretch,
    PoseChange,
    PoseChangeRender,
    stand,
    viewpoint_across,
)
from semantic_digital_twin.adapters.multi_sim import OVERVIEW_VIEWPOINT
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.callbacks.callback import ModelChangeCallback
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
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

TRIAL_BEGAN_AT = datetime(2026, 1, 1, 12, 0, 0)
"""
When the trial the tests read began, on the wall clock.
"""

TRIAL_DURATION = 12.0
"""
How long that trial ran, in seconds.
"""


def at(moment: float) -> datetime:
    """
    The wall-clock instant of a moment of the trial.

    :param moment: Seconds into the trial.
    """
    return TRIAL_BEGAN_AT + timedelta(seconds=moment)


def moved(
    subject: Body,
    moment: float = MOVED_AT,
    from_x: float = STOOD_AT,
    to_x: float = ENDED_AT,
) -> TranslationEvent:
    """
    The report that the given object started moving.

    :param subject: The object that moved.
    :param moment: Seconds into the trial it was reported at.
    :param from_x: Where along the world's x-axis it was.
    :param to_x: Where along it the object had got to when it was reported.
    """
    return TranslationEvent(
        tracked_object=subject,
        start_pose=Pose.from_xyz_rpy(x=from_x),
        current_pose=Pose.from_xyz_rpy(x=to_x),
        timestamp=at(moment),
    )


def stopped(
    subject: Body, moment: float, from_x: float, to_x: float
) -> StopTranslationEvent:
    """
    The report that the given object stopped moving.

    :param subject: The object that stopped.
    :param moment: Seconds into the trial it was reported at.
    :param from_x: Where along the world's x-axis it had started from.
    :param to_x: Where along it the object stopped.
    """
    return StopTranslationEvent(
        tracked_object=subject,
        start_pose=Pose.from_xyz_rpy(x=from_x),
        current_pose=Pose.from_xyz_rpy(x=to_x),
        timestamp=at(moment),
    )


def picked_up(subject: Body, moment: float = MOVED_AT) -> PickUpEvent:
    """
    The report that the given object was picked up.

    :param subject: The object.
    :param moment: Seconds into the trial it was reported at.
    """
    return PickUpEvent(tracked_object=subject, timestamp=at(moment))


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
        duration=TRIAL_DURATION,
        began_at=TRIAL_BEGAN_AT,
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
    held = picked_up(subject)
    trial = trial_that_reported(held, moved(subject))

    change = PoseChange.around(held, trial)

    assert change.before.to_np()[0, 3] == STOOD_AT
    assert change.after.to_np()[0, 3] == ENDED_AT


def test_a_motion_never_reported_stopped_runs_to_the_end_of_the_trial(
    scene_with_a_loose_piece: World,
) -> None:
    """
    As far as the monitor said, the object was still moving when the trial ended.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    held = picked_up(subject)
    trial = trial_that_reported(held, moved(subject))

    change = PoseChange.around(held, trial)

    assert change.over.start == MOVED_AT
    assert change.over.end == TRIAL_DURATION


# %% which stretch of the trial the change is read over

CARRIED_OVER = (5.0, 8.0)
"""
Seconds into the trial the object was carried from where it was picked up to above the
board, as the start and the end of the stretch.
"""

DROPPED_OVER = (9.0, 10.0)
"""
Seconds into the trial it was dropped from there into the hole.
"""

ABOVE_THE_BOARD = 1.5
"""
Where along the world's x-axis the object was carried to, in metres.
"""

IN_THE_HOLE = 1.4
"""
Where along the world's x-axis it was dropped to.
"""


def carried_then_dropped(subject: Body) -> RecordedTrial:
    """
    A trial in which the object was carried, stopped, then dropped and stopped again.

    :param subject: The object.
    """
    return trial_that_reported(
        moved(subject, CARRIED_OVER[0], STOOD_AT, STOOD_AT),
        stopped(subject, CARRIED_OVER[1], STOOD_AT, ABOVE_THE_BOARD),
        moved(subject, DROPPED_OVER[0], ABOVE_THE_BOARD, ABOVE_THE_BOARD),
        stopped(subject, DROPPED_OVER[1], ABOVE_THE_BOARD, IN_THE_HOLE),
    )


def test_a_translation_and_its_stop_are_one_stretch(
    scene_with_a_loose_piece: World,
) -> None:
    subject = loose_piece(scene_with_a_loose_piece)

    carried, dropped = MotionStretch.all_of(subject, carried_then_dropped(subject))

    assert (carried.over.start, carried.over.end) == CARRIED_OVER
    assert carried.before.to_np()[0, 3] == STOOD_AT
    assert carried.after.to_np()[0, 3] == ABOVE_THE_BOARD
    assert (dropped.over.start, dropped.over.end) == DROPPED_OVER
    assert dropped.after.to_np()[0, 3] == IN_THE_HOLE


def test_the_change_is_read_over_the_stretch_the_event_falls_in(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A pick-up reported while the object was being carried is about the carry, not about
    the object's whole life in the trial: it ended up above the board, not in the hole
    it was dropped into later.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    trial = carried_then_dropped(subject)
    held = picked_up(subject, moment=6.0)

    change = PoseChange.around(held, trial)

    assert (change.over.start, change.over.end) == CARRIED_OVER
    assert change.before.to_np()[0, 3] == STOOD_AT
    assert change.after.to_np()[0, 3] == ABOVE_THE_BOARD


def test_an_event_between_stretches_is_read_over_the_nearest(
    scene_with_a_loose_piece: World,
) -> None:
    subject = loose_piece(scene_with_a_loose_piece)
    trial = carried_then_dropped(subject)
    held = picked_up(subject, moment=8.9)

    change = PoseChange.around(held, trial)

    assert (change.over.start, change.over.end) == DROPPED_OVER


def test_a_translation_read_as_the_event_itself_is_read_over_its_own_stretch(
    scene_with_a_loose_piece: World,
) -> None:
    subject = loose_piece(scene_with_a_loose_piece)
    trial = carried_then_dropped(subject)
    [carry] = [
        event
        for event in trial.ticks[0].events
        if isinstance(event, TranslationEvent)
        and event.timestamp == at(CARRIED_OVER[0])
    ]

    change = PoseChange.around(carry, trial)

    assert (change.over.start, change.over.end) == CARRIED_OVER
    assert change.after.to_np()[0, 3] == ABOVE_THE_BOARD


def test_an_object_the_run_never_saw_move_has_no_change_to_draw(
    scene_with_a_loose_piece: World,
) -> None:
    """
    Nothing moved means there is no before and after, so the card leaves the panel out
    rather than drawing the object twice in the same place.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    held = picked_up(subject)
    assert PoseChange.around(held, trial_that_reported(held)) is None


def test_the_motions_read_off_the_run_are_the_ones_about_that_object(
    scene_with_a_loose_piece: World,
) -> None:
    """
    Another object moving in the same tick says nothing about where this one went.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    another = scene_with_a_loose_piece.get_body_by_name(ANSWERED_NAME)
    held = picked_up(subject)
    trial = trial_that_reported(held, moved(another))

    assert PoseChange.around(held, trial) is None


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


def test_the_ghost_wears_its_shapes_on_its_own_frame(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A shape places itself against the frame its origin names, so the copies stand on the
    ghost exactly as the originals stand on the object -- and not on the object, where a
    copy that kept the original's origin would be drawn.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    render = PoseChangeRender(world=scene_with_a_loose_piece)

    ghost = render.stand_a_ghost_at(
        subject, Pose.from_xyz_rpy(x=STOOD_AT).to_homogeneous_matrix()
    )

    for theirs, ours in zip(ghost.visual.shapes, subject.visual.shapes):
        assert theirs.origin.reference_frame is ghost
        assert np.array_equal(theirs.origin.to_np(), ours.origin.to_np())


@needs_a_renderer
def test_the_ghost_is_drawn_where_the_object_was_rather_than_on_it(
    scene_with_a_loose_piece: World,
) -> None:
    """
    The two poses are apart, so the ghost's colour and the object's colour are found in
    different places of the picture.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    drawn = PoseChangeRender(world=scene_with_a_loose_piece, ghost=SOLID_GHOST).of(
        PoseChange.of(moved(subject))
    )

    ghost_at = np.argwhere(drawn.pixels_of(SOLID_GHOST)).mean(axis=0)
    object_at = np.argwhere(drawn.pixels_of(ANSWER_COLOR)).mean(axis=0)
    assert abs(ghost_at[1] - object_at[1]) > drawn.image.shape[1] / 10


# %% where the move is looked at from


def test_the_move_is_looked_at_from_square_across_it() -> None:
    """
    Seen from along the way the object went, the two poses hide one another; seen from
    square across it they stand side by side.

    The camera stands on the side the overview camera stands on, so the picture is
    turned the same way as the others.
    """
    before = Pose.from_xyz_rpy(x=STOOD_AT).to_homogeneous_matrix()
    after = Pose.from_xyz_rpy(x=ENDED_AT).to_homogeneous_matrix()

    viewpoint = viewpoint_across(before, after)

    assert viewpoint[0] == 0.0
    assert viewpoint[1] * OVERVIEW_VIEWPOINT[1] > 0
    assert viewpoint[2] == ACROSS_ELEVATION


def test_a_lift_is_looked_at_from_the_overviews_side() -> None:
    before = Pose.from_xyz_rpy(z=0.0).to_homogeneous_matrix()
    after = Pose.from_xyz_rpy(z=0.3).to_homogeneous_matrix()

    assert np.array_equal(viewpoint_across(before, after), OVERVIEW_VIEWPOINT)


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

    render.take_away([ghost])

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


# %% what the world's own callbacks are told


@dataclass(eq=False)
class CountsModelChanges(ModelChangeCallback):
    """
    Stands in for a simulator or a collision checker attached to the world: counts how
    often it is told the model changed.
    """

    changes: int = 0
    """
    How many changes it was told of.
    """

    def on_model_change(self, **kwargs) -> None:
        self.changes += 1


def hung_from_the_root(world: World, name: str) -> Body:
    """
    Hang a box of the given name from the world's root, as one change to the model.

    :param world: The world to change.
    :param name: What the box is called.
    """
    box = standing_box(name)
    with world.modify_world():
        world.add_connection(FixedConnection(parent=world.root, child=box))
    return box


@needs_a_renderer
def test_the_picture_announces_no_model_change_to_the_worlds_callbacks(
    scene_with_a_loose_piece: World,
) -> None:
    """
    The ghost and the dots stand in the scene for one picture only, so nothing attached
    to the world -- a simulator, a collision checker -- is made to work the scene out
    again for them: that is what turned a picture of a real run into half an hour of
    loading meshes.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    counts = CountsModelChanges(_world=scene_with_a_loose_piece)

    PoseChangeRender(world=scene_with_a_loose_piece).of(PoseChange.of(moved(subject)))

    assert counts.changes == 0
    assert not counts.paused


def test_holding_the_callbacks_off_lets_only_those_it_held_go_again(
    scene_with_a_loose_piece: World,
) -> None:
    """
    A callback something else had paused before stays paused after, and one that was
    live is live again and told of the next change.

    The world's own forward kinematics are never held off, since they are what places
    the body stood in for the picture.
    """
    live = CountsModelChanges(_world=scene_with_a_loose_piece)
    paused_before = CountsModelChanges(_world=scene_with_a_loose_piece)
    paused_before.pause()

    with ModelChangesUnannounced(scene_with_a_loose_piece):
        stood_for_the_picture = hung_from_the_root(
            scene_with_a_loose_piece, "stood_for_the_picture"
        )
        assert np.allclose(
            scene_with_a_loose_piece.compute_forward_kinematics_np(
                scene_with_a_loose_piece.root, stood_for_the_picture
            ),
            np.eye(4),
        )
    assert live.changes == 0
    assert not live.paused
    assert paused_before.paused

    hung_from_the_root(scene_with_a_loose_piece, "stood_for_good")
    assert live.changes == 1
    assert paused_before.changes == 0


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


# %% the robot as it stood at the time


def a_second_loose_body(world: World) -> Body:
    """
    Another body hanging loose in the scene, standing for the robot's own joints: a
    trace can put it somewhere for the length of a picture.

    :param world: The world to add it to.
    """
    arm = standing_box("the_arm")
    with world.modify_world():
        world.add_connection(
            Connection6DoF.create_with_dofs(
                world=world, parent=world.get_body_by_name(ANSWERED_NAME), child=arm
            )
        )
    return arm


def arm_stood_at(world: World, x: float) -> JointPositions:
    """
    Where every joint of the world stands once the arm is at the given place.

    :param world: The world to read.
    :param x: Where along x the arm stands, in metres.
    """
    arm = world.get_body_by_name("the_arm")
    stand(world, arm, HomogeneousTransformationMatrix.from_xyz_rpy(x=x))
    positions = JointPositions(
        moment=MOVED_AT,
        positions={
            str(name): position
            for name, position in world.state.to_position_dict().items()
        },
    )
    stand(world, arm, HomogeneousTransformationMatrix.from_xyz_rpy(x=0.0))
    return positions


@needs_a_renderer
def test_the_robot_is_drawn_where_the_trace_says_it_stood(
    scene_with_a_loose_piece: World,
) -> None:
    """
    The picture is of the moment the event was reported, so the robot stands as it did
    then rather than as the run left it -- which shows as a different picture.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    a_second_loose_body(scene_with_a_loose_piece)
    change = PoseChange.of(moved(subject))
    render = PoseChangeRender(world=scene_with_a_loose_piece)

    as_left = render.of(change)
    as_traced = render.of(change, robot_at=arm_stood_at(scene_with_a_loose_piece, 0.3))

    assert not np.array_equal(as_left.image, as_traced.image)


def test_the_joints_go_back_where_they_stood_after_the_picture(
    scene_with_a_loose_piece: World,
) -> None:
    """
    The next question is answered from the world the run recorded, so a picture of an
    earlier moment leaves every joint where the run left it.
    """
    subject = loose_piece(scene_with_a_loose_piece)
    arm = a_second_loose_body(scene_with_a_loose_piece)
    stood = scene_with_a_loose_piece.state.to_position_dict()

    PoseChangeRender(world=scene_with_a_loose_piece).stand_a_ghost_at(
        subject, Pose.from_xyz_rpy(x=STOOD_AT).to_homogeneous_matrix()
    )
    traced = arm_stood_at(scene_with_a_loose_piece, 0.3)
    traced.restore_into(scene_with_a_loose_piece)
    assert (
        scene_with_a_loose_piece.compute_forward_kinematics_np(
            scene_with_a_loose_piece.root, arm
        )[0, 3]
        != 0.0
    )

    JointPositions(
        moment=MOVED_AT,
        positions={str(name): position for name, position in stood.items()},
    ).restore_into(scene_with_a_loose_piece)

    assert scene_with_a_loose_piece.state.to_position_dict() == stood
