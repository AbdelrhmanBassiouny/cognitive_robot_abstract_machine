"""
Which detector answers a look, decided from what the robot knows.

A look at a surface can be taken in more than one way, and which way works depends on
things the digital twin already states: how the surface takes light, and whether the
piece being looked for wears a colour that separates it from that surface. So the choice
is made by a rule tree over the look itself -- the surface and the piece as the world
states them -- rather than by a branch written into the pipeline, and it gets better as
the world gains annotations rather than as somebody edits the pipeline.

The tree is krrood's
:class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`, built from the
underspecified statement *a look whose detector is to be worked out*, so what is
described and what is left open are read off that statement rather than named again
here.

The choice is made in two parts, which answer different questions:

- **What a detector can answer at all** is the detector's own statement, as an entity
  query language condition over the look (see
  :meth:`~krrood.entity_query_language.backends.PerceptionDetector.capability`). A
  detector is never chosen for a look it declared it cannot answer.
- **Which of the ones that can should**, which is what the rule tree decides.

Neither part subsumes the other. Both detectors here can answer a look at a piece on a
matte surface, so a capability alone leaves the question open; and a tree that named
detectors without asking them would have to be rewritten to gain one.

The tree is a live one. It is stated when the rules are built and grows through
:meth:`DetectorRules.add_rule`, so a situation nobody foresaw is given a rule while the
rules are in use rather than written into the code that reads them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

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
from typing_extensions import Any, Dict, List, Optional, Sequence, Tuple

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import MontessoriShapeDetection
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.exceptions import NoDetectorAnswersTheLook
from experiments.montessori.perception.orthophoto import Orthophoto, WorkspaceRegion
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from experiments.montessori.pieces import (
    HUE_RANGE,
    HUE_TOLERANCE,
    KNOWN_PIECES,
    KnownPiece,
    color_of_hue,
    hue_distance,
    hue_of,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.geometry import Color, SurfaceFinish
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% what the rules read


@dataclass(frozen=True, eq=False)
class TargetOnSurface(Look):
    """
    One piece, the surface it is being looked for on, and what the world says about the
    two together.

    A rule reads the two as they are rather than a copy of the properties it happens to
    want, so what a condition asks about a surface or a piece is what the world states
    about it, and there is no second description to fall out of step with either.

    ..note:: Compared by identity: a piece holds its outline as an array, which does not
        compare as a value, and two looks at one scene are not the same look.
    """

    surface: WorkspaceSurface
    """
    The surface being searched, as it was read from the world.
    """

    target: KnownPiece
    """
    The piece being looked for.
    """

    detector: Optional[PieceDetector] = None
    """
    The detector that answers this look, left open for the rules to work out.

    A look stating nothing here is one whose answer has still to be planned, which is
    what the rules that choose a detector are asked about; one carrying a detector has
    been planned already.
    """

    @property
    def target_outline_is_known(self) -> bool:
        """
        Whether the shape of the piece being looked for is modelled, so an outline of it
        can be laid over what the camera saw.
        """
        return self.target.outline is not None

    @property
    def target_separates_from_the_surface_by_color(self) -> bool:
        """
        Whether the piece wears a colour far enough from the surface's own to be cut out
        of it by colour alone.

        False where the world states no colour for the surface: an unstated colour is
        not a contrasting one, and treating it as one is how a piece gets silently
        merged into the surface it rests on.
        """
        return (
            self.surface.color is not None
            and hue_distance(hue_of(self.surface.color), self.target.hue)
            > HUE_TOLERANCE
        )


# %% what a detector says it can answer


class PieceDetector(PerceptionDetector[TargetOnSurface], ABC):
    """
    Something that finds the loose pieces resting on one surface.

    The looks it can answer are the ones its
    :meth:`~krrood.entity_query_language.backends.PerceptionDetector.capability` states
    over a :class:`TargetOnSurface`, so the choice between detectors is made by matching
    a look against what each one says rather than by a caller knowing which is which.
    """

    piece_height: float
    """
    Roughly how tall a loose piece stands, in metres, which sets the plane a piece's top
    is rectified onto and is reported as its height wherever the depth image cannot
    resolve one.
    """

    @abstractmethod
    def detect(
        self,
        orthophoto: Orthophoto,
        top_orthophoto: Orthophoto,
        edges: EdgeDistances,
        frame: RgbdFrame,
        reference_frame: Optional[KinematicStructureEntity],
        search: SurfaceSearch,
        candidates: Sequence[KnownPiece] = KNOWN_PIECES,
    ) -> List[MontessoriShapeDetection]:
        """
        Find the pieces this detector was chosen for, on the surface it was chosen for.

        :param orthophoto: The rectified view of the surface's own plane.
        :param top_orthophoto: The rectified view of the plane a piece's top stands on.
        :param edges: How far each point of that top view lies from an edge the camera
            saw, which is what a piece's own outline is scored against.
        :param frame: The camera data, for measuring how tall each piece stands.
        :param reference_frame: Frame the resulting poses are expressed in.
        :param search: The surface being searched, which settles what rests on it.
        :param candidates: The pieces this detector was chosen to look for.
        :return: One detection per recognised piece.
        """


# %% choosing between them


@dataclass
class DetectorRules:
    """
    The rule tree that says which detector answers a look at this scene.

    Its rules are krrood ripple-down rules whose conditions are entity query language
    expressions over the look itself, so a look the rules get wrong is corrected by
    adding a rule rather than by editing the ones already stated, and the tree can be
    read (:meth:`render_tree`) rather than only run.
    """

    edge_fit: PieceDetector
    """
    Fits the outlines of the known pieces to the edges the camera saw.

    The general answer: it needs nothing of the surface, only that the piece's shape is
    modelled.
    """

    color_blob: PieceDetector
    """
    Cuts the piece out of the surface by colour and scores that one placement.

    Cheaper than searching for a placement, and that is the whole of why it is
    preferred: the edge fit works on a matte lid too, measured at 0.93 agreement on a
    cube resting on the board.
    """

    rules: EQLSingleClassRDR = field(init=False, repr=False, compare=False)
    """
    The rules themselves, as one tree that outlives the looks it decides.

    Nothing is persisted when a rule is added: a rule concludes the detector itself
    rather than a name for one, and the engine writes a model file as Python source,
    which can spell an enum member or a number but not a collaborator. The rules are
    recovered by stating them again from the detectors, which is what building this
    does.
    """

    expert: Expert = field(init=False, repr=False, compare=False)
    """
    Asked for a new rule's condition, which it reads off
    :meth:`state_the_condition_this_rule_needs`.
    """

    def __post_init__(self) -> None:
        """
        State the rules by fitting the looks each detector answers.

        The engine authors its own tree, so a rule is written by putting a known kind of
        look and the detector that answers it to it.
        """
        self.expert = Expert(
            interface=FunctionInterface(
                answer_function=self.state_the_condition_this_rule_needs
            )
        )
        self.rules = EQLSingleClassRDR.from_underspecified(
            a(TargetOnSurface)(detector=...), model_saver=NullModelSaver()
        )
        answered = self.looks_each_detector_answers()
        self.rules.fit(
            cases=[look for look, _ in answered],
            targets=[detector for _, detector in answered],
            expert=self.expert,
        )

    def state_the_condition_this_rule_needs(
        self, context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        """
        Answer the engine's question about a new rule with what the detector says it can
        answer, narrowed by the situation these rules choose it in.

        A capability alone does not tell the detectors apart -- both answer a look at a
        piece that colour separates from the surface it rests on -- so the condition a
        rule needs is the capability *and* whatever these rules know about when that
        detector is worth running.

        :param context: The look being fitted, and the detector it is fitted to.
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
        self, detector: PieceDetector, look: TargetOnSurface, example: TargetOnSurface
    ) -> Optional[ConditionType]:
        """
        What these rules know about when a detector is worth running, over and above
        what it says it can answer.

        How the surface takes light is what these rules decide by: the edge fit is the
        general answer and needs no situation of its own, and every other detector is
        worth its cost on the finishes it was stated for -- the colour blob on a matte
        surface, measured at 89 ms against 126 ms on the same work -- which is read off
        the look the rule is being stated from rather than named again here.

        :param detector: The detector a rule is being stated for.
        :param look: The variable the condition is stated over.
        :param example: The look the rule is being stated from.
        :return: The situation, or ``None`` where the rules hold none.
        """
        if detector is self.edge_fit:
            return None
        return look.surface.finish == example.surface.finish

    def looks_each_detector_answers(
        self,
    ) -> List[Tuple[TargetOnSurface, PieceDetector]]:
        """
        The known kinds of look, each paired with the detector that answers it.

        A look at a surface nothing is stated about is fitted alongside the matte one,
        so the rules are held to answering it by fitting edges rather than left to
        happen to.
        """
        target = KNOWN_PIECES[0]
        return [
            (
                TargetOnSurface(self.a_surface_of(None, None), target),
                self.edge_fit,
            ),
            (
                TargetOnSurface(
                    self.a_surface_of(
                        SurfaceFinish.MATTE, self.a_color_separating_from(target)
                    ),
                    target,
                ),
                self.color_blob,
            ),
        ]

    @staticmethod
    def a_surface_of(
        finish: Optional[SurfaceFinish], color: Optional[Color]
    ) -> WorkspaceSurface:
        """
        A surface of a kind the rules are stated from, stating only what a rule reads of
        one.

        :param finish: How it takes light, or ``None`` where nothing is stated.
        :param color: The colour the world states for it, or ``None`` where it states
            none.
        """
        return WorkspaceSurface(
            name=PrefixedName("a_surface_the_rules_are_stated_from", "detector_choice"),
            region=WorkspaceRegion(
                minimum_x=0.0, maximum_x=1.0, minimum_y=0.0, maximum_y=1.0
            ),
            height=0.0,
            finish=finish,
            color=color,
        )

    @staticmethod
    def a_color_separating_from(target: KnownPiece) -> Color:
        """
        A colour far enough from a piece's own for colour to cut the piece out of a
        surface wearing it, which is what the colour blob states it needs.

        :param target: The piece the colour has to separate from.
        """
        return color_of_hue((target.hue + HUE_RANGE // 2) % HUE_RANGE)

    def add_rule(self, look: TargetOnSurface, detector: PieceDetector) -> None:
        """
        State a kind of look the rules do not yet cover.

        The rule joins the tree already in use, so such a look is answered by *detector*
        from the next call onwards without any of the rules already stated being
        rewritten. That is what a tree of rules is for, and it is the path an expert
        correcting a choice takes.

        :param look: The kind of look that was not covered.
        :param detector: The detector that answers it.
        """
        self.rules.fit_case(look, detector, self.expert)

    def detectors_for(
        self, surface: WorkspaceSurface, targets: Sequence[KnownPiece]
    ) -> List[Tuple[PieceDetector, Tuple[KnownPiece, ...]]]:
        """
        Which detector answers the look for each piece on one surface, with the pieces
        grouped under the detector chosen for them.

        Grouped rather than answered one piece at a time because a detector reads the
        picture once for every colour it was asked about, so running it once per group
        is the same work as running it once per piece would only ever be more of.

        :param surface: The surface being searched, as it was read from the world.
        :param targets: The pieces that may be standing on it.
        :raises NoDetectorAnswersTheLook: If no detector answers one of the looks.
        :return: Each chosen detector and the pieces it was chosen for, in the order the
            pieces were given.
        """
        grouped: Dict[int, Tuple[PieceDetector, List[KnownPiece]]] = {}
        for target in targets:
            detector = self.detector_for(TargetOnSurface(surface, target))
            grouped.setdefault(id(detector), (detector, []))[1].append(target)
        return [(detector, tuple(pieces)) for detector, pieces in grouped.values()]

    def detector_for(self, look: TargetOnSurface) -> PieceDetector:
        """
        The detector that answers one look.

        :param look: The piece being looked for and the surface it is looked for on.
        :raises NoDetectorAnswersTheLook: If no rule reaches this look.
        """
        concluded = self.rules.classify(look)
        if concluded is ...:
            raise NoDetectorAnswersTheLook(str(look))
        return concluded

    def render_tree(self, look: TargetOnSurface) -> str:
        """
        The rules as a tree, with the rule that answers one look marked out.

        :param look: The look to read the tree for.
        """
        return self.rules.render_tree(look, use_color=False)
