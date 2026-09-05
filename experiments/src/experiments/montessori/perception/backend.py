"""
Answer an :mod:`entity query language <krrood.entity_query_language>` statement about
the Montessori scene by looking at it.

Perception is a backend beside the native and SQLAlchemy ones, so asking and looking are
the same act::

    statement = a(DetectedMontessoriShape)(pose=...)
    statement = statement.where(SupportedBy(statement.variable, board_lid))
    [seen] = statement.evaluate(backend=MontessoriPerceptionBackend(source=node))
    reach_for = seen.pose

Everything about how a statement is read, narrowed and checked belongs to
:class:`~krrood.entity_query_language.backends.PerceptionBackend` and is the same for
any sensor. What is here is only what is particular to this scene: that a look is taken
by the Montessori pipeline, and which relations its search can narrow itself by.

Four can. *Supported by* names a surface, and a surface is a stretch of a plane the
world already describes, so a look narrowed by it rectifies that stretch instead of the
whole table. Every relation that says where a thing may be -- inside a region, right of
one thing, between two, near a place -- answers the stretch it allows, so the picture is
cut to it before anything is detected. A colour says which pieces are worth fitting at
all, so a look asked for one marks that colour alone. And a turn says which way round to
lay a piece over the edges. What none of them do is decide the answer: each is read
again off what came back.

What a look found stands as a body in a copy of the world it was taken in, so a relation
is evaluated there like any relation of the world -- the colour the body is drawn in,
the way it is turned, whether it touches something -- and what the statement rejects
leaves that world again. Only what the look establishes *differently* from a body is
read off the sighting itself: which surface it searched, and where it reported the thing
standing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import (
    Any,
    ClassVar,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

from experiments.montessori.perception.detections import (
    DetectedMontessoriShape,
    MontessoriDetection,
    MontessoriScene,
)
from experiments.montessori.perception.exceptions import (
    LookHasNoReferenceFrame,
    SightingHasNoBody,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import MontessoriSceneSource
from krrood.entity_query_language.backends import (
    LookRequest,
    PerceptionBackend,
    relation_asserted_about,
)
from krrood.entity_query_language.predicate import Relation
from krrood.entity_query_language.query.match import Match
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)
from semantic_digital_twin.reasoning.predicates import (
    Colored,
    PlacementRelation,
    SupportedBy,
    Turned,
)

# %% what a look establishes about a sighting for itself

Read = TypeVar("Read", bound=Relation)
"""
The kind of relation a reading answers.
"""


@dataclass
class SightingReading(Generic[Read], SubClassSafeGeneric, ABC):
    """
    How a look reads one kind of relation off a sighting, without a body to ask.

    A look establishes some things about what it found in the act of finding it: which
    surface it searched and where it reported the thing standing. A relation of those
    kinds is answered from the sighting the way the look established it, which is what
    lets the look narrow itself by the relation and still check it afterwards. Each
    reading binds the kind of relation it answers as its type parameter.
    """

    @classmethod
    def relation_type(cls) -> Type[Read]:
        """
        The kind of relation this reading answers, by the class that means it.
        """
        return cls.get_generic_type_parameters()[0]

    @classmethod
    @abstractmethod
    def holds_for(cls, instance: MontessoriDetection, stated: Match[Relation]) -> bool:
        """
        Whether a sighting satisfies one relation of this kind.

        :param instance: One detection the look reported.
        :param stated: The relation, as stated about the thing sought.
        """


@dataclass
class RestsOnTheSurfaceNamed(SightingReading[SupportedBy]):
    """
    A detection says what it rests on by the name the world knows that surface by, so
    what the statement names is read back the same way.
    """

    @classmethod
    def holds_for(cls, instance: MontessoriDetection, stated: Match[Relation]) -> bool:
        named = stated.kwargs[stated.type.object_name()]
        return instance.supporting_surface == named.name


@dataclass
class StandsWhereAllowed(SightingReading[PlacementRelation]):
    """
    Where a detection stands is the position the look reported it at, which is what
    a placement is read against rather than the volume of the body standing for it.
    """

    @classmethod
    def holds_for(cls, instance: MontessoriDetection, stated: Match[Relation]) -> bool:
        return stated.construct_instance().allows(instance.pose.to_position())


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

    seen: Optional[MontessoriScene] = field(init=False, default=None)
    """
    What the last look found, which is what says where the things found stand.
    """

    readings: ClassVar[Tuple[Type[SightingReading], ...]] = (
        RestsOnTheSurfaceNamed,
        StandsWhereAllowed,
    )
    """
    What a look here establishes about a sighting for itself, and so reads off the
    sighting rather than asking of the body standing for it.
    """

    narrowing_relations: ClassVar[Tuple[Type[Relation], ...]] = (
        SupportedBy,
        PlacementRelation,
        Colored,
        Turned,
    )
    """
    What a look here can be narrowed by: which surface to search, which part of it to
    read, which colour to look for, and which way round to lay a piece.
    """

    def look(
        self, request: LookRequest[MontessoriDetection]
    ) -> Iterable[MontessoriDetection]:
        """
        Take a look at the scene.

        :param request: What the statement asks a look for.
        :return: Everything the look found.
        """
        self.seen = self.source.scene(self.scene_request(request))
        return self.seen.detections

    def discard(self, instances: List[MontessoriDetection]) -> None:
        """
        Take what the statement rejected out of the world the look stood it in, so what
        that world holds is the answer and nothing else.

        :param instances: Everything the look reported that the statement rejected.
        """
        if self.seen is None or self.seen.imagined is None:
            return
        for instance in instances:
            if isinstance(instance, DetectedMontessoriShape):
                self.seen.imagined.remove(instance.role_taker)

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
        :raises LookHasNoReferenceFrame: If the statement says where the thing lies but
            the source reports its detections in no frame, which leaves the relation
            nothing to be read against.
        """
        placements = self.placements_asked_about(request)
        if placements and self.source.reference_frame is None:
            raise LookHasNoReferenceFrame(type(placements[0]).__name__)
        narrowed_by = request.stated_relations_of(self.narrowing_relations)
        return not self.contradicted_by(instance, narrowed_by)

    @classmethod
    def contradicted_by(
        cls, instance: MontessoriDetection, stated: Sequence[Match[Relation]]
    ) -> Tuple[Relation, ...]:
        """
        Every stated relation a detection does not satisfy, each asserted about what the
        look found so it can be read as the claim that failed.

        A relation this look establishes for itself is read off the sighting the way
        the look established it; any other is asked of the body the look stood in its
        world for the sighting -- the colour it is drawn in, the way it is turned, what
        it touches -- which is what lets whatever relation a statement can state be
        checked here.

        :param instance: One detection the look reported.
        :param stated: The relations, each as stated about the thing sought.
        :raises SightingHasNoBody: If a relation the look cannot establish itself is
            asked of a sighting that no body stands for.
        :return: The violated relations, in the order they were stated.
        """
        return tuple(
            relation_asserted_about(
                stated_relation, cls._subject_of(instance, stated_relation)
            )
            for stated_relation in stated
            if not cls._holds_for(instance, stated_relation)
        )

    @classmethod
    def _holds_for(cls, instance: MontessoriDetection, stated: Match[Relation]) -> bool:
        """
        :param instance: One detection the look reported.
        :param stated: One relation, as stated about the thing sought.
        """
        for reading in cls.readings:
            if issubclass(stated.type, reading.relation_type()):
                return reading.holds_for(instance, stated)
        return bool(relation_asserted_about(stated, cls._body_of(instance, stated))())

    @classmethod
    def _subject_of(cls, instance: MontessoriDetection, stated: Match[Relation]) -> Any:
        """
        :param instance: One detection the look reported.
        :param stated: One relation, as stated about the thing sought.
        :return: What a violated relation is reported about: the body standing for the
            sighting where there is one, and the sighting itself otherwise.
        """
        if isinstance(instance, DetectedMontessoriShape):
            return cls._body_of(instance, stated)
        return instance

    @staticmethod
    def _body_of(instance: MontessoriDetection, stated: Match[Relation]) -> Any:
        """
        :param instance: One detection the look reported.
        :param stated: The relation about to be asked of it.
        :raises SightingHasNoBody: If no body stands in a world for the sighting.
        :return: The body the look stood in its world for the sighting.
        """
        if not isinstance(instance, DetectedMontessoriShape):
            raise SightingHasNoBody(stated.type.__name__, instance.label)
        return instance.role_taker.root

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
            placement.construct_instance()
            for placement in request.stated_relations_of(PlacementRelation)
        )

    @classmethod
    def scene_request(cls, request: LookRequest[MontessoriDetection]) -> SceneRequest:
        """
        Read what a statement asks for as something a look at this scene can act on.

        :param request: What the statement asks a look for.
        :return: The kind of detection to run detectors for, the surface to search, the
            placements to stay within, the colour to look for, and the turn to lay a
            piece at.
        """
        return SceneRequest(
            detection_type=request.type_,
            supporting_surface=cls.supporting_surface_asked_about(request),
            placements=cls.placements_asked_about(request),
            color=request.related_by(Colored),
            turn=cls.turn_asked_about(request),
        )

    @classmethod
    def turn_asked_about(
        cls, request: LookRequest[MontessoriDetection]
    ) -> Optional[Turned]:
        """
        Which way a statement says the thing it is looking for is turned.

        :param request: What the statement asks a look for.
        :return: The relation that says it, with nothing standing in the place of that
            thing, or ``None`` when the statement says nothing about its turn.
        """
        stated = request.stated_relations_of(Turned)
        if not stated:
            return None
        return stated[0].construct_instance()

    @classmethod
    def supporting_surface_asked_about(
        cls, request: LookRequest[MontessoriDetection]
    ) -> Optional[KinematicStructureEntity]:
        """
        The surface a statement says the thing it is looking for rests on, as the world
        holds it.

        :param request: What the statement asks a look for.
        :return: The surface asked about, or ``None`` when the statement asks about
            none.
        """
        return request.related_by(SupportedBy)
