from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import List

from krrood.entity_query_language.dialogue.exceptions import (
    NoMatchingObligationError,
    ObligationAlreadyDischargedError,
    UndischargedObligationError,
)
from krrood.entity_query_language.dialogue.speech_act import (
    Acknowledge,
    Ask,
    Explain,
    Inform,
    SpeechAct,
    Warn,
)


class ObligationKind(Enum):
    """The kind of response a discourse obligation requires."""

    ANSWER = "answer"
    """An open question obliges an answer (an :class:`Inform` or :class:`Explain`)."""

    ACKNOWLEDGEMENT = "acknowledgement"
    """A warning obliges an acknowledgement (an :class:`Acknowledge`)."""


@dataclass
class Obligation:
    """A pending discourse obligation introduced by one act and discharged by a responding act."""

    kind: ObligationKind
    """What kind of response discharges this obligation."""

    source_act: SpeechAct
    """The act that introduced this obligation (the question or the warning)."""

    discharged: bool = False
    """Whether a responding act has already discharged this obligation."""

    def matches(self, act: SpeechAct) -> bool:
        """:return: Whether *act* is of the kind that discharges this obligation, regardless of
        whether it is already discharged."""
        if self.kind is ObligationKind.ANSWER:
            return isinstance(act, (Inform, Explain))
        return isinstance(act, Acknowledge)


@dataclass
class DiscourseState:
    """The obligations outstanding in a teaching dialogue (a Traum-style discourse model).

    Registering a question raises an answer obligation; registering a warning raises an
    acknowledgement obligation; registering a responding act discharges the matching open obligation.
    This is an instance, not global state, so independent dialogues stay isolated.
    """

    obligations: List[Obligation] = field(default_factory=list)
    """The obligations introduced so far, discharged or not, in introduction order."""

    def register(self, act: SpeechAct) -> None:
        """Update the discourse with *act*: raise an obligation for a question/warning, or
        discharge the matching open obligation for a responding act."""
        if isinstance(act, Ask):
            self.obligations.append(Obligation(ObligationKind.ANSWER, act))
            return
        if isinstance(act, Warn):
            self.obligations.append(Obligation(ObligationKind.ACKNOWLEDGEMENT, act))
            return
        self.discharge(act)

    def discharge(self, act: SpeechAct) -> Obligation:
        """Discharge the first open obligation that *act* matches.

        :return: The obligation discharged.
        :raises ObligationAlreadyDischargedError: When *act* matches only already-discharged obligations.
        :raises NoMatchingObligationError: When *act* matches no obligation at all.
        """
        matching = [obligation for obligation in self.obligations if obligation.matches(act)]
        open_matching = [obligation for obligation in matching if not obligation.discharged]
        if open_matching:
            obligation = open_matching[0]
            obligation.discharged = True
            return obligation
        if matching:
            raise ObligationAlreadyDischargedError(obligation=matching[-1], act=act)
        raise NoMatchingObligationError(act=act)

    @property
    def open_obligations(self) -> List[Obligation]:
        """:return: The obligations that have not yet been discharged."""
        return [obligation for obligation in self.obligations if not obligation.discharged]

    def assert_all_discharged(self) -> None:
        """:raises UndischargedObligationError: When any obligation is still open."""
        if self.open_obligations:
            raise UndischargedObligationError(obligations=self.open_obligations)
