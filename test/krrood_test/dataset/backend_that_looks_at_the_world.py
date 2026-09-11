"""
A backend that answers a statement about the world by looking at it, mimicking the shape
a backend over a sensor takes.

Such a backend is generative: the things it reports are not in any domain the statement
was given, and it is the look that brings them into existence as instances. What the
look can act on narrows it; what it cannot is checked over what came back.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import ClassVar, List, Optional

from krrood.entity_query_language.backends import LookRequest, PerceptionBackend

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

    searched_place: Optional[str] = field(init=False, default=None)
    """
    The place the last look was narrowed to, or ``None`` when the statement named none.
    """

    PLACE_ATTRIBUTE_NAME: ClassVar[str] = "place"
    """
    The attribute of a sighting a look can narrow itself by.
    """

    def look(self, request: LookRequest[Sighting]) -> List[Sighting]:
        """
        Look for what the statement asks about, narrowed to one place when it names one.

        :param request: What the statement asks a look for.
        :return: Every sighting the look found.
        """
        self.searched_place = request.value_stated_for(self.PLACE_ATTRIBUTE_NAME)
        if self.searched_place is None:
            return list(self.sightings)
        return [
            sighting
            for sighting in self.sightings
            if sighting.place == self.searched_place
        ]
