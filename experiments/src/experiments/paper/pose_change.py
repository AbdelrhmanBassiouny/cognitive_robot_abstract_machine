"""
An object drawn where it was and where it ended up, in one view.

The panel that says what an event did to the scene. A chart says a translation was
reported; this says the piece went from the table to the gripper, or from where it stood
to where a hand shoved it, which is what lets a reader see that the answer is about a
change in the world rather than a label on a chart.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    DetectionEvent,
    EventWithTrackedObjects,
    MotionEvent,
    StopTranslationEvent,
    TranslationEvent,
)
import numpy as np
from typing_extensions import List, Optional, Sequence, Tuple

from experiments.episodes.episode import RecordedTrial
from experiments.episodes.trace import JointPositions
from experiments.paper.chart import TimelineSpan
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.run_plan import TrialClock
from experiments.paper.scene import (
    BACKGROUND_COLOR,
    PICTURE_HEIGHT,
    PICTURE_WIDTH,
    PickedOut,
    RenderedScene,
    SceneRender,
)
from semantic_digital_twin.adapters.multi_sim import OVERVIEW_VIEWPOINT, MujocoCamera
from semantic_digital_twin.callbacks.callback import ModelChangeCallback
from semantic_digital_twin.spatial_computations.forward_kinematics import (
    ForwardKinematicsManager,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import (
    Body,
    Connection,
    KinematicStructureEntity,
)
from semantic_digital_twin.world_description.geometry import Color, Sphere

# %% how the earlier pose is told from the later one

GHOST_COLOR = Color(0.36, 0.42, 0.90, 0.55)
"""
What the object is drawn in where it used to be.

