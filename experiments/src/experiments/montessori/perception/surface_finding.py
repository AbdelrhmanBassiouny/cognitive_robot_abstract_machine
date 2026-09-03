"""
Where a surface reaches, worked out from what the world says it is like.

Every surface this package searches has so far been taken from a model: a rectangle
written down for the recordings, or the widest horizontal face of the body the twin
places. Neither is a measurement of where the table really is, and this scene has
already drifted away from its own model once.

So a surface is *described* instead -- how it takes light, and how far the world says it
reaches -- and which finder answers that description is a rule over it, exactly as
:mod:`~experiments.montessori.perception.detector_choice` decides which detector reads a
piece off a surface. A surface the world says colour cannot outline is measured in the
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
from functools import cached_property

import numpy as np
from krrood.entity_query_language.factories import (
    ConditionType,
    add,
    an,
    and_,
    deduced_variable,
    entity,
    refinement,
    variable,
)
from krrood.entity_query_language.rules.conclusion_selector import Alternative
from typing_extensions import TYPE_CHECKING, Optional

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.exceptions import (
    NoSurfaceFinderAnswersTheLook,
    SurfaceNotSeenWhereTheWorldPutsIt,
)
from experiments.montessori.perception.orthophoto import WorkspaceBox, WorkspaceRegion
from experiments.montessori.perception.surfaces import WorkspaceSurface
from semantic_digital_twin.world_description.geometry import SurfaceFinish

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.query.query import Query

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


@dataclass(frozen=True)
class SoughtSurface:
    """
    One surface being looked for, and what the world says about it.

    Everything a rule reads is stated here rather than reached for through the world, so
    a rule is a condition over plain properties and the reading of the world happens
    once in :meth:`of`.
    """

    finish: Optional[SurfaceFinish]
    """
    How the surface takes the light that falls on it, or ``None`` where the world states
    no finish for it.
    """

    extent_is_modelled: bool
    """
    Whether the world says how far the surface reaches.

    That bound is what the model states outright and what a measurement narrows, so a
    surface without one is one neither finder can answer.
    """

    depth_was_returned: bool = True
    """
    Whether the camera returned any depth for the look this surface is sought in.

    What the world says is not the whole of what a finder needs: a camera that reports
    only colour can be described a mirror-finished plane all day and still have nothing
    to measure one in.
    """

    @classmethod
    def of(cls, surface: WorkspaceSurface, frame: RgbdFrame) -> SoughtSurface:
        """
        What the world says about a surface, and what one look offers to find it with.

        :param surface: The surface as the world models it.
        :param frame: The camera data it is being looked for in.
        """
        return cls(
            finish=surface.finish,
            extent_is_modelled=True,
            depth_was_returned=bool((frame.depth > 0.0).any()),
        )


# %% what a finder says it can answer


class SurfaceFinder(ABC):
    """
    Something that says how far one horizontal surface reaches.

    A finder states the surfaces it can answer, so the choice between finders is made by
    matching a description against what each one says rather than by a caller knowing
    which is which.
    """

    @abstractmethod
    def capability(self, sought: SoughtSurface) -> ConditionType:
        """
        The surfaces this finder can answer, as a condition over a description.

        Written as an entity query language condition rather than as a predicate on a
        value, so the same statement both decides one surface and forms part of the rule
        tree that chooses between finders.

        :param sought: The :class:`SoughtSurface` variable to state the condition over.
        :return: The condition, which holds exactly for the surfaces this finder
            answers.
        """

    @cached_property
    def stated_surface(self) -> SoughtSurface:
        """
        The variable this finder states its own capability over.

        The statement is made once and one description at a time is bound to this to ask
        it.
        """
        return variable(SoughtSurface, domain=[])

    @cached_property
    def answerable_surfaces(self) -> Query:
        """
        The surfaces this finder can answer, stated once over :attr:`stated_surface`.
        """
        return an(
            entity(self.stated_surface).where(self.capability(self.stated_surface))
        )

    def answers(self, sought: SoughtSurface) -> bool:
        """
        Whether this finder declares it can answer one description.

        :param sought: The description to put to it.
        """
        self.stated_surface._update_domain_([sought])
        return bool(self.answerable_surfaces.tolist())

    @abstractmethod
    def find(self, modelled: WorkspaceSurface, frame: RgbdFrame) -> WorkspaceSurface:
        """
        Say how far the surface reaches and how high its plane stands.

        :param modelled: The surface as the world models it, which is what a measurement
            narrows and what a reading of the model answers outright.
        :param frame: The camera data the surface is looked for in.
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
        Any surface the world bounds, which is the extent this finder states.

        :param sought: The description to state the condition over.
        """
        return sought.extent_is_modelled == True  # noqa: E712 - a stated condition

    def find(self, modelled: WorkspaceSurface, frame: RgbdFrame) -> WorkspaceSurface:
        """
        The surface exactly as the world models it.

        :param modelled: The surface as the world models it.
        :param frame: The camera data, which this finder does not read.
        """
        return modelled


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
        Any surface the world bounds, looked for in a picture that carries depth: the
        bound is what a measurement narrows, and the depth is what it reads.

        :param sought: The description to state the condition over.
        """
        return and_(
            sought.extent_is_modelled == True,  # noqa: E712 - a stated condition
            sought.depth_was_returned == True,  # noqa: E712 - a stated condition
        )

    def find(self, modelled: WorkspaceSurface, frame: RgbdFrame) -> WorkspaceSurface:
        """
        The stretch of the modelled surface the camera saw.

        Only how far the surface reaches is measured. How high it stands is left as the
        world states it, because that is the half of the model this scene has *not*
        drifted away from -- the recorded layout put the board and the pieces in the
        wrong place while the table's height agreed exactly -- and because the lid's own
        plane is derived from the table's, so measuring one and not the other would
        leave the two surfaces describing different tables.

        :param modelled: The surface as the world models it.
        :param frame: The camera data the surface is measured in.
        :raises WorkspaceOutOfView: If the stretch the world allows falls outside the
            picture entirely.
        :raises SurfaceNotSeenWhereTheWorldPutsIt: If nothing stands at the modelled
            plane inside that stretch.
        """
        at_the_plane = self._points_standing_at(modelled, frame)
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

    Its rules are krrood ripple-down rules, so a surface the rules get wrong is
    corrected by adding an exception under it rather than by editing the rule, and every
    condition is an entity query language expression over what the world states.

    The tree is stated once, when the rules are built, and each surface is decided by
    binding its description to :attr:`stated_surface` and evaluating that one tree. It
    outlives the surfaces it decides, so it can be read, and a surface it gets wrong can
    be given a rule through :meth:`add_rule` while it is in use.
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

    stated_surface: SoughtSurface = field(init=False, repr=False, compare=False)
    """
    The variable every rule states its conditions over, which one description at a time
    is bound to.
    """

    chosen_finder: SurfaceFinder = field(init=False, repr=False, compare=False)
    """
    The variable the rules conclude, which a surface's answer is read from.
    """

    rule_tree: Query = field(init=False, repr=False, compare=False)
    """
    The rules themselves, as one live tree that outlives the surfaces it decides.
    """

    latest_rule: SymbolicExpression = field(init=False, repr=False, compare=False)
    """
    The most recently stated exception, which the next one is attached beside so the
    exceptions to the base rule form one chain and a surface reaches at most one of
    them.
    """

    def __post_init__(self) -> None:
        """
        State the rules, once, over the variables the descriptions are bound to.
        """
        self.stated_surface = variable(SoughtSurface, domain=[])
        self.chosen_finder = deduced_variable(SurfaceFinder)
        self.rule_tree = entity(self.chosen_finder).where(
            self.modelled.capability(self.stated_surface)
        )
        with self.rule_tree:
            add(self.chosen_finder, self.modelled)
            self.latest_rule = refinement(
                and_(
                    self.stated_surface.finish == SurfaceFinish.MIRROR,
                    self.measured.capability(self.stated_surface),
                )
            )
            with self.latest_rule:
                add(self.chosen_finder, self.measured)

    def add_rule(self, condition: ConditionType, finder: SurfaceFinder) -> None:
        """
        State a surface the rules do not yet cover.

        The rule joins the tree already in use, so a surface the rules got wrong is
        answered by *finder* from the next call onwards without any of them being
        rewritten.

        :param condition: What holds of the surface, stated over :attr:`stated_surface`.
        :param finder: The finder that answers such a surface.
        """
        self.latest_rule = Alternative.insert_at(self.latest_rule, condition)
        with self.latest_rule:
            add(self.chosen_finder, finder)

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
        return self.finder_for(SoughtSurface.of(modelled, frame)).find(modelled, frame)

    def finder_for(self, sought: SoughtSurface) -> SurfaceFinder:
        """
        The finder that answers one description.

        :param sought: What the world says about the surface being looked for.
        :raises NoSurfaceFinderAnswersTheLook: If no finder declares it can answer.
        """
        self.stated_surface._update_domain_([sought])
        answered = self.rule_tree.tolist()
        if not answered:
            raise NoSurfaceFinderAnswersTheLook(str(sought))
        [finder] = answered
        return finder
