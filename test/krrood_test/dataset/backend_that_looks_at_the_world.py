"""
A backend that answers a statement about the world by looking at it, mimicking the shape
a backend over a sensor takes.

Such a backend is generative: the things it reports are not in any domain the statement
was given, and it is the look that brings them into existence as instances. What the
look can act on narrows it; what it cannot is checked over what came back.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, ClassVar, List, Optional, Tuple, Type

from krrood.entity_query_language.backends import LookRequest, PerceptionBackend
from krrood.entity_query_language.predicate import Relation, Triple
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    clause,
    Noun,
    Verb,
)

# %% what a look finds


@dataclass(frozen=True)
class Sighting:
    """
    One thing a look found, and where it was standing.
    """

    label: str
    """
    What it was recognised as.
    """

    place: str
    """
    What the world calls the place it was found in.
    """


@dataclass(frozen=True)
class SightingOfSomethingHeldUp(Sighting):
    """
    A sighting of a kind a statement can ask for on its own, so that a look answering
    with more kinds than were asked for is a case the tests can state.
    """


# %% what the world means by where a thing is


@dataclass(frozen=True)
class Place:
    """
    Somewhere in the world a thing can be found, mimicking an entity the world holds.
    """

    name: str
    """
    What the world calls it.
    """


@dataclass(eq=False)
class StandingOn(Triple):
    """
    Asserts that a thing rests on a place.

    A relation rather than an attribute, so a statement narrowing a look by it names a
    class the world already means something by instead of spelling a field's name.
    """

    thing: Any
    """
    What is resting.
    """

    place: Place
    """
    What it is resting on.
    """

    @property
    def subject(self) -> Any:
        return self.thing

    @property
    def object(self) -> Place:
        return self.place

    def __call__(self) -> bool:
        return self.thing.place == self.place.name

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return clause(Noun(fields["thing"]), Verb("stand on"), Noun(fields["place"]))


@dataclass(eq=False)
class StandingBetween(Relation):
    """
    Asserts that a thing rests somewhere between two places.

    A relation of more than two operands, so what a look reads off a statement has to be
    the whole relation rather than the one thing a triple relates its subject to. The
    thing it is asserted about is optional, so the relation can also be built as the
    constraint alone -- which is the form a search reads before anything has been found.
    """

    thing: Optional[Any] = None
    """
    What is resting between the two, or None where the relation is the constraint alone.
    """

    one: Optional[Place] = None
    """
    One of the two places.
    """

    other: Optional[Place] = None
    """
    The other of the two.
    """

    @property
    def subject(self) -> Any:
        return self.thing

    def __call__(self) -> bool:
        return self.thing.place in (self.one.name, self.other.name)

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return clause(
            Noun(fields["thing"]),
            Verb("stand between"),
            Noun(fields["one"]),
            Noun(fields["other"]),
        )


# %% the backend


@dataclass
class BackendThatLooksAtTheWorld(PerceptionBackend):
    """
    Answers by looking, over a fixed set of sightings standing in for a world.
    """

    sightings: List[Sighting] = field(default_factory=list)
    """
    Everything a look could find, were it to search everywhere.
    """

    searched_place: Optional[Place] = field(init=False, default=None)
    """
    The place the last look was narrowed to, or ``None`` when the statement named none.
    """

    narrowing_relations: ClassVar[Tuple[Type[Triple], ...]] = (StandingOn,)
    """
    A look here can be narrowed to one place, and says so by the relation that means it.
    """

    def look(self, request: LookRequest[Sighting]) -> List[Sighting]:
        """
        Look for what the statement asks about, narrowed to one place when it names one.

        :param request: What the statement asks a look for.
        :return: Every sighting the look found.
        """
        self.searched_place = request.related_by(StandingOn)
        if self.searched_place is None:
            return list(self.sightings)
        return [
            sighting
            for sighting in self.sightings
            if sighting.place == self.searched_place.name
        ]

    def relations_hold(
        self, instance: Sighting, request: LookRequest[Sighting]
    ) -> bool:
        """
        Whether a sighting stands where the statement said the thing sought stands.

        :param instance: One sighting the look found.
        :param request: What the look was asked for.
        """
        place = request.related_by(StandingOn)
        return place is None or instance.place == place.name
