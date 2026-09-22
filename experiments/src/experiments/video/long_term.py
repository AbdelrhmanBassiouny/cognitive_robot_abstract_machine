"""
What long-term memory is asked over the perturbation grid, once the runs have played.

Every episode the robot recorded went into the results database, and the database is
asked in the same query language a live world is: which episodes the cube moved in, and
which of those the robot picked it up in. The answers are read from the database when
the scene is built, never written down here, and the grid lights the episodes they name;
how many episodes the questions range over, in simulation and on the robot, is read the
same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from krrood.entity_query_language.factories import a, contains
from krrood.entity_query_language.query.query import Query
from segmind.datastructures.events import DetectionEvent, MotionEvent, PickUpEvent
from typing_extensions import FrozenSet, List, Optional, Tuple, Type

from experiments.video.canvas import Span, changed_spans

from experiments.episodes.episode import RecordedTrial, Tick
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.montessori.results_database import ResultsDatabase

REMEMBERED_PIECE = "cube"
"""
What the piece asked about is called: every look names a piece for its kind and a
number (``cube_2``, ``cube_3``), so the kind is what is asked for.
"""


@dataclass(frozen=True)
class RememberedQuestion:
    """
    One question put to long-term memory, with the answer it gave.
    """

    english: str
    """
    The question as a person would ask it.
    """

    statement: Tuple[str, ...]
    """
    The query behind it, line by line, as it is written on screen.
    """

    episodes: Tuple[str, ...]
    """
    The identifier of every episode the answer names, in one order.
    """

    lit_as: str
    """
    What an episode the answer names is badged with on the grid.
    """

    def names(self, episode_identifier: str) -> bool:
        """
        :param episode_identifier: An episode.
        :return: Whether the answer names it.
        """
        return episode_identifier in self.episodes

    def changed_from(self, earlier: RememberedQuestion) -> Tuple[List[Span], ...]:
        """
        What of the statement differs from an earlier question's, line by line: the
        stretches to mark when this question follows that one on screen.

        :param earlier: The question asked before this one.
        """
        return tuple(
            changed_spans(before, after)
            for before, after in zip(earlier.statement, self.statement)
        )


@dataclass
class RememberedPiece:
    """
    The questions about one kind of piece, asked of everything the robot recorded.
    """

    memory: LongTermMemory = field(
        default_factory=lambda: LongTermMemory(ResultsDatabase())
    )
    """
    The recorded episodes, as the database holds them.
    """

    piece: str = REMEMBERED_PIECE
    """
    The kind of piece asked about.
    """

    over: Optional[FrozenSet[str]] = None
    """
    The identifiers of the episodes the questions are asked over, or None for every
    episode the memory holds: the query is run over the memory and its answer kept to
    these, which is what running it over a memory holding these alone would give, the
    query naming episodes one by one.
    """

    def where_it_moved(self) -> RememberedQuestion:
        """
        Which episodes recorded a motion of the piece, whoever moved it.
        """
        return self._asked(
            f"In which episodes did the {self.piece} move?",
            MotionEvent,
            "motion",
            f"the {self.piece} moved",
        )

    def where_the_robot_picked_it_up(self) -> RememberedQuestion:
        """
        Which episodes recorded the robot picking the piece up.
        """
        return self._asked(
            f"In which episodes did you pick the {self.piece} up?",
            PickUpEvent,
            "pickup",
            f"picked the {self.piece} up",
        )

    def both(self) -> List[RememberedQuestion]:
        """
        The two questions, motion first.
        """
        return [self.where_it_moved(), self.where_the_robot_picked_it_up()]

    def _asked(
        self, english: str, kind: Type[DetectionEvent], named: str, lit_as: str
    ) -> RememberedQuestion:
        """
        One question, answered from the database.

        :param english: The question as a person would ask it.
        :param kind: The kind of event an episode has to have recorded of the piece.
        :param named: What the event is called in the statement on screen.
        :param lit_as: What an episode the answer names is badged with.
        """
        found = set(self.memory.answer_with_identifiers(self.query(kind)))
        if self.over is not None:
            found &= self.over
        return RememberedQuestion(
            english=english,
            statement=self.statement(kind, named),
            episodes=tuple(sorted(found)),
            lit_as=lit_as,
        )

    def query(self, kind: Type[DetectionEvent]) -> Query:
        """
        The episode of every trial whose ticks recorded an event of the given kind about
        a piece of this kind: each of the three matched by its class, the event named
        where it is matched.

        :param kind: The kind of event.
        """
        trial, tick = a(RecordedTrial), a(Tick)
        return a(trial.episode).where(
            contains(trial.ticks, tick),
            contains(tick.events, event := a(kind)),
            contains(event.tracked_object.name.name, self.piece),
        )

    def statement(self, kind: Type[DetectionEvent], named: str) -> Tuple[str, ...]:
        """
        :meth:`query`, as it is written on screen: the same lines that build it.

        :param kind: The kind of event.
        :param named: What the event is called.
        """
        return (
            "trial, tick = a(RecordedTrial), a(Tick)",
            "a(trial.episode).where(contains(trial.ticks, tick),",
            f"    contains(tick.events, {named} := a({kind.__name__})),",
            f'    contains({named}.tracked_object.name.name, "{self.piece}"))',
        )
