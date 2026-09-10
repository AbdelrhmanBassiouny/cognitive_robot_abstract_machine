"""
Which detector answers a look, decided from what the robot knows.

A look at a surface can be taken in more than one way, and which way works depends on
things the digital twin already states: how the surface takes light, and whether the
piece being looked for wears a colour that separates it from that surface. So the choice
is made by a rule tree over those properties rather than by a branch written into the
pipeline, and it gets better as the world gains annotations rather than as somebody
edits the pipeline.

The choice is made in two parts, which answer different questions:

- **What a detector can answer at all** is the detector's own statement, as an entity
  query language condition over the look (see :meth:`PieceDetector.capability`). A
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
from functools import cached_property

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
from typing_extensions import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import MontessoriShapeDetection
from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.exceptions import NoDetectorAnswersTheLook
from experiments.montessori.perception.orthophoto import Orthophoto
from experiments.montessori.perception.surfaces import SurfaceSearch, WorkspaceSurface
from experiments.montessori.pieces import (
    HUE_TOLERANCE,
    KNOWN_PIECES,
    KnownPiece,
    hue_distance,
    hue_of,
)
from semantic_digital_twin.world_description.geometry import SurfaceFinish
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.query.query import Query

# %% what the rules read


@dataclass(frozen=True)
class TargetOnSurface:
    """
    One piece, the surface it is being looked for on, and what the world says about the
    two together.

    Everything a rule reads is stated here rather than reached for through the world, so
    a rule is a condition over plain properties and the reading of the world happens
    once in :meth:`of`.
    """

    surface_finish: Optional[SurfaceFinish]
    """
    How the surface takes light, or ``None`` where the world states no finish.
    """

    target_outline_is_known: bool
    """
    Whether the shape of the piece being looked for is modelled, so an outline of it can
    be laid over what the camera saw.
    """

    target_separates_from_the_surface_by_color: bool
    """
    Whether the piece wears a colour far enough from the surface's own to be cut out of
    it by colour alone.

    False where the world states no colour for the surface: an unstated colour is not a
    contrasting one, and treating it as one is how a piece gets silently merged into the
    surface it rests on.
    """

    @classmethod
    def of(cls, surface: WorkspaceSurface, target: KnownPiece) -> TargetOnSurface:
        """
        What the world says about looking for one piece on one surface.

        :param surface: The surface being searched, as it was read from the world.
        :param target: The piece being looked for.
        """
        return cls(
            surface_finish=surface.finish,
            target_outline_is_known=target.outline is not None,
            target_separates_from_the_surface_by_color=(
                surface.color is not None
                and hue_distance(hue_of(surface.color), target.hue) > HUE_TOLERANCE
            ),
        )


# %% what a detector says it can answer


class PieceDetector(ABC):
    """
    Something that finds the loose pieces resting on one surface.

    A detector states the looks it can answer, so the choice between detectors is made
    by matching a look against what each one says rather than by a caller knowing which
    is which.
    """

    @abstractmethod
    def capability(self, look: TargetOnSurface) -> ConditionType:
        """
        The looks this detector can answer, as a condition over a look.

        Written as an entity query language condition rather than as a predicate on a
        value, so the same statement both decides one look and forms part of the rule
        tree that chooses between detectors.

        :param look: The :class:`TargetOnSurface` variable to state the condition over.
        :return: The condition, which holds exactly for the looks this detector answers.
        """

    @cached_property
    def stated_look(self) -> TargetOnSurface:
        """
        The variable this detector states its own capability over.

        The statement is made once and one look at a time is bound to this to ask it.
        """
        return variable(TargetOnSurface, domain=[])

    @cached_property
    def answerable_looks(self) -> Query:
        """
        The looks this detector can answer, stated once over :attr:`stated_look`.
        """
        return an(entity(self.stated_look).where(self.capability(self.stated_look)))

    def answers(self, look: TargetOnSurface) -> bool:
        """
        Whether this detector declares it can answer one look.

        :param look: The look to put to it.
        """
        self.stated_look._update_domain_([look])
        return bool(self.answerable_looks.tolist())

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

    Its rules are krrood ripple-down rules, so a case that a rule gets wrong is
    corrected by adding an exception under it rather than by editing the rule, and every
    condition is an entity query language expression over what the world states.

    The tree is stated once, when the rules are built, and each look is decided by
    binding it to :attr:`stated_look` and evaluating that one tree. It outlives the
    looks it decides, so it can be read, and a situation it gets wrong can be given a
    rule through :meth:`add_rule` while it is in use.
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

    stated_look: TargetOnSurface = field(init=False, repr=False, compare=False)
    """
    The variable every rule states its conditions over, which one look at a time is
    bound to.
    """

    chosen_detector: PieceDetector = field(init=False, repr=False, compare=False)
    """
    The variable the rules conclude, which a look's answer is read from.
    """

    rule_tree: Query = field(init=False, repr=False, compare=False)
    """
    The rules themselves, as one live tree that outlives the looks it decides.
    """

    latest_rule: SymbolicExpression = field(init=False, repr=False, compare=False)
    """
    The most recently stated exception, which the next one is attached beside so the
    exceptions to the base rule form one chain and a look reaches at most one of them.
    """

    def __post_init__(self) -> None:
        """
        State the rules, once, over the variables the looks are bound to.
        """
        self.stated_look = variable(TargetOnSurface, domain=[])
        self.chosen_detector = deduced_variable(PieceDetector)
        self.rule_tree = entity(self.chosen_detector).where(
            self.edge_fit.capability(self.stated_look)
        )
        with self.rule_tree:
            add(self.chosen_detector, self.edge_fit)
            self.latest_rule = refinement(
                and_(
                    self.stated_look.surface_finish == SurfaceFinish.MATTE,
                    self.color_blob.capability(self.stated_look),
                )
            )
            with self.latest_rule:
                add(self.chosen_detector, self.color_blob)

    def add_rule(self, condition: ConditionType, detector: PieceDetector) -> None:
        """
        State a situation the rules do not yet cover.

        The rule joins the tree already in use, so a look the rules got wrong is
        answered by *detector* from the next call onwards without any of them being
        rewritten. That is what a tree of rules is for, and it is the path an expert
        correcting a choice takes.

        :param condition: What holds of the look, stated over :attr:`stated_look`.
        :param detector: The detector that answers such a look.
        """
        self.latest_rule = Alternative.insert_at(self.latest_rule, condition)
        with self.latest_rule:
            add(self.chosen_detector, detector)

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
            detector = self.detector_for(TargetOnSurface.of(surface, target))
            grouped.setdefault(id(detector), (detector, []))[1].append(target)
        return [(detector, tuple(pieces)) for detector, pieces in grouped.values()]

    def detector_for(self, look: TargetOnSurface) -> PieceDetector:
        """
        The detector that answers one look.

        :param look: The piece being looked for and the surface it is looked for on.
        :raises NoDetectorAnswersTheLook: If no detector declares it can answer.
        """
        self.stated_look._update_domain_([look])
        answered = self.rule_tree.tolist()
        if not answered:
            raise NoDetectorAnswersTheLook(str(look))
        [detector] = answered
        return detector
