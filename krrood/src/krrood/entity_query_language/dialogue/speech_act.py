from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.dialogue.answer import (
    Answer,
    CauseSetAnswer,
    WhatAnswer,
)
from krrood.entity_query_language.questions.cause import CauseSet


class IllocutionaryForce(Enum):
    """The illocutionary force of a speech act — what the speaker does in saying it."""

    QUESTION = "question"
    ASSERTION = "assertion"
    EXPLANATION = "explanation"
    WARNING = "warning"
    ACKNOWLEDGEMENT = "acknowledgement"


@dataclass
class SpeechAct(ABC):
    """A communicative act: propositional content carried with an illocutionary force.

    Speech acts are dumb, typed data. The discourse logic (which act discharges which obligation)
    lives in :class:`~krrood.entity_query_language.dialogue.discourse_state.DiscourseState` and the
    rendering lives in the verbalization rules, so an act itself only declares its content and force.
    """

    @property
    @abstractmethod
    def force(self) -> IllocutionaryForce:
        """:return: The illocutionary force of this act."""


@dataclass
class Ask(SpeechAct):
    """Pose a question (an entity-query-language expression to be answered)."""

    question: SymbolicExpression
    """The question expression, e.g. a ``Why`` operator or a retrieval entity."""

    @property
    def force(self) -> IllocutionaryForce:
        return IllocutionaryForce.QUESTION


@dataclass
class Inform(SpeechAct):
    """Assert the answer to a ``what`` question."""

    answer: WhatAnswer
    """The retrieval answer being asserted."""

    @property
    def force(self) -> IllocutionaryForce:
        return IllocutionaryForce.ASSERTION


@dataclass
class Explain(SpeechAct):
    """State the reason behind something — the answer to a ``why`` question."""

    answer: CauseSetAnswer
    """The cause-set answer being given."""

    @property
    def force(self) -> IllocutionaryForce:
        return IllocutionaryForce.EXPLANATION


@dataclass
class Warn(SpeechAct):
    """Warn about a proposition."""

    proposition: SymbolicExpression
    """The expression the hearer is being warned about."""

    @property
    def force(self) -> IllocutionaryForce:
        return IllocutionaryForce.WARNING


@dataclass
class Acknowledge(SpeechAct):
    """Acknowledge a prior act, discharging an outstanding acknowledgement obligation."""

    @property
    def force(self) -> IllocutionaryForce:
        return IllocutionaryForce.ACKNOWLEDGEMENT


def ask(question: SymbolicExpression) -> Ask:
    """:return: An :class:`Ask` posing *question*."""
    return Ask(question=question)


def inform(answer: WhatAnswer) -> Inform:
    """:return: An :class:`Inform` asserting *answer*."""
    return Inform(answer=answer)


def explain(cause_set: CauseSet) -> Explain:
    """:return: An :class:`Explain` giving *cause_set* as the reason."""
    return Explain(answer=CauseSetAnswer(cause_set=cause_set))


def warn(proposition: SymbolicExpression) -> Warn:
    """:return: A :class:`Warn` about *proposition*."""
    return Warn(proposition=proposition)


def acknowledge() -> Acknowledge:
    """:return: An :class:`Acknowledge`."""
    return Acknowledge()
