"""
Where a surface reaches, worked out from what the world says it is like.

Every surface this package searches has so far been taken from a model: a rectangle
written down for the recordings, or the widest horizontal face of the body the twin
places. Neither is a measurement of where the table really is, and this scene has
already drifted away from its own model once.

So a surface is *described* instead -- how it takes light, and how far the world says it
reaches -- and which finder answers that description is a rule over it, exactly as
:mod:`~experiments.montessori.perception.detector_choice` decides which detector reads a
piece off a surface. The rules are krrood's
:class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`, built from the
underspecified statement *a surface whose finder is to be worked out*, so what is
described and what is left open are read off that statement rather than named again
here. A surface the world says colour cannot outline is measured in the depth image; one
it says nothing about is taken from the model, because a description nothing states is
not one a look can be compiled from.

..note:: A plane fit answers the *surface* and not what rests on it. The point-cloud
    trial this measurement follows found a plane holding a third of the points on the
    bare steel and no piece standing out of that cloud at all, which is why pieces are
    read by fitting known outlines to edges instead.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

import numpy as np
from krrood.entity_query_language.backends import (
    DetectorChoice,
    Look,
    PerceptionDetector,
)
from krrood.entity_query_language.factories import (
    ConditionType,
    a,
    add,
    alternative,
    and_,
    entity,
)
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.query.query import Entity
from krrood.patterns.belief_source import BeliefSource
from typing_extensions import Optional

from experiments.montessori.perception.camera import BelievedCameraPose, RgbdFrame
from experiments.montessori.perception.exceptions import (
    CameraTiltedFurtherThanTrusted,
    NoSurfaceFinderAnswersTheLook,
    SurfaceNotSeenWhereTheWorldPutsIt,
)
from experiments.montessori.perception.orthophoto import WorkspaceBox, WorkspaceRegion
from experiments.montessori.perception.surfaces import WorkspaceSurface
from semantic_digital_twin.world_description.geometry import SurfaceFinish

# %% how far a surface's own points scatter

SURFACE_SCATTER = 0.017
"""
How far a point of a horizontal surface may lie from its plane and still belong to it,
in metres.

Measured on Tracy's brushed steel table by the point-cloud trial this package's
detectors were written after: the table's own points scattered about seventeen
millimetres either side of the plane fitted through them.
"""

LARGEST_TRUSTED_TILT = math.radians(3.0)
"""
How far fitting the camera to a modelled surface may turn it before the disagreement
stops reading as a pose error, in radians.

