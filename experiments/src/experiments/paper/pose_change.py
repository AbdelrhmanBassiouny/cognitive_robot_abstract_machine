"""
An object drawn where it was and where it ended up, in one view.

The panel that says what an event did to the scene. A chart says a translation was
reported; this says the piece went from the table to the gripper, or from where it stood
to where a hand shoved it, which is what lets a reader see that the answer is about a
change in the world rather than a label on a chart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    DetectionEvent,
    EventWithTrackedObjects,
    MotionEvent,
)
from typing_extensions import List, Optional

from experiments.episodes.episode import RecordedTrial
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.scene import BACKGROUND_COLOR, RenderedScene, SceneRender
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body, Connection
from semantic_digital_twin.world_description.geometry import Color

# %% how the earlier pose is told from the later one

GHOST_COLOR = Color(0.36, 0.42, 0.90, 1.0)
"""
What the object is drawn in where it used to be.

A colour of its own rather than a fainter answer colour, so that the two poses are read
as *then* and *now* rather than as one object and a smudge of it.
"""

GHOST_OPACITY = 0.55
"""
How much of the earlier pose is let through where it is laid over the scene.

Solid enough to read as the object's own shape, thin enough that what it is standing in
front of still shows through and it is not mistaken for the object itself.
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

    ghost_opacity: float = field(default=GHOST_OPACITY)
    """
    How much of the earlier pose is let through where it is laid over the scene.
    """

    def of(self, change: PoseChange) -> RenderedScene:
        """
        Draw the given change of pose as one picture.

        The twin is left exactly as it was: the object is put back where it came from for
        the length of one render and returned afterwards.

        :param change: Where the object was and where it ended up.
        :raises NothingToDrawError: If a camera or a light has to be placed and the world
            holds no geometry to place it around.
        """
        scene = SceneRender(world=self.world, camera=self.camera)
        placed = scene.place_around_the_scene()
        camera = self.camera if self.camera is not None else placed[0]
        try:
            was = self._drawn_at(change, change.before, camera, self.ghost)
            now = self._drawn_at(change, change.after, camera, self.highlight)
            return RenderedScene(
                image=self._ghosted(was, now), answer_mask=now.answer_mask
            )
        finally:
            for own in placed:
                own.body.simulator_additional_properties.remove(own)

    # %% one of the two poses

    def _drawn_at(
        self,
        change: PoseChange,
        pose: HomogeneousTransformationMatrix,
        camera: MujocoCamera,
        color: Color,
    ) -> RenderedScene:
        """
        The scene with the object standing at the given pose.

        :param change: The change being drawn, which says which object moves.
        :param pose: Where to stand it, in the world root frame.
        :param camera: The camera both poses are drawn through.
        :param color: What the object is drawn in.
        """
        stood_at = self.standing_pose(change.subject)
        self._stand(change.subject, pose)
        try:
            return SceneRender(
                world=self.world,
                camera=camera,
                highlight=color,
                faded=self.faded,
                label_answers=False,
            ).of([change.subject])
        finally:
            self._stand(change.subject, stood_at)

    def standing_pose(self, subject: Body) -> HomogeneousTransformationMatrix:
        """
        Where the given object stands, in the world root frame.

        :param subject: The object to look up.
        """
        return HomogeneousTransformationMatrix(
            self.world.compute_forward_kinematics_np(self.world.root, subject),
            reference_frame=self.world.root,
            child_frame=subject,
        )

    def _stand(self, subject: Body, pose: HomogeneousTransformationMatrix) -> None:
        """
        Put the given object at the given pose and let the twin work the scene out
        again.

        The connection is looked up afresh each time rather than held onto, because
        building a MuJoCo mirror of the world re-creates the connections it is built
        from and leaves an earlier one detached.

        :param subject: The object to stand.
        :param pose: Where to stand it, in the world root frame.
        :raises ObjectHeldFixedError: If the twin holds the object fixed where it is.
        """
        connection = subject.parent_connection
        if not self.can_be_stood_somewhere_else(connection):
            raise ObjectHeldFixedError(
                subject_name=subject.name.name,
                connection_type=type(connection).__name__,
            )
        connection.origin = pose.copy_with_new_reference_frames(
            new_reference_frame=self.world.root, new_child_frame=subject
        )
        self.world.notify_state_change()

    @staticmethod
    def can_be_stood_somewhere_else(connection: Connection) -> bool:
        """
        Whether the twin lets this connection be given a new origin.

        A connection that holds its child fixed refuses one, so a body hanging from it
        can only be drawn where it already stands.

        :param connection: The connection to ask.
        """
        return type(connection).origin.fset is not Connection.origin.fset

    # %% laying the one over the other

    def _ghosted(self, was: RenderedScene, now: RenderedScene) -> np.ndarray:
        """
        The later picture with the earlier pose laid over it.

        :param was: The scene with the object where it used to be.
        :param now: The scene with the object where it ended up.
        """
        picture = now.image.copy()
        covered = was.answer_mask
        picture[covered] = (
            was.image[covered] * self.ghost_opacity
            + picture[covered] * (1.0 - self.ghost_opacity)
        ).astype(np.uint8)
        return picture
