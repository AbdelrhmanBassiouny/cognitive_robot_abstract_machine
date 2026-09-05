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
here. A surface the world says colour cannot outline is measured in the
depth image; one it says nothing about is taken from the model, because a description
nothing states is not one a look can be compiled from.

..note:: A plane fit answers the *surface* and not what rests on it. The point-cloud
    trial this measurement follows found a plane holding a third of the points on the
    bare steel and no piece standing out of that cloud at all, which is why pieces are
    read by fitting known outlines to edges instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

import numpy as np
from krrood.entity_query_language.backends import Look, PerceptionDetector
from krrood.entity_query_language.factories import ConditionType, a, and_
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.serialization import NullModelSaver
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from typing_extensions import Any, Dict, List, Optional, Tuple

from experiments.montessori.perception.camera import CameraIntrinsics, RgbdFrame
from experiments.montessori.perception.exceptions import (
    NoSurfaceFinderAnswersTheLook,
    SurfaceNotSeenWhereTheWorldPutsIt,
)
from experiments.montessori.perception.orthophoto import WorkspaceBox, WorkspaceRegion
from experiments.montessori.perception.surfaces import WorkspaceSurface
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
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
        at_the_plane = self._points_standing_at(modelled, sought.frame)
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
        return replace(modelled, region=self._reach_of(surface_points, modelled.region))

    def _points_standing_at(
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
    def _reach_of(points: np.ndarray, region: WorkspaceRegion) -> WorkspaceRegion:
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


# %% choosing between them


@dataclass
class SurfaceRules:
    """
    The rule tree that says which finder answers a surface of this scene.

    Its rules are krrood ripple-down rules whose conditions are entity query language
    expressions over the surface being sought itself, so a surface the rules get wrong
    is corrected by adding a rule rather than by editing the ones already stated, and
    the tree can be read (:meth:`render_tree`) rather than only run.
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

    rules: EQLSingleClassRDR = field(init=False, repr=False, compare=False)
    """
    The rules themselves, as one tree that outlives the surfaces it decides.

    Nothing is persisted when a rule is added: a rule concludes the finder itself rather
    than a name for one, and the engine writes a model file as Python source, which can
    spell an enum member or a number but not a collaborator. The rules are recovered by
    stating them again from the finders, which is what building this does.
    """

    expert: Expert = field(init=False, repr=False, compare=False)
    """
    Asked for a new rule's condition, which it reads off
    :meth:`state_the_condition_this_rule_needs`.
    """

    def __post_init__(self) -> None:
        """
        State the rules by fitting the surfaces each finder answers.

        The engine authors its own tree, so a rule is written by putting a known kind of
        sought surface and the finder that answers it to it.
        """
        self.expert = Expert(
            interface=FunctionInterface(
                answer_function=self.state_the_condition_this_rule_needs
            )
        )
        self.rules = EQLSingleClassRDR.from_underspecified(
            a(SoughtSurface)(finder=...), model_saver=NullModelSaver()
        )
        answered = self.surfaces_each_finder_answers()
        self.rules.fit(
            cases=[sought for sought, _ in answered],
            targets=[finder for _, finder in answered],
            expert=self.expert,
        )

    def state_the_condition_this_rule_needs(
        self, context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        """
        Answer the engine's question about a new rule with what the finder says it can
        answer, narrowed by the situation these rules choose it in.

        A capability alone does not tell the finders apart -- both answer any surface
        the world bounds, and on a picture with depth both answer it -- so the condition
        a rule needs is the capability *and* whatever these rules know about when that
        finder is worth running.

        :param context: The surface being fitted, and the finder it is fitted to.
        :param requests: The answers asked for, which this reads nothing from.
        :return: The conditions answer.
        """
        capability = context.target_conclusion.capability(context.case_variable)
        situation = self.situation_answered_by(
            context.target_conclusion, context.case_variable, context.case_instance
        )
        if situation is None:
            return {AnswerName.CONDITIONS: capability}
        return {AnswerName.CONDITIONS: and_(situation, capability)}

    def situation_answered_by(
        self, finder: SurfaceFinder, sought: SoughtSurface, example: SoughtSurface
    ) -> Optional[ConditionType]:
        """
        What these rules know about when a finder is worth running, over and above what
        it says it can answer.

        How the surface takes light is what these rules decide by: the model is the
        general answer and needs no situation of its own, and every other finder is
        worth its cost on the finishes it was stated for, which is read off the surface
        the rule is being stated from rather than named again here.

        :param finder: The finder a rule is being stated for.
        :param sought: The variable the condition is stated over.
        :param example: The surface the rule is being stated from.
        :return: The situation, or ``None`` where the rules hold none.
        """
        if finder is self.modelled:
            return None
        return sought.surface.finish == example.surface.finish

    def surfaces_each_finder_answers(
        self,
    ) -> List[Tuple[SoughtSurface, SurfaceFinder]]:
        """
        The known kinds of sought surface, each paired with the finder that answers it.

        A surface nothing is stated about is fitted alongside the mirror-finished one,
        so the rules are held to answering it from the model rather than left to happen
        to.
        """
        bounds = WorkspaceRegion(
            minimum_x=0.0, maximum_x=1.0, minimum_y=0.0, maximum_y=1.0
        )
        return [
            (
                SoughtSurface(
                    self.a_surface_of(bounds), self.a_picture_carrying_depth(False)
                ),
                self.modelled,
            ),
            (
                SoughtSurface(
                    self.a_surface_of(bounds, SurfaceFinish.MIRROR),
                    self.a_picture_carrying_depth(True),
                ),
                self.measured,
            ),
        ]

    @staticmethod
    def a_surface_of(
        bounds: WorkspaceRegion, finish: Optional[SurfaceFinish] = None
    ) -> WorkspaceSurface:
        """
        A surface of a kind the rules are stated from, bounded to some ground so both
        finders declare they can answer it.

        :param bounds: The stretch of plane it covers.
        :param finish: How it takes light, or ``None`` where nothing is stated.
        """
        return WorkspaceSurface(
            name=PrefixedName("a_surface_the_rules_are_stated_from", "surface_finding"),
            region=bounds,
            height=0.0,
            finish=finish,
        )

    @staticmethod
    def a_picture_carrying_depth(carries_depth: bool) -> RgbdFrame:
        """
        A picture of a kind the rules are stated from, as small as one can be.

        Only whether the camera returned any depth at all separates the kinds of look
        the rules tell apart, so a single pixel says everything a rule reads of a
        picture, and nothing is claimed about a scene that was never photographed.

        :param carries_depth: Whether the camera returned a depth reading.
        """
        return RgbdFrame(
            color=np.zeros((1, 1, 3), dtype=np.uint8),
            depth=np.full((1, 1), 1.0 if carries_depth else 0.0),
            intrinsics=CameraIntrinsics(
                focal_length_x=1.0,
                focal_length_y=1.0,
                principal_point_x=0.0,
                principal_point_y=0.0,
            ),
            reference_frame_T_camera=np.eye(4),
        )

    def add_rule(self, sought: SoughtSurface, finder: SurfaceFinder) -> None:
        """
        State a kind of surface the rules do not yet cover.

        The rule joins the tree already in use, so such a surface is answered by
        *finder* from the next call onwards without any of the rules already stated
        being rewritten. That is what a tree of rules is for, and it is the path an
        expert correcting an answer takes.

        :param sought: The kind of surface that was not covered.
        :param finder: The finder that answers it.
        """
        self.rules.fit_case(sought, finder, self.expert)

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
        return self.finder_for(sought).find(sought)

    def finder_for(self, sought: SoughtSurface) -> SurfaceFinder:
        """
        The finder that answers one description.

        :param sought: What the world says about the surface being looked for.
        :raises NoSurfaceFinderAnswersTheLook: If no rule reaches this surface.
        """
        concluded = self.rules.classify(sought)
        if concluded is ...:
            raise NoSurfaceFinderAnswersTheLook(str(sought))
        return concluded

    def render_tree(self, sought: SoughtSurface) -> str:
        """
        The rules as a tree, with the rule that answers one surface marked out.

        :param sought: The surface to read the tree for.
        """
        return self.rules.render_tree(sought, use_color=False)
