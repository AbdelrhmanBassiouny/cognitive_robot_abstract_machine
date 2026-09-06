"""
How a look at the Montessori scene is answered, concluded from what was asked for.

A statement asks for a kind of thing, and what has to be run to answer it differs with
what was asked: a request about the board is answered by finding the board, a request
about the pieces by searching every surface they can rest on. That choice used to be a
branch written into the pipeline, which meant a request nobody foresaw could only be
answered by editing the code that reads it.

It is a rule tree here instead, stated over the request itself -- the description of
what is sought, which is what the rules are asked about and what a condition reads. The
tree is krrood's
:class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`, built from
the underspecified statement *a request whose detector is to be worked out*, so what is
described and what is left open are read off that statement rather than named again
here.

Each detector states the requests it can answer as an entity query language condition,
which is
:meth:`~krrood.entity_query_language.backends.PerceptionDetector.capability` and is the
same statement every family of detectors makes about itself, so a detector added to the
rules brings its own condition with it. No two of these say the same, so each rule is
one detector's capability and nothing more.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from krrood.entity_query_language.backends import DetectorChoice, PerceptionDetector
from krrood.entity_query_language.factories import a, add, alternative, entity
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.query.query import Entity
import numpy as np
from typing_extensions import Dict, List, Optional

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
)
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.exceptions import (
    LookHasNoReferenceFrame,
    NoDetectorAnswersTheRequest,
)
from experiments.montessori.perception.explanations import CompetingExplanations
from experiments.montessori.perception.hypotheses import (
    BelievedPlace,
    PieceHypothesis,
    YawInterval,
)
from experiments.montessori.perception.imagination import ImaginedWorld
from experiments.montessori.perception.occupancy import OccupiedVolume
from experiments.montessori.perception.orthophoto import (
    Orthophoto,
    OrthophotoProjector,
    WorkspaceRegion,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from experiments.montessori.pieces import (
    KNOWN_PIECE_BY_CATEGORY,
    LOOSE_PIECE_HEIGHT,
    pieces_colored,
)
from experiments.montessori.planar_geometry import PlanarPoint
from experiments.montessori.semantics import MontessoriShape
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% the material one look works over


@dataclass
class RectifiedFrame:
    """
    One camera frame, and every horizontal plane it has been rectified onto.

    A plane is rectified once however many detectors read it: the surfaces a look
    searches and the detectors chosen for them ask for overlapping planes, and
    rectifying is the most expensive thing a look does.
    """

    frame: RgbdFrame
    """
    The camera data every plane is rectified from.
    """

    projector: OrthophotoProjector
    """
    Rectifies the frame onto a plane, over the stretch of table perception searches.
    """

    views: Dict[float, Orthophoto] = field(default_factory=dict)
    """
    The planes rectified so far, by their height above the world frame's origin.
    """

    edges: Dict[float, EdgeDistances] = field(default_factory=dict)
    """
    The edges read off each rectified plane so far, by that plane's height.
    """

    def at(self, height: float) -> Orthophoto:
        """
        The frame rectified onto one horizontal plane.

        :param height: Height of the plane above the world frame's origin, in metres.
        """
        if height not in self.views:
            self.views[height] = self.projector.project(self.frame, height)
        return self.views[height]

    def edges_at(self, height: float) -> EdgeDistances:
        """
        How far each point of one rectified plane lies from an edge the camera saw.

        :param height: Height of the plane above the world frame's origin, in metres.
        """
        if height not in self.edges:
            self.edges[height] = EdgeDistances.of(self.at(height))
        return self.edges[height]


@dataclass
class SceneToSearch:
    """
    Everything a look has to work with: what was asked for, where the camera stood, and
    the frame it returned.

    A way of looking is handed one of these and nothing else, so what answers a look is
    the request, the camera and the pictures rather than a pipeline configured in
    advance.
    """

    frame: RgbdFrame
    """
    The camera data this look reads.
    """

    table: WorkspaceSurface
    """
    The surface the scene is set up on, and the patch of it this look searches.
    """

    lid: WorkspaceSurface
    """
    The board's lid: the second surface pieces rest on, and the plane its holes lie in.
    """

    reference_frame: Optional[KinematicStructureEntity] = None
    """
    Frame the detections' poses are expressed in, which must be the frame the camera's
    own pose was given in.
    """

    request: SceneRequest = SceneRequest()
    """
    What this look was asked for, unnarrowed by default.
    """

    world: Optional[World] = None
    """
    The world the robot already keeps, which says what pieces it has placed in the
    workspace and so where a look may expect to find them.

    ``None`` where a look has no world behind it at all, as a recorded frame does.
    """

    explanations: CompetingExplanations = field(default_factory=CompetingExplanations)
    """
    How much better one account of a place must be than the next before it is reported.

    A statement about what a wrong report costs whoever asked for the look, so it
    belongs to the look rather than to the detector that takes it.
    """

    headroom: float = 0.15
    """
    How far above the table, in metres, the view still holds something worth seeing.

    Wide enough for the board's lid and for a piece held over it on its way in; anything
    higher is a passing arm or the room behind the table.
    """

    rectified: RectifiedFrame = field(init=False, repr=False)
    """
    The frame rectified onto each plane this look reads, built once however many
    detectors ask for the same plane.
    """

    def __post_init__(self) -> None:
        self.rectified = RectifiedFrame(
            frame=self.frame, projector=OrthophotoProjector(region=self.table.region)
        )

    def imagine(self) -> ImaginedWorld:
        """
        Take the world this look is about to stand its findings in.

        :return: A copy of the world this look reads, reporting in the frame this look
            places its detections in.
        """
        return ImaginedWorld.copied_from(self.world, self.reference_frame)

    def searched_surfaces(
        self, board: Optional[MontessoriBoardDetection]
    ) -> List[SurfaceSearch]:
        """
        The surfaces this look searches, each with the part of its plane it may claim.

        The table is everything but where the board stands; the board's lid is the board
        itself, and only where it was actually seen. A request naming one of them drops
        the other, so a look asked about one surface rectifies and searches one plane,
        and a region the statement names cuts each remaining plane down to where the
        thing sought may actually be.

        :param board: The board, or None if it was not in view.
        :return: One entry per surface a piece can be found on that the request asked
            about and left anything of to search.
        """
        if board is None:
            searches = [SurfaceSearch(surface=self.table)]
        else:
            searches = [
                SurfaceSearch(surface=self.table, supported_surfaces=(board,)),
                SurfaceSearch(surface=self.lid, boundary=board),
            ]
        asked_about = [
            search for search in searches if self.request.searches(search.surface.name)
        ]
        narrowed = [self._narrowed(search) for search in asked_about]
        return [search for search in narrowed if search is not None]

    def _narrowed(self, search: SurfaceSearch) -> Optional[SurfaceSearch]:
        """
        One surface's search, cut down to the stretch of its own plane the statement
        allows.

        :param search: The surface being searched, before the statement narrows it.
        :return: The narrowed search, or None where the statement leaves none of this
            surface to read.
        """
        if not self.request.placements:
            return search
        allowed = self.stated_region(search)
        if allowed is None:
            return None
        return replace(search, narrowed_to=allowed)

    def stated_region(self, search: SurfaceSearch) -> Optional[WorkspaceRegion]:
        """
        The stretch of one surface's own plane this look's statement says the thing
        sought lies in.

        A relation is stated between things the world holds, so what it leaves in metres
        is read here, where the frame the detections are reported in is known, rather
        than where the statement was compiled. Each is asked about the stretch this
        surface was going to read rather than about the world, because a direction read
        from where the camera stands runs across the world's own axes and no axis-
        aligned patch holds everything such a direction allows, while the part of one
        surface's plane on that side of a thing is a patch. Several of them compose,
        each narrowing what the one before it left.

        :param search: The surface being searched, before this narrowing.
        :raises LookHasNoReferenceFrame: If the statement says where the thing lies but
            this look reports its detections in no frame, which leaves the relation
            nothing to be read against.
        :return: The patch the statement leaves of this surface, or None where it leaves
            none of it.
        """
        if self.reference_frame is None:
            raise LookHasNoReferenceFrame(type(self.request.placements[0]).__name__)
        allowed = self._space_over(search)
        for placement in self.request.placements:
            allowed = placement.allowed_part_of(allowed)
            if allowed is None:
                return None
        return WorkspaceRegion(
            minimum_x=allowed.x_interval.lower,
            maximum_x=allowed.x_interval.upper,
            minimum_y=allowed.y_interval.lower,
            maximum_y=allowed.y_interval.upper,
            resolution=self.table.region.resolution,
        )

    def _space_over(self, search: SurfaceSearch) -> VolumetricBoundingBox:
        """
        The stretch of the world one pass of a surface reads: how far the surface itself
        reaches, and how high above it a thing standing on it is reported.

        A relation says where a thing stands rather than where its surface is, so the
        height matters: read at the plane alone, a direction tilted away from it would
        leave out ground a thing standing on that plane is allowed.

        :param search: The surface being searched.
        """
        reach = search.region
        standing = search.surface.height + LOOSE_PIECE_HEIGHT
        return VolumetricBoundingBox.from_array_bounds(
            np.array([reach.minimum_x, reach.minimum_y, search.surface.height]),
            np.array([reach.maximum_x, reach.maximum_y, standing]),
            HomogeneousTransformationMatrix.from_xyz_rpy(
                reference_frame=self.reference_frame
            ),
        )

    def table_hidden_by(self, board: MontessoriBoardDetection) -> OccupiedVolume:
        """
        The stretch of table the board takes out of the search: what it stands on, and
        what it stands in front of.

        A piece on the lid is seen against the table behind the board, so the table's
        own pass reads it as something resting there. The shadow is cast from the top of
        a piece standing on the lid rather than from the lid itself, since that is what
        actually stands between the camera and the table. Only the space up to the lid
        is taken, so a piece resting on the lid stands above it and keeps its own place.

        :param board: The board as it was seen.
        """
        standing_on_the_lid = OccupiedVolume(
            outline=board.outline,
            bottom=board.lid_height,
            top=board.lid_height + LOOSE_PIECE_HEIGHT,
        )
        return standing_on_the_lid.hides(self.table.height, self.frame.camera_position)

    def expected_pieces(self) -> List[PieceHypothesis]:
        """
        Where a piece may be, from what the robot knows before anything is segmented.

        The world already places the pieces the robot has put in the workspace and names
        which piece each one is, and a belief that names one piece at one place needs no
        colour to separate it from what it rests on -- which is what a piece wearing
        that surface's own hue never has. Anything believed more particularly than the
        world can say is supplied by whoever asks for the look.

        :return: One hypothesis per place a piece is expected.
        """
        if self.world is None:
            return []
        placed = []
        for shape in self.world.get_semantic_annotations_by_type(MontessoriShape):
            position = shape.root.global_pose.to_position().to_np()[:2]
            if not self.table.region.contains(float(position[0]), float(position[1])):
                continue
            placed.extend(
                PieceHypothesis(
                    place=BelievedPlace(
                        surface=surface.name,
                        center=PlanarPoint(x=float(position[0]), y=float(position[1])),
                    ),
                    source=self.world,
                    candidates=(KNOWN_PIECE_BY_CATEGORY[shape.shape_category],),
                )
                for surface in (self.table, self.lid)
            )
        return placed

    def believed_from(self, search: SurfaceSearch) -> List[PieceHypothesis]:
        """
        What whoever asked for the look believes is on one surface, read from where the
        statement says the thing sought lies.

        A placement that confines the thing closely -- within a radius of a hole, inside
        a region -- is a place worth fitting a piece at whether or not any colour
        separates one there, so it is evaluated the way a place the world believes in
        is. The pieces tried are the ones that have the stated colour, or every piece
        where none is stated, and the turns tried are the ones the statement allows.

        :param search: The surface being searched.
        :return: One hypothesis where the request confines the thing sought and someone
            vouches for it, and none otherwise.
        """
        stretch = self.request.believed_stretch()
        if self.request.believed_by is None or stretch is None:
            return []
        across = stretch.x_interval.upper - stretch.x_interval.lower
        along = stretch.y_interval.upper - stretch.y_interval.lower
        turn = self.request.turn
        return [
            PieceHypothesis(
                place=BelievedPlace(
                    surface=search.surface.name,
                    center=PlanarPoint(
                        x=stretch.x_interval.lower + across / 2,
                        y=stretch.y_interval.lower + along / 2,
                    ),
                    radius=max(across, along) / 2,
                    yaw=(
                        None
                        if turn is None
                        else YawInterval(center=turn.yaw, spread=turn.spread)
                    ),
                ),
                source=self.request.believed_by,
                candidates=pieces_colored(self.request.color),
            )
        ]


# %% what a detector of this scene is


class SceneDetector(PerceptionDetector[SceneRequest], ABC):
    """
    Something that answers a look at the Montessori scene.

    Its capability is stated over the request itself, so a detector is chosen by
    matching what was asked for against what each detector says it can answer rather
    than by naming detectors in the code that reads the request.
    """

    @abstractmethod
    def detect(self, scene: SceneToSearch) -> MontessoriScene:
        """
        Take the look this detector was chosen for.

        :param scene: What was asked for, and the frame to answer it from.
        :return: What the look found.
        """


# %% the rules


@dataclass
class LookRules(DetectorChoice[SceneRequest]):
    """
    The rule tree that says which detector answers a look at this scene.

    Its rules are krrood ripple-down rules whose conditions are entity query language
    expressions over the request itself, so a request the rules get wrong is corrected
    by adding a rule rather than by editing the ones already stated, and the tree can be
    read (:meth:`~krrood.entity_query_language.backends.DetectorChoice.render_tree`)
    rather than only run.
    """

    find_the_board: SceneDetector
    """
    Answers a request the board or one of its holes can answer.
    """

    find_the_pieces: SceneDetector
    """
    Answers a request a loose piece can answer, reporting the board it measured the
    surfaces by along with them.
    """

    def underspecified_look(self) -> Match:
        """
        A request whose detector is to be worked out.
        """
        return a(SceneRequest)(detector=...)

    def rules_stated_at_the_start(self) -> Entity:
        """
        Each detector answers the requests it says it can, and no two of them say the
        same, so what a request asks for settles the choice on its own.

        Searching the surfaces comes first, so a request narrowed to neither is answered
        by the detector that reports both.
        """
        rules = entity(self.look).where(self.find_the_pieces.capability(self.look))
        with rules:
            add(self.chosen_detector, self.find_the_pieces)
            with alternative(self.find_the_board.capability(self.look)):
                add(self.chosen_detector, self.find_the_board)
        return rules

    def nothing_answers(self, request: SceneRequest) -> NoDetectorAnswersTheRequest:
        """
        :param request: The request no rule reached.
        """
        return NoDetectorAnswersTheRequest(str(request))
