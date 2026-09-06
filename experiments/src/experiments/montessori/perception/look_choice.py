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
from dataclasses import dataclass, field

from krrood.entity_query_language.backends import DetectorChoice, PerceptionDetector
from krrood.entity_query_language.factories import a, add, alternative, entity
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.query.query import Entity
from typing_extensions import Dict, List, Optional

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
)
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.exceptions import (
    NoDetectorAnswersTheRequest,
)
from experiments.montessori.perception.orthophoto import Orthophoto, OrthophotoProjector
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
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

    rectified: RectifiedFrame = field(init=False, repr=False)
    """
    The frame rectified onto each plane this look reads, built once however many
    detectors ask for the same plane.
    """

    def __post_init__(self) -> None:
        self.rectified = RectifiedFrame(
            frame=self.frame, projector=OrthophotoProjector(region=self.table.region)
        )

    def searched_surfaces(
        self, board: Optional[MontessoriBoardDetection]
    ) -> List[SurfaceSearch]:
        """
        The surfaces this look searches, each with the part of its plane it may claim.

        The table is everything but where the board stands; the board's lid is the board
        itself, and only where it was actually seen. A request naming one of them drops
        the other, so a look asked about one surface rectifies and searches one plane.

        :param board: The board, or None if it was not in view.
        :return: One entry per surface a piece can be found on and the request asked
            about.
        """
        if board is None:
            searches = [SurfaceSearch(surface=self.table)]
        else:
            searches = [
                SurfaceSearch(surface=self.table, supported_surfaces=(board,)),
                SurfaceSearch(surface=self.lid, boundary=board),
            ]
        return [
            search for search in searches if self.request.searches(search.surface.name)
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