A colour of its own rather than a fainter answer colour, so that the two poses are read
as *then* and *now* rather than as one object and a smudge of it. Its opacity is what
makes the ghost see-through: it is a body of the scene like any other, so the renderer
lets whatever stands behind it show through and hides the part of it that stands behind
something else.
"""

GHOST_NAME = "%s_where_it_was"
"""
What the body standing at the object's earlier pose is called, after the object itself.
"""

WAYPOINT_NAME = "%s_on_its_way_%d"
"""
What each dot standing along the object's way is called, after the object and its place
along the way.
"""

WAYPOINT_RADIUS = 0.006
"""
How big a dot along the object's way is, in metres: visible on a table-sized scene,
small beside a piece.
"""

WAYPOINTS = 10
"""
How many dots the object's way is shown with.
"""

# %% where the move is looked at from

MOVE_CAMERA_NAME = "paper_move_camera"
"""
What the render calls the camera it hangs to look across an object's move.
"""

ACROSS_ELEVATION = 1.0
"""
How far up the camera looking across a move stands for every metre it stands to the
side, so the move is seen from diagonally above rather than along the table.
"""

MINIMUM_MOVE_ACROSS_THE_TABLE = 0.01
"""
How far an object has to have moved across the table, in metres, for there to be a side
to look at the move from; a move straight up or down is looked at from the overview's
side.
"""


def viewpoint_across(
    before: HomogeneousTransformationMatrix, after: HomogeneousTransformationMatrix
) -> np.ndarray:
    """
    Which way from a move the camera stands to see the two poses side by side: square
    across the table to the way the object went, raised, on whichever side the overview
    camera also stands on so the picture is turned the same way as the other cards.

    A move with no way across the table -- a lift -- is looked at from the overview's
    own side.

    :param before: Where the object was, in the world root frame.
    :param after: Where it ended up, in the world root frame.
    """
    across_the_table = (after.to_np()[:3, 3] - before.to_np()[:3, 3])[:2]
    length = float(np.linalg.norm(across_the_table))
    if length < MINIMUM_MOVE_ACROSS_THE_TABLE:
        return np.array(OVERVIEW_VIEWPOINT, dtype=float)
    square_to_it = np.array([-across_the_table[1], across_the_table[0]]) / length
    if square_to_it @ np.array(OVERVIEW_VIEWPOINT[:2]) < 0:
        square_to_it = -square_to_it
    return np.array([square_to_it[0], square_to_it[1], ACROSS_ELEVATION])


# %% an event that says nothing about where its object went


@dataclass
class EventStatesNoPoseChangeError(DataclassException):
    """
    Raised when an event that states no motion is asked where its object went.
    """

    event: str
    """
    The event that was asked.
    """

    def error_message(self) -> str:
        return (
            "%s states no motion, so it says nothing about where its object went."
            % (self.event)
        )

    def suggest_correction(self) -> str:
        return (
            "Only a motion event carries the poses either side of it. Use "
            "PoseChange.around to read an event that is not one against the motions the "
            "run reported of the same object."
        )


@dataclass
class ObjectHeldFixedError(DataclassException):
    """
    Raised when the object of a pose change is one the twin holds fixed where it is.
    """

    subject_name: str
    """
    The object that cannot be stood anywhere else.
    """

    connection_type: str
    """
    The kind of connection holding it, named as its class is.
    """

    def error_message(self) -> str:
        return (
            "%s hangs from a %s, which states no pose to change, so it cannot be drawn "
            "anywhere but where it stands." % (self.subject_name, self.connection_type)
        )

    def suggest_correction(self) -> str:
        return (
            "Only a body whose connection carries a pose can be stood somewhere else. A "
            "loose piece of the scene hangs from a Connection6DoF and can; a part welded "
            "to another body cannot, and its card is drawn without this panel."
        )


# %% standing an object somewhere for the length of a picture


def can_be_stood_somewhere_else(connection: Connection) -> bool:
    """
    Whether the twin lets this connection be given a new origin.

    A connection that holds its child fixed refuses one, so a body hanging from it can
    only be drawn where it already stands.

    :param connection: The connection to ask.
    """
    return type(connection).origin.fset is not Connection.origin.fset


def standing_pose(world: World, subject: Body) -> HomogeneousTransformationMatrix:
    """
    Where the given object stands, in the world root frame.

    :param world: The twin it stands in.
    :param subject: The object to look up.
    """
    return HomogeneousTransformationMatrix(
        world.compute_forward_kinematics_np(world.root, subject),
        reference_frame=world.root,
        child_frame=subject,
    )


def stand(world: World, subject: Body, pose: HomogeneousTransformationMatrix) -> None:
    """
    Put the given object at the given pose and let the twin work the scene out again.

    The connection is looked up afresh each time rather than held onto, because building
    a MuJoCo mirror of the world re-creates the connections it is built from and leaves
    an earlier one detached.

    :param world: The twin the object stands in.
    :param subject: The object to stand.
    :param pose: Where to stand it, in the world root frame.
    :raises ObjectHeldFixedError: If the twin holds the object fixed where it is.
    """
    connection = subject.parent_connection
    if not can_be_stood_somewhere_else(connection):
        raise ObjectHeldFixedError(
            subject_name=subject.name.name,
            connection_type=type(connection).__name__,
        )
    connection.origin = pose.copy_with_new_reference_frames(
        new_reference_frame=world.root, new_child_frame=subject
    )
    world.notify_state_change()


# %% keeping a change made for one picture to the picture


@dataclass
class ModelChangesUnannounced:
    """
    Holds off, for as long as it is entered, everything the world tells when its model
    changes, except its own forward kinematics.

    A body stood in the scene for one picture and taken out again is no change to what a
    simulator or a collision checker attached to the world has to know about, and each
    of them working the whole scene out again for it is what turns a picture of a real
    run into half an hour of loading meshes. The forward kinematics are what the world
    knows of where its bodies stand, so they are told: they are what places the body in
    the picture, which is drawn by a mirror of its own.
    """

    world: World
    """
    The world whose callbacks are held off.
    """

    held: List[ModelChangeCallback] = field(default_factory=list, init=False)
    """
    The callbacks this held off, so that only those are let go again; one that was
    paused before stays paused after.
    """

    def __enter__(self) -> ModelChangesUnannounced:
        self.held = [
            callback
            for callback in ModelChangeCallback.all_callbacks_of_this_type_from_world(
                self.world
            )
            if not callback.paused
            and not isinstance(callback, ForwardKinematicsManager)
        ]
        for callback in self.held:
            callback.pause()
        return self

    def __exit__(self, *exception) -> None:
        for callback in self.held:
            callback.resume()
        self.held = []


# %% one stretch of the trial an object was moving over


@dataclass(frozen=True)
class MotionStretch:
    """
    One stretch of a trial an object was moving over, as the monitor reported it: from
    the translation that started it to the one that stopped it.
    """

    started: TranslationEvent
    """
    The report that the object had started moving, which says where it was.
    """

    stopped: Optional[StopTranslationEvent]
    """
    The report that it had stopped, which says where it got to; None where the trial
    ended with it still moving.
    """

    over: TimelineSpan
    """
    The seconds of the trial the stretch runs over.
    """

    @property
    def before(self) -> HomogeneousTransformationMatrix:
        """
        Where the object was as the stretch began.
        """
        return self.started.start_pose.to_homogeneous_matrix()

    @property
    def after(self) -> HomogeneousTransformationMatrix:
        """
        Where it was as the stretch ended: where it stopped, or where it had got to when
        the trial ended with it still moving.
        """
        ended_by = self.started if self.stopped is None else self.stopped
        return ended_by.current_pose.to_homogeneous_matrix()

    def distance_to(self, moment: float) -> float:
        """
        How far the given moment lies outside this stretch, in seconds: nothing where it
        falls within it.

        :param moment: Seconds into the trial.
        """
        return max(self.over.start - moment, moment - self.over.end, 0.0)

    @classmethod
    def all_of(cls, subject: Body, trial: RecordedTrial) -> List[MotionStretch]:
        """
        Every stretch of the trial the given object was moving over, in order.

        Matched by the name the twin gives the object rather than by identity, because a
        recalled episode reads its events back as separate objects. A stop the monitor
        reported with no start before it is a stretch of no length at the stop.

        :param subject: The object to look for.
        :param trial: The trial to read.
        """
        clock = TrialClock.of(trial)
        stretches: List[MotionStretch] = []
        started: Optional[TranslationEvent] = None
        for event in cls._translations_of(subject, trial):
            moment = clock.seconds_of(event.timestamp)
            if isinstance(event, TranslationEvent):
                if started is not None:
                    stretches.append(cls._open_until(started, clock, moment))
                started = event
                continue
            began_at = (
                moment if started is None else clock.seconds_of(started.timestamp)
            )
            stretches.append(
                cls(
                    started=started if started is not None else event,
                    stopped=event,
                    over=TimelineSpan(began_at, moment - began_at),
                )
            )
            started = None
        if started is not None:
            stretches.append(cls._open_until(started, clock, trial.duration))
        return stretches

    @classmethod
    def _open_until(
        cls, started: TranslationEvent, clock: TrialClock, end: float
    ) -> MotionStretch:
        """
        A stretch the monitor never reported the end of, running to the given moment.

        :param started: The report that the object had started moving.
        :param clock: Where the trial's own seconds start.
        :param end: Seconds into the trial the stretch is taken to run to.
        """
        began_at = clock.seconds_of(started.timestamp)
        return cls(
            started=started, stopped=None, over=TimelineSpan(began_at, end - began_at)
        )

    @staticmethod
    def _translations_of(subject: Body, trial: RecordedTrial) -> List[MotionEvent]:
        """
        Every report that the given object started or stopped moving, oldest first.

        :param subject: The object to look for.
        :param trial: The trial to read.
        """
        return sorted(
            (
                event
                for tick in trial.ticks
                for event in tick.events
                if isinstance(event, (TranslationEvent, StopTranslationEvent))
                and event.tracked_object.name == subject.name
            ),
            key=lambda event: event.timestamp,
        )


# %% where an object went


@dataclass(frozen=True)
class PoseChange:
    """
    Where one object of the scene was and where it ended up.
    """

    subject: Body
    """
    The object that moved.
    """

    before: HomogeneousTransformationMatrix
    """
    Where it was, in the world root frame.
    """

    after: HomogeneousTransformationMatrix
    """
    Where it ended up, in the world root frame.
    """

    over: Optional[TimelineSpan] = None
    """
    The seconds of the trial the change happened over, or None for a change read off one
    event alone.
    """

    way: Tuple[HomogeneousTransformationMatrix, ...] = ()
    """
    Where it stood on its way from the one to the other, in order, in the world root
    frame; empty where the run kept no record of the way.
    """

    def with_the_way(
        self, way: Sequence[HomogeneousTransformationMatrix]
    ) -> PoseChange:
        """
        The same change, with the way the object took between its two poses.

        :param way: Where it stood on the way, in order.
        """
        return PoseChange(
            subject=self.subject,
            before=self.before,
            after=self.after,
            over=self.over,
            way=tuple(way),
        )

    def standing_in(self, world: World) -> PoseChange:
        """
        The same change, of the body of the given name in the given world.

        :param world: The twin the change is to be drawn in.
        """
        return PoseChange(
            subject=world.get_body_by_name(self.subject.name.name),
            before=self.before,
            after=self.after,
            over=self.over,
            way=self.way,
        )

    def straight_way(
        self, dots: int = WAYPOINTS
    ) -> Tuple[HomogeneousTransformationMatrix, ...]:
        """
        The straight line from where the object was to where it ended up, as the places
        along it: what stands in for the way where the run kept no record of it.

        :param dots: How many places along the line.
        """
        start = self.before.to_np()[:3, 3]
        end = self.after.to_np()[:3, 3]
        return tuple(
            HomogeneousTransformationMatrix.from_xyz_rpy(
                *(start + (end - start) * fraction).tolist()
            )
            for fraction in np.linspace(0.0, 1.0, dots + 2)[1:-1]
        )

    @classmethod
    def of(cls, event: MotionEvent) -> PoseChange:
        """
        The change of pose a reported motion states itself.

        :param event: The motion that was reported.
        :raises EventStatesNoPoseChangeError: If the event states no motion.
        """
        if not isinstance(event, MotionEvent):
            raise EventStatesNoPoseChangeError(event=str(event))
        return cls(
            subject=event.tracked_object,
            before=event.start_pose.to_homogeneous_matrix(),
            after=event.current_pose.to_homogeneous_matrix(),
        )

    @classmethod
    def around(
        cls, event: DetectionEvent, trial: RecordedTrial
    ) -> Optional[PoseChange]:
        """
        The change of pose the trial recorded for the object an event is about, over the
        stretch it was moving that the event falls in.

        A pick-up says the object is held, not where it went; a translation says it
        started moving, not where it stopped. Either is read against the stretch of the
        trial the monitor saw that object moving over -- the one the event falls in, or
        the nearest one where it falls in none -- from where the object was as the
        stretch began to where it was as it ended.

        :param event: The event whose object is asked after.
        :param trial: The trial it was reported in.
        :return: The change, or None where the run saw that object move at no point.
        """
        if not isinstance(event, EventWithTrackedObjects):
            return None
        stretches = MotionStretch.all_of(event.tracked_object, trial)
        if not stretches:
            return None
        moment = TrialClock.of(trial).seconds_of(event.timestamp)
        nearest = min(stretches, key=lambda stretch: stretch.distance_to(moment))
        return cls(
            subject=event.tracked_object,
            before=nearest.before,
            after=nearest.after,
            over=nearest.over,
        )


# %% drawing it


@dataclass
class PoseChangeRender:
    """
    Draws one object where it was and where it ended up, from one place.

    Both poses are drawn from the same camera under the same light, so the ghost reads
    as the same object moved rather than as a second scene. The ghost is a see-through
    body of the scene, so a piece now held in the gripper still shows where it came from
    through whatever ended up standing in front of it.
    """

    world: World
    """
    The twin the picture is drawn of.
    """

    camera: Optional[MujocoCamera] = None
    """
    The camera to draw through, already attached to :attr:`world`.

    When none is given, a camera looking across the move from the side is hung on the
    world's root for the one panel and taken off again afterwards, so the two poses are
    seen side by side rather than one behind the other.
    """

    highlight: Color = ANSWER_COLOR
    """
    What the object is drawn in where it ended up.
    """

    ghost: Color = GHOST_COLOR
    """
    What the object is drawn in where it used to be.
    """

    faded: Color = BACKGROUND_COLOR
    """
    What everything else is drawn in.
    """

    def of(
        self,
        change: PoseChange,
        robot_at: Optional[JointPositions] = None,
        among: Sequence[KinematicStructureEntity] = (),
    ) -> RenderedScene:
        """
        Draw the given change of pose as one picture.

        Both poses stand in the one scene: the object itself where it ended up, a
        see-through copy of it where it was, and a dot at each place it stood on its
        way -- the way the run recorded, or the straight line where it recorded none.
        Being bodies of the scene rather than pictures laid over one, they are lit,
        shaded and occluded like everything else -- a piece now held in the gripper
        shows its old place on the table through whatever happens to stand in front of
        it.

        The twin is left exactly as it was: every joint goes back where it stood, the
        object goes back where it came from and the ghost and the dots are taken out
        again.

        :param change: Where the object was and where it ended up.
        :param robot_at: Where every joint of the world stood at the moment drawn, so
            the robot is shown as it was -- reaching for the piece, or holding it --
            rather than as the run left it. None leaves the joints where they are.
        :param among: What else the picture is framed on, so the move is seen with
            the scene it happened in -- the gripper that took the piece, the board it
            went to -- rather than alone.
        :raises ObjectHeldFixedError: If the twin holds the object fixed where it is.
        :raises NothingToDrawError: If a camera or a light has to be placed and the world
            holds no geometry to place it around.
        """
        stood = JointPositions(
            moment=0.0,
            positions={
                str(name): position
                for name, position in self.world.state.to_position_dict().items()
            },
        )
        if robot_at is not None:
            robot_at.restore_into(self.world)
        stood_at = standing_pose(self.world, change.subject)
        stand(self.world, change.subject, change.after)
        with ModelChangesUnannounced(self.world):
            ghost = self.stand_a_ghost_at(change.subject, change.before)
            dots = self.stand_dots_along(
                change.subject, change.way or change.straight_way()
            )
            framed_on = self.framed_on(change.subject, ghost) + tuple(among)
            camera = self.camera
            if camera is None:
                camera = self.hang_a_camera_across(change, framed_on)
            try:
                return SceneRender(
                    world=self.world,
                    camera=camera,
                    highlight=self.highlight,
                    faded=self.faded,
                    label_answers=False,
                    framed_on=framed_on,
                    picked_out=(PickedOut(entity=ghost, color=self.ghost),)
                    + tuple(PickedOut(entity=dot, color=self.ghost) for dot in dots),
                ).of([change.subject])
            finally:
                if self.camera is None:
                    camera.body.simulator_additional_properties.remove(camera)
                self.take_away([ghost] + dots)
                stand(self.world, change.subject, stood_at)
                stood.restore_into(self.world)

    def hang_a_camera_across(
        self, change: PoseChange, framed_on: Sequence[KinematicStructureEntity]
    ) -> MujocoCamera:
        """
        Hang a camera on the world's root that looks across the move from the side,
        framing everything the picture is about.

        :param change: The move to look across.
        :param framed_on: What the picture is framed on.
        :return: The camera, already attached, to be taken off again once the picture is
            drawn.
        """
        pose = MujocoCamera.pose_looking_from(
            SceneRender(world=self.world, framed_on=tuple(framed_on)).bounds(),
            viewpoint_across(change.before, change.after),
        )
        camera = MujocoCamera(
            name=MOVE_CAMERA_NAME,
            body=self.world.root,
            position=pose.to_position().to_np()[:3].tolist(),
            quaternion=MujocoCamera.quaternion_of(pose),
            resolution=[float(PICTURE_WIDTH), float(PICTURE_HEIGHT)],
        )
        self.world.root.simulator_additional_properties.append(camera)
        return camera

    @staticmethod
    def framed_on(subject: Body, ghost: Body) -> Tuple[Body, ...]:
        """
        What this panel's picture is always framed on: the object and the ghost of where
        it was.

        A picture framed on the whole world leaves a piece on a table a few pixels
        across; framed on the two poses, it is a picture of the move itself with as much
        of the scene around it as that takes.

        :param subject: The object, standing where it ended up.
        :param ghost: The copy standing where it was.
        """
        return (subject, ghost)

    def stand_dots_along(
        self, subject: Body, way: Sequence[HomogeneousTransformationMatrix]
    ) -> List[Body]:
        """
        Put a small dot into the scene at each place along the object's way.

        :param subject: The object whose way it is.
        :param way: The places, in order, in the world root frame.
        :return: The bodies that were added, to be taken away again once the picture is
            drawn.
        """
        dots = []
        with self.world.modify_world():
            for place, pose in enumerate(way):
                dot = Body(
                    name=PrefixedName(WAYPOINT_NAME % (subject.name.name, place)),
                    visual=ShapeCollection([Sphere(radius=WAYPOINT_RADIUS)]),
                    collision=ShapeCollection([Sphere(radius=WAYPOINT_RADIUS)]),
                )
                self.world.add_connection(
                    FixedConnection(
                        parent=self.world.root,
                        child=dot,
                        parent_T_connection_expression=pose.copy_with_new_reference_frames(
                            new_reference_frame=self.world.root, new_child_frame=dot
                        ),
                    )
                )
                dots.append(dot)
        return dots

    # %% the body standing where the object used to be

    def stand_a_ghost_at(
        self, subject: Body, pose: HomogeneousTransformationMatrix
    ) -> Body:
        """
        Put a copy of the given object into the scene at the given pose.

        The copy wears the object's own shapes rather than a box standing for it, so
        what the reader sees where it used to be is the piece itself. Each shape is
        copied rather than shared, because a scene built from the same shape twice draws
        it once.

        :param subject: The object to copy.
        :param pose: Where to stand the copy, in the world root frame.
        :return: The body that was added, to be taken away again once the picture is
            drawn.
        """
        ghost = Body(name=PrefixedName(GHOST_NAME % subject.name.name))
        ghost.visual = self._copied(subject.visual, ghost)
        ghost.collision = self._copied(subject.collision, ghost)
        with self.world.modify_world():
            self.world.add_connection(
                FixedConnection(
                    parent=self.world.root,
                    child=ghost,
                    parent_T_connection_expression=pose.copy_with_new_reference_frames(
                        new_reference_frame=self.world.root, new_child_frame=ghost
                    ),
                )
            )
        return ghost

    def take_away(self, added: Sequence[Body]) -> None:
        """
        Take every body added for a picture back out of the scene, so the next question
        is answered from the world the run recorded rather than from one with a spare
        piece in it. One change to the world for all of them, since each change has the
        twin work the whole scene out again.

        :param added: The bodies :meth:`stand_a_ghost_at` and :meth:`stand_dots_along`
            added.
        """
        with self.world.modify_world():
            for body in added:
                self.world.remove_kinematic_structure_entity(body)

    @staticmethod
    def _copied(shapes: ShapeCollection, worn_by: Body) -> ShapeCollection:
        """
        One body's shapes, copied so that a scene built from both draws both, each
        standing on the copy's own frame exactly as the original stands on its body's.

        A shape places itself against the frame its origin names, so a copy that kept
        the original's origin would be drawn on the original wherever the copy stood.

        :param shapes: The shapes to copy.
        :param worn_by: The body the copies belong to.
        """
        copies = []
        for shape in shapes.shapes:
            copied = copy.copy(shape)
            copied.origin = HomogeneousTransformationMatrix(
                shape.origin.to_np(), reference_frame=worn_by
            )
            copies.append(copied)
        return ShapeCollection(copies, reference_frame=worn_by)
