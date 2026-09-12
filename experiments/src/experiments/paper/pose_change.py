"""
An object drawn where it was and where it ended up, in one view.

The panel that says what an event did to the scene. A chart says a translation was
reported; this says the piece went from the table to the gripper, or from where it stood
to where a hand shoved it, which is what lets a reader see that the answer is about a
change in the world rather than a label on a chart.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    DetectionEvent,
    EventWithTrackedObjects,
    MotionEvent,
)
from typing_extensions import List, Optional, Tuple

from experiments.episodes.episode import RecordedTrial
from experiments.episodes.trace import JointPositions
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.scene import (
    BACKGROUND_COLOR,
    PickedOut,
    RenderedScene,
    SceneRender,
)
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, Connection
from semantic_digital_twin.world_description.geometry import Color

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
        The change of pose the trial recorded for the object an event is about.

        An event that is itself a motion states the change; one that is not -- a pick-up
        says the object is held, not where it went -- is read against every motion of
        the same object the run reported, from where the first of them started to where
        the last of them got to.

        :param event: The event whose object is asked after.
        :param trial: The trial it was reported in.
        :return: The change, or None where the run saw that object move at no point.
        """
        if isinstance(event, MotionEvent):
            return cls.of(event)
        if not isinstance(event, EventWithTrackedObjects):
            return None
        moved = cls._motions_of(event.tracked_object, trial)
        if not moved:
            return None
        return cls(
            subject=event.tracked_object,
            before=moved[0].start_pose.to_homogeneous_matrix(),
            after=moved[-1].current_pose.to_homogeneous_matrix(),
        )

    @staticmethod
    def _motions_of(subject: Body, trial: RecordedTrial) -> List[MotionEvent]:
        """
        Every motion of the given object the trial reported, oldest first.

        Matched by the name the twin gives the object rather than by identity, because a
        recalled episode reads its events back as separate objects.

        :param subject: The object to look for.
        :param trial: The trial to read.
        """
        return sorted(
            (
                event
                for tick in trial.ticks
                for event in tick.events
                if isinstance(event, MotionEvent)
                and event.tracked_object.name == subject.name
            ),
            key=lambda event: event.timestamp,
        )


# %% drawing it


@dataclass
class PoseChangeRender:
    """
    Draws one object where it was and where it ended up, from one place.

    Both poses are drawn from the same camera under the same light, so the ghost reads
    as the same object moved rather than as a second scene. The ghost is laid over the
    picture rather than drawn into it, so it shows through whatever ended up standing in
    front of it -- which is what makes a piece now held in the gripper still show where
    it came from.
    """

    world: World
    """
    The twin the picture is drawn of.
    """

    camera: Optional[MujocoCamera] = None
    """
    The camera to draw through, already attached to :attr:`world`.

    When none is given, an overview camera framing the whole scene is hung on the
    world's root for the one panel and taken off again afterwards.
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
        self, change: PoseChange, robot_at: Optional[JointPositions] = None
    ) -> RenderedScene:
        """
        Draw the given change of pose as one picture.

        Both poses stand in the one scene: the object itself where it ended up, and a
        see-through copy of it where it was. Being a body of the scene rather than a
        picture laid over one, the ghost is lit, shaded and occluded like everything
        else -- a piece now held in the gripper shows its old place on the table through
        whatever happens to stand in front of it.

        The twin is left exactly as it was: every joint goes back where it stood, the
        object goes back where it came from and the ghost is taken out again.

        :param change: Where the object was and where it ended up.
        :param robot_at: Where every joint of the world stood at the moment drawn, so
            the robot is shown as it was -- reaching for the piece, or holding it --
            rather than as the run left it. None leaves the joints where they are.
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
        ghost = self.stand_a_ghost_at(change.subject, change.before)
        try:
            return SceneRender(
                world=self.world,
                camera=self.camera,
                highlight=self.highlight,
                faded=self.faded,
                label_answers=False,
                framed_on=self.framed_on(change.subject, ghost),
                picked_out=(PickedOut(entity=ghost, color=self.ghost),),
            ).of([change.subject])
        finally:
            self.take_the_ghost_away(ghost)
            stand(self.world, change.subject, stood_at)
            stood.restore_into(self.world)

    @staticmethod
    def framed_on(subject: Body, ghost: Body) -> Tuple[Body, ...]:
        """
        What this panel's picture is framed on: the object and the ghost of where it
        was.

        A picture framed on the whole world leaves a piece on a table a few pixels
        across; framed on the two poses, it is a picture of the move itself with as much
        of the scene around it as that takes.

        :param subject: The object, standing where it ended up.
        :param ghost: The copy standing where it was.
        """
        return (subject, ghost)

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

    def take_the_ghost_away(self, ghost: Body) -> None:
        """
        Take the copy back out of the scene, so the next question is answered from the
        world the run recorded rather than from one with a spare piece in it.

        :param ghost: The body :meth:`stand_a_ghost_at` added.
        """
        with self.world.modify_world():
            self.world.remove_kinematic_structure_entity(ghost)

    @staticmethod
    def _copied(shapes: ShapeCollection, worn_by: Body) -> ShapeCollection:
        """
        One body's shapes, copied so that a scene built from both draws both.

        :param shapes: The shapes to copy.
        :param worn_by: The body the copies belong to.
        """
        return ShapeCollection(
            [copy.copy(shape) for shape in shapes.shapes], reference_frame=worn_by
        )
