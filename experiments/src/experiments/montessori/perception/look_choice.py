"""
How a look at the Montessori scene is answered, concluded from what was asked for.

A statement asks for a kind of thing, and what has to be run to answer it differs with
what was asked: a request about the board is answered by finding the board, a request
about the pieces by searching every surface they can rest on. That choice used to be a
branch written into the pipeline, which meant a request nobody foresaw could only be
answered by editing the code that reads it.

It is a rule tree here instead, over what the request states, so a new kind of request
is given a rule by an expert while the rules are in use. The tree is krrood's
:class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`, whose rules
are authored by fitting known requests through an expert -- the same path an expert
correcting an answer later takes, rather than a separate authoring model.

Each way of looking states the requests it can answer as an entity query language
condition, exactly as
:meth:`~experiments.montessori.perception.detector_choice.PieceDetector.capability`
states the looks a detector answers, so a way added to the rules brings its own
condition with it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from krrood.entity_query_language.factories import ConditionType
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

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
    MontessoriShapeDetection,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.exceptions import (
    NoWayOfLookingAnswersTheRequest,
)
from experiments.montessori.perception.orthophoto import Orthophoto, OrthophotoProjector
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% what the rules read about a request

WAY_OF_LOOKING_ATTRIBUTE_NAME = "way_of_looking"
"""
The attribute of a request the rules conclude, which the engine predicts by name.
"""


@dataclass(frozen=True)
class RequestedLook:
    """
    One request, read as the plain properties a rule states its conditions over.

    Everything a rule reads is stated here rather than reached for through the request,
    so a rule is a condition over named properties and the reading of the request
    happens once, in :meth:`of`.
    """

    pieces_are_asked_for: bool
    """
    Whether a loose piece is a thing this request can be answered with.
    """

    the_board_is_asked_for: bool
    """
    Whether the board, or one of the holes cut through its lid, is a thing this request
    can be answered with.
    """

    way_of_looking: Optional[WayOfLooking] = None
    """
    How this request is to be answered, which is what the rules conclude.

    Unset on a request put to the rules: the engine predicts this attribute rather than
    reading it, and it is declared here because naming a field is how a conclusion is
    named.
    """

    @classmethod
    def of(cls, request: SceneRequest) -> RequestedLook:
        """
        Read what a look was asked for.

        :param request: What the statement asks a look for.
        """
        return cls(
            pieces_are_asked_for=request.wants(MontessoriShapeDetection),
            the_board_is_asked_for=(
                request.wants(MontessoriBoardDetection)
                or request.wants(ShapeSortingHoleDetection)
            ),
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


# %% what a way of looking is


class WayOfLooking(ABC):
    """
    One way of answering a look at the Montessori scene.

    A way of looking states the requests it can answer, so the rules choose between ways
    by matching a request against what each one says rather than by naming them.
    """

    @abstractmethod
    def capability(self, request: RequestedLook) -> ConditionType:
        """
        The requests this way of looking can answer, as a condition over a request.

        Written as an entity query language condition rather than as a predicate on a
        value, so the same statement both decides one request and becomes the rule that
        concludes this way of looking.

        :param request: The :class:`RequestedLook` variable to state the condition over.
        :return: The condition, which holds exactly for the requests this way answers.
        """

    @abstractmethod
    def take(self, scene: SceneToSearch) -> MontessoriScene:
        """
        Take the look this way of looking was chosen for.

        :param scene: What was asked for, and the frame to answer it from.
        :return: What the look found.
        """


# %% the rules


def state_the_ways_own_condition(
    context: CaseContext, requests: List[AnswerRequest]
) -> Dict[AnswerName, Any]:
    """
    Answer the engine's question about a new rule with the condition the way of looking
    being fitted already states about itself.

    Only conditions are ever asked for, since every request the rules are fitted with
    names the way that answers it.

    :param context: The request being fitted, and the way of looking it is fitted to.
    :param requests: The answers asked for, which this reads nothing from.
    :return: The conditions answer.
    """
    return {
        AnswerName.CONDITIONS: context.target_conclusion.capability(
            context.case_variable
        )
    }


@dataclass
class LookRules:
    """
    The rule tree that says how a look at this scene is answered.

    Its rules are krrood ripple-down rules whose conditions are entity query language
    expressions over what a request states, so a request the rules get wrong is
    corrected by adding a rule rather than by editing the ones already stated, and the
    tree can be read (:meth:`render_tree`) rather than only run.
    """

    find_the_board: WayOfLooking
    """
    Answers a request the board or one of its holes can answer.
    """

    find_the_pieces: WayOfLooking
    """
    Answers a request a loose piece can answer, reporting the board it measured the
    surfaces by along with them.
    """

    rules: EQLSingleClassRDR = field(init=False, repr=False, compare=False)
    """
    The rules themselves, as one tree that outlives the requests it answers.

    Nothing is persisted when a rule is added: a rule concludes the way of looking
    itself rather than a name for one, and the engine writes a model file as Python
    source, which can spell an enum member or a number but not a collaborator. The rules
    are recovered by stating them again from the ways, which is what building this does.
    """

    expert: Expert = field(init=False, repr=False, compare=False)
    """
    Asked for a new rule's condition, which it reads off the way of looking being
    fitted.
    """

    def __post_init__(self) -> None:
        """
        State the rules by fitting the requests each way of looking answers.

        The engine authors its own tree, so a rule is written by putting a known request
        and the way that answers it to it, and each way supplies the condition from its
        own :meth:`~WayOfLooking.capability`.
        """
        self.expert = Expert(
            interface=FunctionInterface(answer_function=state_the_ways_own_condition)
        )
        self.rules = EQLSingleClassRDR(
            RequestedLook,
            WAY_OF_LOOKING_ATTRIBUTE_NAME,
            model_saver=NullModelSaver(),
        )
        answered = self.requests_each_way_answers()
        self.rules.fit(
            cases=[request for request, _ in answered],
            targets=[way for _, way in answered],
            expert=self.expert,
        )

    def requests_each_way_answers(self) -> List[Tuple[RequestedLook, WayOfLooking]]:
        """
        The known kinds of request, each paired with the way of looking that answers it.

        The unnarrowed request is fitted alongside the two narrowed ones, so the rules
        are held to answering it rather than left to happen to.
        """
        return [
            (RequestedLook.of(SceneRequest()), self.find_the_pieces),
            (
                RequestedLook.of(SceneRequest(detection_type=MontessoriShapeDetection)),
                self.find_the_pieces,
            ),
            (
                RequestedLook.of(SceneRequest(detection_type=MontessoriBoardDetection)),
                self.find_the_board,
            ),
        ]

    def way_of_looking_for(self, request: RequestedLook) -> WayOfLooking:
        """
        How one request is to be answered.

        :param request: What the look was asked for.
        :raises NoWayOfLookingAnswersTheRequest: If no rule reaches this request.
        """
        concluded = self.rules.classify(request)
        if concluded is ...:
            raise NoWayOfLookingAnswersTheRequest(str(request))
        return concluded

    def add_rule(self, request: RequestedLook, way: WayOfLooking) -> None:
        """
        State a kind of request the rules do not yet cover.

        The rule joins the tree already in use, so such a request is answered by *way*
        from the next call onwards without any of the rules already stated being
        rewritten. That is what a tree of rules is for, and it is the path an expert
        correcting an answer takes.

        :param request: The kind of request that was not covered.
        :param way: The way of looking that answers it, which supplies the rule's
            condition from its own capability.
        """
        self.rules.fit_case(request, way, self.expert)

    def render_tree(self, request: RequestedLook) -> str:
        """
        The rules as a tree, with the rule that answers one request marked out.

        :param request: The request to read the tree for.
        """
        return self.rules.render_tree(request, use_color=False)
