"""
Mimics of a program that asks queries, some of them while another query is answered,
and of an observer that logs what it is told about them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import Iterator, List

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.query_observation import AskedQuery, QueryObserver

# %% shelves a program asks about


@dataclass(unsafe_hash=True)
class Shelf:
    """
    A shelf a program asks about by its width.
    """

    width: float
    """
    The width of the shelf, in metres.
    """


@dataclass
class WideShelvesFoundOnIteration:
    """
    A variable domain that asks which of its shelves are wide each time it is
    iterated.
    """

    shelves: List[Shelf]
    """
    The shelves asked about.
    """

    minimum_width: float = 1.0
    """
    The width from which a shelf counts as wide, in metres.
    """

    def __iter__(self) -> Iterator[Shelf]:
        shelf = variable(Shelf, domain=self.shelves)
        yield from an(entity(shelf).where(shelf.width >= self.minimum_width)).evaluate()


# %% an observer logging what it is told


class ObservedMoment(Enum):
    """
    The moments in a query's evaluation an observer is told about.
    """

    ASKED = "asked"
    """
    The query was asked.
    """

    ANSWERED = "answered"
    """
    The query's answering ended.
    """


@dataclass
class ObservedEvent:
    """
    One thing an observer was told.
    """

    moment: ObservedMoment
    """
    What happened to the query.
    """

    asked: AskedQuery
    """
    The query it happened to.
    """

    answer_count: int
    """
    How many answers the query had given when the observer was told.
    """


@dataclass
class QueryLog(QueryObserver):
    """
    Logs every query it is told about, in the order it is told.
    """

    events: List[ObservedEvent] = field(default_factory=list)
    """
    What it was told, in order.
    """

    def on_query_asked(self, asked: AskedQuery) -> None:
        self.events.append(
            ObservedEvent(ObservedMoment.ASKED, asked, len(asked.answers))
        )

    def on_query_answered(self, asked: AskedQuery) -> None:
        self.events.append(
            ObservedEvent(ObservedMoment.ANSWERED, asked, len(asked.answers))
        )
