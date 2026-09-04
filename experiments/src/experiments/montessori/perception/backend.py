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
again off what came back, the way the look itself established it.

A relation no search covers is answered rather than refused: what a look found stands as
a body in a copy of the world it was taken in, so the relation is evaluated there, and
what it rejects leaves that world again.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import (
    Any,
    ClassVar,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
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
    StatedRelation,
)
from krrood.entity_query_language.predicate import Relation
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


class SightingReading(ABC):
    """
    How a look reads one kind of relation off a sighting, without a body to ask.

    A look establishes some things about what it found in the act of finding it: which
    surface it searched, where it stands, what colour it marked, which way it laid the
    outline. A relation of those kinds is answered from the sighting the way the look
    established it, which is what lets the look narrow itself by the relation and still
    check it afterwards.
    """

    relation_type: ClassVar[Type[Relation]]
    """
    The kind of relation this reading answers, by the class that means it.
    """

    @classmethod
    @abstractmethod
    def holds_of(cls, instance: MontessoriDetection, stated: StatedRelation) -> bool:
        """
        Whether a sighting satisfies one relation of this kind.

        :param instance: One detection the look reported.
        :param stated: The relation, as stated about the thing sought.
        """


class RestsOnTheSurfaceNamed(SightingReading):
    """
    A detection says what it rests on by the name the world knows that surface by, so
    what the statement names is read back the same way.
    """

    relation_type = SupportedBy

    @classmethod
    def holds_of(cls, instance: MontessoriDetection, stated: StatedRelation) -> bool:
        return instance.supporting_surface == stated.related_thing.name


class StandsWhereAllowed(SightingReading):
    """
    A detection is a sighting rather than a body, so where it stands is the position it
    was reported at rather than a volume a containment can be measured against.
    """

    relation_type = PlacementRelation

    @classmethod
    def holds_of(cls, instance: MontessoriDetection, stated: StatedRelation) -> bool:
        return stated.constraint().allows(instance.pose.to_position())


class WearsTheColor(SightingReading):
    """
    The colour a detection wears is the colour this set gives what was recognised.
    """

    relation_type = Colored

    @classmethod
    def holds_of(cls, instance: MontessoriDetection, stated: StatedRelation) -> bool:
        return instance.color == stated.related_thing


class IsTurnedSo(SightingReading):
    """
    Which way a detection is turned is the turn the fit settled on.
    """

    relation_type = Turned

    @classmethod
    def holds_of(cls, instance: MontessoriDetection, stated: StatedRelation) -> bool:
        return stated.constraint().allows_turn(instance.yaw)


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
        WearsTheColor,
        IsTurnedSo,
    )
    """
    How a look here reads each relation it can narrow itself by off what it found.
    """

    narrowing_relations: ClassVar[Tuple[Type[Relation], ...]] = tuple(
        reading.relation_type for reading in readings
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
        cls, instance: MontessoriDetection, stated: Sequence[StatedRelation]
    ) -> Tuple[Relation, ...]:
        """
        Every stated relation a detection does not satisfy, each asserted about what the
        look found so it can be read as the claim that failed.

        A relation this look can establish for itself is read off the sighting the way
        the look established it; any other is asked of the body the look stood in its
        world for the sighting, which is what lets whatever relation a statement can
        state be checked here.

        :param instance: One detection the look reported.
        :param stated: The relations, each as stated about the thing sought.
        :raises SightingHasNoBody: If a relation the look cannot establish itself is
            asked of a sighting that no body stands for.
        :return: The violated relations, in the order they were stated.
        """
        return tuple(
            stated_relation.about(cls._subject_of(instance, stated_relation))
            for stated_relation in stated
            if not cls._holds_of(instance, stated_relation)
        )

    @classmethod
    def _holds_of(cls, instance: MontessoriDetection, stated: StatedRelation) -> bool:
        """
        :param instance: One detection the look reported.
        :param stated: One relation, as stated about the thing sought.
        """
        for reading in cls.readings:
            if issubclass(stated.relation_type, reading.relation_type):
                return reading.holds_of(instance, stated)
        return bool(stated.about(cls._body_of(instance, stated))())

    @classmethod
    def _subject_of(cls, instance: MontessoriDetection, stated: StatedRelation) -> Any:
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
    def _body_of(instance: MontessoriDetection, stated: StatedRelation) -> Any:
        """
        :param instance: One detection the look reported.
        :param stated: The relation about to be asked of it.
        :raises SightingHasNoBody: If no body stands in a world for the sighting.
        :return: The body the look stood in its world for the sighting.
        """
        if not isinstance(instance, DetectedMontessoriShape):
            raise SightingHasNoBody(stated.relation_type.__name__, instance.label)
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
            placement.constraint()
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
        return stated[0].constraint()

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
