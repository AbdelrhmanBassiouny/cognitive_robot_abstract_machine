"""
Answer an :mod:`entity query language <krrood.entity_query_language>` statement about
the Montessori scene by looking at it.

Perception is a backend beside the native and SQLAlchemy ones, so asking and looking are
the same act::

    statement = an(DetectedMontessoriShape)(pose=...)
    statement = statement.where(SupportedBy(statement.variable, board_lid))
    [seen] = statement.evaluate(backend=MontessoriPerceptionBackend(source=node))
    reach_for = seen.pose

Everything about how a statement is read, narrowed and checked belongs to
:class:`~krrood.entity_query_language.backends.PerceptionBackend` and is the same for
any sensor. What is here is only what is particular to this scene: that a look is taken
by the Montessori pipeline, and which relations its search can narrow itself by.

Three can. *Supported by* names a surface, and a surface is a stretch of a plane the
world already describes, so a look narrowed by it rectifies that stretch instead of the
whole table. Every relation that says where a thing may be -- inside a region, right of
one thing, between two, near a place -- answers the stretch it allows, so the picture is
cut to it before anything is detected. And a colour says which pieces are worth fitting
at all, so a look asked for one marks that colour alone. What none of them do is decide
the answer: each is checked again over what came back.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import ClassVar, Iterable, Optional, Tuple, Type

from experiments.montessori.perception.detections import MontessoriDetection
from experiments.montessori.perception.exceptions import LookHasNoReferenceFrame
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import MontessoriSceneSource
from krrood.entity_query_language.backends import LookRequest, PerceptionBackend
from krrood.entity_query_language.predicate import Relation
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import (
    Colored,
    PlacementRelation,
    SupportedBy,
)

# %% the backend


@dataclass
class MontessoriPerceptionBackend(PerceptionBackend):
    """
    Answers a statement about the Montessori scene by looking at it.
    """

    source: MontessoriSceneSource
    """
    Where a look at the scene comes from.
    """

    narrowing_relations: ClassVar[Tuple[Type[Relation], ...]] = (
        SupportedBy,
        PlacementRelation,
        Colored,
    )
    """
    What a look here can be narrowed by: which surface to search, which part of it to
    read, and which colour to look for.
    """

    def look(
        self, request: LookRequest[MontessoriDetection]
    ) -> Iterable[MontessoriDetection]:
        """
        Take a look at the scene.

        :param request: What the statement asks a look for.
        :return: Everything the look found.
        """
        return self.source.scene(self.scene_request(request)).detections

    def relations_hold(
        self, instance: MontessoriDetection, request: LookRequest[MontessoriDetection]
    ) -> bool:
        """
        Whether a detection stands where the statement said the thing sought stands.

        A look already taken cannot be narrowed, so what the search was asked for is
        checked again here over whatever came back -- which is what makes the narrowing
        an economy rather than the thing the answer's correctness rests on.

        :param instance: One detection the look reported.
        :param request: What the statement asks a look for.
        """
        return (
            self._rests_on_the_surface_asked_about(instance, request)
            and self._stands_where_the_statement_says(instance, request)
            and self._wears_the_color_asked_about(instance, request)
        )

    def _rests_on_the_surface_asked_about(
        self, instance: MontessoriDetection, request: LookRequest[MontessoriDetection]
    ) -> bool:
        """
        :param instance: One detection the look reported.
        :param request: What the statement asks a look for.
        """
        supporting_surface = self.supporting_surface_asked_about(request)
        return (
            supporting_surface is None
            or instance.supporting_surface == supporting_surface
        )

    def _stands_where_the_statement_says(
        self, instance: MontessoriDetection, request: LookRequest[MontessoriDetection]
    ) -> bool:
        """
        Whether a detection was seen where every relation the statement states allows.

        A detection is a sighting rather than a body, so where it stands is the position
        it was reported at rather than a volume a containment can be measured against.

        :param instance: One detection the look reported.
        :param request: What the statement asks a look for.
        :raises LookHasNoReferenceFrame: If the statement says where the thing lies but
            the source reports its detections in no frame, which leaves the relation
            nothing to be read against.
        """
        placements = self.placements_asked_about(request)
        if not placements:
            return True
        if self.source.reference_frame is None:
            raise LookHasNoReferenceFrame(type(placements[0]).__name__)
        return all(
            placement.allows(instance.pose.to_position()) for placement in placements
        )

    def _wears_the_color_asked_about(
        self, instance: MontessoriDetection, request: LookRequest[MontessoriDetection]
    ) -> bool:
        """
        :param instance: One detection the look reported.
        :param request: What the statement asks a look for.
        """
        color = request.related_by(Colored)
        return color is None or instance.color == color

    @classmethod
    def placements_asked_about(
        cls, request: LookRequest[MontessoriDetection]
    ) -> Tuple[PlacementRelation, ...]:
        """
        Everything the statement says about where the thing it is looking for lies, each
        as the relation that says it with nothing standing in the place of that thing.

        :param request: What the statement asks a look for.
        :return: One relation per placement the statement states, empty where it states
            none.
        """
        return tuple(
            placement.constraint()
            for placement in request.stated_relations_of(PlacementRelation)
        )

    @classmethod
    def scene_request(cls, request: LookRequest[MontessoriDetection]) -> SceneRequest:
        """
        Read what a statement asks for as something a look at this scene can act on.

        :param request: What the statement asks a look for.
        :return: The kind of detection to run detectors for, the surface to search, the
            placements to stay within, and the colour to look for.
        """
        return SceneRequest(
            detection_type=request.type_,
            supporting_surface=cls.supporting_surface_asked_about(request),
            placements=cls.placements_asked_about(request),
            color=request.related_by(Colored),
        )

    @classmethod
    def supporting_surface_asked_about(
        cls, request: LookRequest[MontessoriDetection]
    ) -> Optional[PrefixedName]:
        """
        The surface a statement says the thing it is looking for rests on.

        A detection says what it rests on by the name the world knows that surface by,
        so what the statement names is read back the same way.

        :param request: What the statement asks a look for.
        :return: The name of the surface asked about, or ``None`` when the statement
            asks about none.
        """
        supporter = request.related_by(SupportedBy)
        if supporter is None:
            return None
        return supporter.name