Deliberately loose. It is here to refuse a disagreement that cannot be a drifted mount
at all, not to arbitrate between a small pose error and a small model error: nothing
measured on this setup separates those two, and which of the two is trusted is stated
per setup rather than inferred from the fit.
"""

# %% what the rules read


@dataclass(frozen=True, eq=False)
class SoughtSurface(Look):
    """
    One surface being looked for, and the look it is being looked for in.

    A rule reads these two as they are rather than a copy of the properties it happens
    to want, so what a condition asks about a surface is what the world states about it
    -- the finish its own shape carries, the ground its own region covers -- and there
    is no second description to fall out of step with either.

    ..note:: Compared by identity: a look holds images, which do not compare as values,
        and two looks at one scene are not the same look.
    """

    surface: WorkspaceSurface
    """
    The surface as the world models it: how far it says the surface reaches, how high
    its plane stands, and how it takes the light that falls on it.
    """

    frame: RgbdFrame
    """
    The camera data the surface is being looked for in.
    """

    finder: Optional[SurfaceFinder] = None
    """
    The finder that answers this surface, left open for the rules to work out.

    A surface stating nothing here is one whose answer has still to be planned, which is
    what the rules that choose a finder are asked about; one carrying a finder has been
    planned already.
    """


# %% what a finder says it can answer


class SurfaceFinder(PerceptionDetector[SoughtSurface], ABC):
    """
    Something that says how far one horizontal surface reaches.

    The surfaces it can answer are the ones its
    :meth:`~krrood.entity_query_language.backends.PerceptionDetector.capability` states
    over a :class:`SoughtSurface`, so the choice between finders is made by matching a
    description against what each one says rather than by a caller knowing which is
    which.
    """

    @abstractmethod
    def find(self, sought: SoughtSurface) -> WorkspaceSurface:
        """
        Say how far the surface reaches and how high its plane stands.

        :param sought: The surface the world models, and the look it is sought in.
        :return: The surface a run searches.
        """


@dataclass(eq=False)
class ModelledSurfaceFinder(SurfaceFinder):
    """
    Answers a surface with what the world models it as.

    The general answer, and the one every run took before this: it needs nothing of the
    picture, only that the world says where the surface reaches.

    ..note:: Compared by identity, so the rules can conclude this finder itself: two
        finders configured the same are not the same finder.
    """

    def capability(self, sought: SoughtSurface) -> ConditionType:
        """
        Any surface the world bounds to some ground, which is the extent this finder
        states.

        :param sought: The description to state the condition over.
        """
        return sought.surface.region.area > 0.0

    def find(self, sought: SoughtSurface) -> WorkspaceSurface:
        """
        The surface exactly as the world models it.

        :param sought: The surface the world models, and the look it is sought in, which
            this finder does not read.
        """
        return sought.surface


@dataclass(eq=False)
class MeasuredSurfaceFinder(SurfaceFinder):
    """
    Answers a surface with the stretch of it the camera actually saw.

    The surface's own points are the ones standing at its plane inside the stretch the
    world already allows, so the answer is that stretch narrowed to what was seen --
    never grown past it, which is what keeps a run searching only ground the world had
    already described.

    ..note:: Compared by identity, for the reason :class:`ModelledSurfaceFinder` records.
    """

    scatter: float = SURFACE_SCATTER
    """
    How far a point may lie from the surface's plane and still belong to it, in metres.
    """

    def capability(self, sought: SoughtSurface) -> ConditionType:
        """
        Any surface the world bounds to some ground, looked for in a picture that
        carries depth: the bound is what a measurement narrows, and the depth is what it
        reads.

        What the world says is not the whole of what a finder needs -- a camera
        reporting only colour can be described a mirror-finished plane all day and still
        have nothing to measure one in -- so the picture is asked as well as the world.

        :param sought: The description to state the condition over.
        """
        return and_(
            sought.surface.region.area > 0.0,
            sought.frame.carries_depth == True,  # noqa: E712 - a stated condition
        )

    def find(self, sought: SoughtSurface) -> WorkspaceSurface:
        """
        The stretch of the modelled surface the camera saw.

        Only how far the surface reaches is measured. How high it stands is left as the
        world states it, because that is the half of the model this scene has *not*
        drifted away from -- the recorded layout put the board and the pieces in the
        wrong place while the table's height agreed exactly -- and because the lid's own
        plane is derived from the table's, so measuring one and not the other would
        leave the two surfaces describing different tables.

        :param sought: The surface the world models, and the look it is measured in.
        :raises WorkspaceOutOfView: If the stretch the world allows falls outside the
            picture entirely.
        :raises SurfaceNotSeenWhereTheWorldPutsIt: If nothing stands at the modelled
            plane inside that stretch.
        """
        modelled = sought.surface
        at_the_plane = self.points_standing_at(modelled, sought.frame)
        if not len(at_the_plane):
            raise SurfaceNotSeenWhereTheWorldPutsIt(str(modelled.name), modelled.height)
        surface_points = self._within(
            at_the_plane[
                np.abs(at_the_plane[:, 2] - np.median(at_the_plane[:, 2]))
                <= self.scatter
            ],
            modelled.region,
        )
        if not len(surface_points):
            raise SurfaceNotSeenWhereTheWorldPutsIt(str(modelled.name), modelled.height)
        return replace(modelled, region=self.reach_of(surface_points, modelled.region))

    def points_standing_at(
        self, modelled: WorkspaceSurface, frame: RgbdFrame
    ) -> np.ndarray:
        """
        The points the depth image measured about the plane the world puts a surface on.

        Only the pixels the surface's own space covers are read, since a surface cannot
        have been seen anywhere the world does not allow it to be, and how high a
        pixel's point stands is settled before where it stands is worked out -- a
        surface's own points are a small part even of that.

        :param modelled: The surface as the world models it.
        :param frame: The camera data to read.
        :return: The points, in the frame detections are reported in, shape ``(n, 3)``.
        """
        window = self._space_of(modelled).window_in(frame)
        depth = window.cut_from(frame.depth)
        reference_frame_R_camera = frame.reference_frame_T_camera[:3, :3]
        camera_position = frame.reference_frame_T_camera[:3, 3]
        across = (
            np.arange(window.left, window.left + window.width)
            - frame.intrinsics.principal_point_x
        ) / frame.intrinsics.focal_length_x
        down = (
            np.arange(window.top, window.top + window.height)
            - frame.intrinsics.principal_point_y
        ) / frame.intrinsics.focal_length_y
        rightwards = across[None, :] * depth
        downwards = down[:, None] * depth
        standing = (
            reference_frame_R_camera[2, 0] * rightwards
            + reference_frame_R_camera[2, 1] * downwards
            + reference_frame_R_camera[2, 2] * depth
            + camera_position[2]
        )
        measured = (depth > 0.0) & (np.abs(standing - modelled.height) <= self.scatter)
        camera_points = np.stack(
            [rightwards[measured], downwards[measured], depth[measured]]
        )
        return np.column_stack(
            [
                (reference_frame_R_camera[:2] @ camera_points).T + camera_position[:2],
                standing[measured],
            ]
        )

    def _space_of(self, modelled: WorkspaceSurface) -> WorkspaceBox:
        """
        The space a surface's own points can stand in: its stretch of plane, as thick as
        such a surface's points scatter.

        :param modelled: The surface as the world models it.
        """
        return WorkspaceBox(
            region=modelled.region,
            minimum_height=modelled.height - self.scatter,
            maximum_height=modelled.height + self.scatter,
        )

    @staticmethod
    def _within(points: np.ndarray, region: WorkspaceRegion) -> np.ndarray:
        """
        The points standing over a stretch of a plane, seen from above.

        :param points: Points in the reported frame, shape ``(n, 3)``.
        :param region: The stretch they must stand over.
        :return: Those of them that do, shape ``(m, 3)``.
        """
        return points[
            (points[:, 0] >= region.minimum_x)
            & (points[:, 0] <= region.maximum_x)
            & (points[:, 1] >= region.minimum_y)
            & (points[:, 1] <= region.maximum_y)
        ]

    @staticmethod
    def reach_of(points: np.ndarray, region: WorkspaceRegion) -> WorkspaceRegion:
        """
        The stretch a surface's own points cover, on the modelled region's own grid.

        Each edge is taken out to the sample beyond the outermost point rather than in,
        so a measured stretch is a whole number of the modelled region's own pixels away
        from its corner and rectifies the world onto the same lattice the unmeasured one
        did.

        :param points: The surface's own points, shape ``(n, 3)``.
        :param region: The stretch the world models, whose grid the answer lands on.
        """
        steps_out = np.floor(
            (points[:, :2] - [region.minimum_x, region.minimum_y]) / region.resolution
        ).min(axis=0)
        steps_back = np.ceil(
            (points[:, :2] - [region.minimum_x, region.minimum_y]) / region.resolution
        ).max(axis=0)
        minimum_x, minimum_y = region.to_world_position(*steps_out)
        maximum_x, maximum_y = region.to_world_position(*steps_back)
        return WorkspaceRegion(
            minimum_x=minimum_x,
            maximum_x=maximum_x,
            minimum_y=minimum_y,
            maximum_y=maximum_y,
            resolution=region.resolution,
        )


# %% the camera turned until the picture and the model agree


@dataclass(eq=False)
class FittedSurfaceFinder(SurfaceFinder, BeliefSource):
    """
    Answers a surface by turning the camera until what it sees stands where the world
    says it does, and keeps the turn.

    A plane the world describes and a depth image of it are two accounts of one rigid
    scene, so where they disagree one of them is wrong. This finder reads the
    disagreement as a *pose* error and says so twice over: it answers the surface
    measured through the corrected pose, and it holds that pose as a
    :class:`~experiments.montessori.perception.camera.BelievedCameraPose` for the next
    picture from the same camera.

    Only the tilt is fitted. A horizontal plane fixes which way is up and nothing else
    -- it says nothing about where along itself the camera stands, nor which way round
    it faces -- and the one half of the model this setup is known *not* to have drifted
    away from is the height, so a fit free to move the camera as well would spend the
    plane's own evidence hiding a model error in a translation.

    Unlike :class:`MeasuredSurfaceFinder`, the answer may reach *past* the stretch the
    world models rather than only inside it, up to :attr:`reaches_past`. That is the
    different contract this finder exists for: a fit that may correct where the camera
    stands is one whose measurement may move the model, not only cut it down.

    ..note:: Compared by identity, for the reason :class:`ModelledSurfaceFinder`
        records, and because two finders holding different beliefs are not one finder.
    """

    measurement: MeasuredSurfaceFinder = field(default_factory=MeasuredSurfaceFinder)
    """
    Reads the surface's own points out of the depth image, which is what the plane is
    fitted through and what its reach is then read from.
    """

    largest_trusted_tilt: float = LARGEST_TRUSTED_TILT
    """
    How far this fit may turn the camera before refusing, in radians.
    """

    reaches_past: float = 0.2
    """
    How far past the stretch the world models the surface may be found reaching, in
    metres.

    A bound rather than a suggestion: a fit allowed to move the model still may not
    grow a table across the room out of whatever else the depth image holds at that
    height.
    """

    believed_pose: Optional[BelievedCameraPose] = None
    """
    Where this finder currently believes the camera stands, or ``None`` before it has
    fitted anything.
    """

    def capability(self, sought: SoughtSurface) -> ConditionType:
        """
        Any surface the world bounds to some ground, looked for in a picture that
        carries depth: the bound says where to read, and the depth is the plane this
        fits the camera to.

        :param sought: The description to state the condition over.
        """
        return self.measurement.capability(sought)

    def find(self, sought: SoughtSurface) -> WorkspaceSurface:
        """
        Turn the camera until the plane stands level, then say how far the surface
        reaches as seen from there.

        :param sought: The surface the world models, and the look it is fitted in.
        :raises SurfaceNotSeenWhereTheWorldPutsIt: If nothing stands at the modelled
            plane.
        :raises CameraTiltedFurtherThanTrusted: If levelling the plane turns the camera
            further than this setup reads as a pose error, which is a disagreement
            about the model rather than about the pose.
        """
        modelled = sought.surface
        looked_over = replace(
            modelled, region=modelled.region.grown_by(self.reaches_past)
        )
        believed = self._levelled(sought, looked_over)
        turned = self._turn_between(
            sought.frame.reference_frame_T_camera, believed.reference_frame_T_camera
        )
        if turned > self.largest_trusted_tilt:
            raise CameraTiltedFurtherThanTrusted(turned, self.largest_trusted_tilt)
        seen_from_there = self._points_of(
            looked_over, believed.applied_to(sought.frame)
        )
        self.believed_pose = believed
        return replace(
            modelled,
            region=self.measurement.reach_of(seen_from_there, looked_over.region),
        )

    def _levelled(
        self, sought: SoughtSurface, looked_over: WorkspaceSurface
    ) -> BelievedCameraPose:
        """
        The pose that leaves the plane standing as level as one reading of it can say.

        One reading, not a fit driven to a fixed point. A surface's own points are
        picked out by standing within :attr:`MeasuredSurfaceFinder.scatter` of the
        height the world states, which is a horizontal slab; cut out of a plane that
        leans, it keeps the middle of the lean and neither end, so the plane fitted
        through it comes back flatter than the one it was cut from. Reading again
        through the corrected pose cuts a different slab out of a differently placed
        cloud, and on this setup's own captures that walks rather than settles.

        :param sought: The surface the world models, and the look it is fitted in.
        :param looked_over: That surface over the stretch this fit may find it reaching.
        :raises SurfaceNotSeenWhereTheWorldPutsIt: If nothing stands at its plane.
        """
        frame = (
            sought.frame
            if self.believed_pose is None
            else self.believed_pose.applied_to(sought.frame)
        )
        points = self._points_of(looked_over, frame)
        return BelievedCameraPose(self._turned_level(points, frame), self)

    @staticmethod
    def _turn_between(before: np.ndarray, after: np.ndarray) -> float:
        """
        How far one pose is turned from another, in radians.

        :param before: The pose turned from, as a 4x4 homogeneous transformation.
        :param after: The pose turned to, likewise.
        """
        turn = after[:3, :3] @ before[:3, :3].T
        return float(np.arccos(np.clip((np.trace(turn) - 1.0) / 2.0, -1.0, 1.0)))

    def tilt_of(self, points: np.ndarray) -> float:
        """
        How far the plane a set of points lies in stands away from level, in radians.

        :param points: The surface's own points, shape ``(n, 3)``.
        """
        upwards = self._upward_normal_of(points)
        return float(np.arccos(np.clip(upwards[2], -1.0, 1.0)))

    def _points_of(self, looked_over: WorkspaceSurface, frame: RgbdFrame) -> np.ndarray:
        """
        The surface's own points, as one picture shows them.

        :param looked_over: The surface, over the stretch this fit is allowed to find it
            reaching.
        :param frame: The camera data to read.
        :raises SurfaceNotSeenWhereTheWorldPutsIt: If nothing stands at its plane.
        :return: The points, shape ``(n, 3)``.
        """
        points = self.measurement.points_standing_at(looked_over, frame)
        if not len(points):
            raise SurfaceNotSeenWhereTheWorldPutsIt(
                str(looked_over.name), looked_over.height
            )
        return points

    def _turned_level(self, points: np.ndarray, frame: RgbdFrame) -> np.ndarray:
        """
        The camera's pose turned so that the plane its picture holds stands level.

        Turned about where the camera itself stands, so the point directly under it
        keeps the depth it was measured at and the plane keeps the height the world
        states for it.

        :param points: The surface's own points as this frame shows them, shape
            ``(n, 3)``.
        :param frame: The camera data they were read from.
        :return: The corrected pose, as a 4x4 homogeneous transformation.
        """
        upwards = self._upward_normal_of(points)
        corrected = np.eye(4)
        corrected[:3, :3] = (
            self._turning_onto_up(upwards) @ frame.reference_frame_T_camera[:3, :3]
        )
        corrected[:3, 3] = frame.reference_frame_T_camera[:3, 3]
        return corrected

    @staticmethod
    def _upward_normal_of(points: np.ndarray) -> np.ndarray:
        """
        The unit normal of the plane a set of points lies in, pointing upwards.

        :param points: The surface's own points, shape ``(n, 3)``.
        """
        centred = points - points.mean(axis=0)
        _, directions = np.linalg.eigh(centred.T @ centred)
        normal = directions[:, 0]
        return normal if normal[2] >= 0.0 else -normal

    @staticmethod
    def _turning_onto_up(upwards: np.ndarray) -> np.ndarray:
        """
        The rotation taking one unit direction onto the reference frame's own up.

        :param upwards: The direction to turn, as a unit vector.
        :return: The rotation, shape ``(3, 3)``.
        """
        axis = np.cross(upwards, [0.0, 0.0, 1.0])
        reach = float(np.linalg.norm(axis))
        if reach == 0.0:
            return np.eye(3)
        axis = axis / reach
        angle = float(np.arccos(np.clip(upwards[2], -1.0, 1.0)))
        across = np.array(
            [
                [0.0, -axis[2], axis[1]],
                [axis[2], 0.0, -axis[0]],
                [-axis[1], axis[0], 0.0],
            ]
        )
        return (
            np.eye(3)
            + math.sin(angle) * across
            + (1.0 - math.cos(angle)) * (across @ across)
        )


# %% choosing between them


@dataclass
class SurfaceRules(DetectorChoice[SoughtSurface]):
    """
    The rule tree that says which finder answers a surface of this scene.

    Its rules are krrood ripple-down rules whose conditions are entity query language
    expressions over the surface being sought itself, so a surface the rules get wrong
    is corrected by adding a rule rather than by editing the ones already stated, and
    the tree can be read
    (:meth:`~krrood.entity_query_language.backends.DetectorChoice.render_tree`) rather
    than only run.
    """

    modelled: SurfaceFinder = field(default_factory=ModelledSurfaceFinder)
    """
    Answers with what the world models the surface as.

    The general answer: it needs nothing of the picture, only that the world bounds the
    surface at all.
    """

    measured: SurfaceFinder = field(default_factory=MeasuredSurfaceFinder)
    """
    Answers with the stretch of the surface the camera actually saw.
    """

    def underspecified_look(self) -> Match:
        """
        A surface whose finder is to be worked out.
        """
        return a(SoughtSurface)(finder=...)

    def rules_stated_at_the_start(self) -> Entity:
        """
        Both finders answer any surface the world bounds, and on a picture carrying
        depth both answer it, so what tells them apart is how the surface takes light:
        a mirror-finished one is worth measuring, because its own model is what this
        scene has already drifted away from, and the model is the general answer
        everywhere else.
        """
        rules = entity(self.look).where(
            and_(
                self.look.surface.finish == SurfaceFinish.MIRROR,
                self.measured.capability(self.look),
            )
        )
        with rules:
            add(self.chosen_detector, self.measured)
            with alternative(self.modelled.capability(self.look)):
                add(self.chosen_detector, self.modelled)
        return rules

    def nothing_answers(self, sought: SoughtSurface) -> NoSurfaceFinderAnswersTheLook:
        """
        :param sought: The surface no rule reached.
        """
        return NoSurfaceFinderAnswersTheLook(str(sought))

    def situation_answered_by(
        self,
        finder: SurfaceFinder,
        sought: SoughtSurface,
        example: SoughtSurface,
    ) -> Optional[ConditionType]:
        """
        How the surface takes light is what these rules decide by, so a rule added for a
        finder other than the general one holds only on surfaces finished like the one
        it was stated from.

        :param finder: The finder a rule is being stated for.
        :param sought: The variable the condition is stated over.
        :param example: The surface the rule is being stated from.
        :return: The situation, or ``None`` where the rules hold none.
        """
        if finder is self.modelled:
            return None
        return sought.surface.finish == example.surface.finish

    def surface_in(
        self, modelled: WorkspaceSurface, frame: RgbdFrame
    ) -> WorkspaceSurface:
        """
        How far a surface reaches in one frame, answered by the finder the rules choose.

        :param modelled: The surface as the world models it.
        :param frame: The camera data the surface is looked for in.
        :raises NoSurfaceFinderAnswersTheLook: If no finder answers what the world says
            about it.
        """
        sought = SoughtSurface(modelled, frame)
        return self.detector_for(sought).find(sought)
