"""
The question set asked the moment the object it is about stops moving.

A query asked at the end of a run stands minutes after the event it is about, and a card
of the two says nothing about when the answer was known. Asked directly after the
monitor reports the object has come to rest, the query stands right after the stretch of
the trial the card draws.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from segmind.datastructures.events import DetectionEvent, StopTranslationEvent
from typing_extensions import Callable, List, Optional

from experiments.episodes.episode import RecordedQuery
from experiments.episodes.observer import EpisodeObserver, ObserverListener
from experiments.questions.question_set import QuestionSet
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world_description.world_entity import Body

# %% asking once the object has come to rest


@dataclass
class QuestionAfterTheMove:
    """
    Asks the question set once, the moment the monitor reports the object asked about
    has stopped moving, and records the query on the trial.

    Told what a monitor detects, in place of the trial's own listener, which it tells in
    turn.
    """

    observer: EpisodeObserver
    """
    The trial's observer, which the query is recorded on and whose clock stamps it.
    """

    asked_about: Body
    """
    The object the question set is about, whose coming to rest is waited for.
    """

    question_set: Callable[[], QuestionSet]
    """
    What is asked, built when it is asked: what the object is placed against may only
    be known once the run has looked.
    """

    robot: AbstractRobot
    """
    The robot the questions are put to.
    """

    listener: Optional[ObserverListener] = None
    """
    The trial's own listener, told what the monitor detected before it is looked at
    here; None where the run records its ticks some other way.
    """

    asked: bool = field(init=False, default=False)
    """
    Whether the question set has been asked yet.
    """

    def receive(self, events: List[DetectionEvent]) -> None:
        """
        Take what the monitor just detected, and ask once it says the object asked about
        has stopped moving.

        :param events: The newly detected events.
        """
        if self.listener is not None:
            self.listener.receive(events)
        if self.asked or not any(self.stops_the_object(event) for event in events):
            return
        self.ask()

    def stops_the_object(self, event: DetectionEvent) -> bool:
        """
        Whether the given event says the object asked about has stopped moving.

        Matched by the name the twin gives the object rather than by identity, since a
        monitor may hold the object as its own world does.

        :param event: The event to read.
        """
        return (
            isinstance(event, StopTranslationEvent)
            and event.tracked_object.name == self.asked_about.name
        )

    def ask(self) -> List[RecordedQuery]:
        """
        Ask the question set now, whatever the monitor has said.

        :return: The queries that were recorded.
        """
        self.asked = True
        return self.observer.ask(
            self.question_set(), self.robot, self.observer.elapsed_seconds
        )

    def ask_if_not_yet(self) -> List[RecordedQuery]:
        """
        Ask the question set now unless it has been asked already: what a run does as it
        ends, so a run in which the object never came to rest is still questioned.

        :return: The queries that were recorded, or none where it had been asked.
        """
        if self.asked:
            return []
        return self.ask()
