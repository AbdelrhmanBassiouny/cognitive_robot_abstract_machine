"""
What long-term memory is asked over the perturbation grid, once the runs have played.

Every episode the robot recorded went into the results database, and the database is
asked in the same query language a live world is: which episodes the cube moved in, and
which of those the robot picked it up in. The answers are read from the database when
the scene is built, never written down here, and the grid lights the episodes they name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from krrood.entity_query_language.factories import an, contains, entity, variable
from krrood.entity_query_language.query.query import Query
from segmind.datastructures.events import DetectionEvent, MotionEvent, PickUpEvent
from typing_extensions import List, Tuple, Type

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

    def where_it_moved(self) -> RememberedQuestion:
        """
        Which episodes recorded a motion of the piece, whoever moved it.
        """
        return self._asked(
            f"In which episodes did the {self.piece} move?",
            MotionEvent,
            f"the {self.piece} moved",
        )

    def where_the_robot_picked_it_up(self) -> RememberedQuestion:
        """
        Which episodes recorded the robot picking the piece up.
        """
        return self._asked(
            f"In which episodes did you pick the {self.piece} up?",
            PickUpEvent,
            f"picked the {self.piece} up",
        )

    def both(self) -> List[RememberedQuestion]:
        """
        The two questions, motion first.
        """
        return [self.where_it_moved(), self.where_the_robot_picked_it_up()]

    def _asked(
        self, english: str, kind: Type[DetectionEvent], lit_as: str
    ) -> RememberedQuestion:
        """
        One question, answered from the database.

        :param english: The question as a person would ask it.
        :param kind: The kind of event an episode has to have recorded of the piece.
        :param lit_as: What an episode the answer names is badged with.
        """
        found = self.memory.answer_with_identifiers(self.query(kind))
        return RememberedQuestion(
            english=english,
            statement=self.statement(kind),
            episodes=tuple(sorted(set(found))),
            lit_as=lit_as,
        )

    def query(self, kind: Type[DetectionEvent]) -> Query:
        """
        The episode of every trial whose ticks recorded an event of the given kind about
        a piece of this kind.

        :param kind: The kind of event.
        """
        trial = variable(RecordedTrial, domain=[])
        tick = variable(Tick, domain=[])
        event = variable(kind, domain=[])
        return an(
            entity(trial.episode).where(
                contains(trial.ticks, tick),
                contains(tick.events, event),
                contains(event.tracked_object.name.name, self.piece),
            )
        )

    def statement(self, kind: Type[DetectionEvent]) -> Tuple[str, ...]:
        """
        :meth:`query`, as it is written on screen: the same lines that build it.

        :param kind: The kind of event.
        """
        return (
            f"trial, tick, event = variable(RecordedTrial), variable(Tick), variable({kind.__name__})",
            "an(entity(trial.episode).where(",
            "    contains(trial.ticks, tick), contains(tick.events, event),",
            f'    contains(event.tracked_object.name.name, "{self.piece}")))',
        )
