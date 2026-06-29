from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TYPE_CHECKING, List

from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from krrood.entity_query_language.dialogue.discourse_state import Obligation
    from krrood.entity_query_language.dialogue.speech_act import SpeechAct


@dataclass
class UndischargedObligationError(DataclassException):
    """Raised when a dialogue is closed while discourse obligations are still open."""

    obligations: List[Obligation]
    """The obligations that were never discharged."""

    def error_message(self) -> str:
        kinds = ", ".join(obligation.kind.value for obligation in self.obligations)
        return f"{len(self.obligations)} discourse obligation(s) remain undischarged: {kinds}."

    def suggest_correction(self) -> str:
        return "Respond to each open obligation (answer questions, acknowledge warnings) before closing the dialogue."


@dataclass
class ObligationAlreadyDischargedError(DataclassException):
    """Raised when an act would discharge an obligation that is already discharged."""

    obligation: Obligation
    """The obligation that was already discharged."""

    act: SpeechAct
    """The act that redundantly tried to discharge it."""

    def error_message(self) -> str:
        return (
            f"A {self.act.force.value} act cannot discharge the {self.obligation.kind.value} "
            f"obligation again: it was already discharged."
        )

    def suggest_correction(self) -> str:
        return "Each obligation is discharged once; do not respond to an already-answered question or acknowledged warning."


@dataclass
class NoMatchingObligationError(DataclassException):
    """Raised when a responding act matches no obligation at all."""

    act: SpeechAct
    """The act that found no obligation to discharge."""

    def error_message(self) -> str:
        return f"A {self.act.force.value} act discharges no open obligation: nothing required this response."

    def suggest_correction(self) -> str:
        return "Only respond when an obligation is open: answer after an Ask, acknowledge after a Warn."
