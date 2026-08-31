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
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from krrood.entity_query_language.factories import (
    add,
    an,
    and_,
    deduced_variable,
    entity,
    refinement,
    variable,
)
from typing_extensions import Any, Dict, List, Optional, Sequence, Tuple

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

    @classmethod
    @abstractmethod
    def capability(cls, look: Any) -> Any:
        """
        The looks this detector can answer, as a condition over a look.

        Written as an entity query language condition rather than as a predicate on a
        value, so the same statement both decides one look and forms part of the rule
        tree that chooses between detectors.

        :param look: The :class:`TargetOnSurface` variable to state the condition over.
        :return: The condition, which holds exactly for the looks this detector answers.
        """

    @classmethod
    def answers(cls, look: TargetOnSurface) -> bool:
        """
        Whether this detector declares it can answer one look.

        :param look: The look to put to it.
        """
        stated = variable(TargetOnSurface, domain=[look])
        return bool(an(entity(stated).where(cls.capability(stated))).tolist())

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
        stated = variable(TargetOnSurface, domain=[look])
        chosen = deduced_variable(PieceDetector)
        rules = entity(chosen).where(type(self.edge_fit).capability(stated))
        with rules:
            add(chosen, self.edge_fit)
            with refinement(
                and_(
                    stated.surface_finish == SurfaceFinish.MATTE,
                    type(self.color_blob).capability(stated),
                )
            ):
                add(chosen, self.color_blob)
        answered = rules.tolist()
        if not answered:
            raise NoDetectorAnswersTheLook(str(look))
        [detector] = answered
        return detector
