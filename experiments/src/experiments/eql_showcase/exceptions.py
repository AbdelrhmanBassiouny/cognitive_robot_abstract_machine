"""
What can go wrong while the EQL showcase answers the parts a plan leaves open.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.query.match import Match
from krrood.exceptions import DataclassException


@dataclass
class NoBackendAnswers(DataclassException):
    """
    Raised when none of the backends declares it can answer a statement a plan left
    open.
    """

    statement: Match
    """
    The statement nobody could answer.
    """

    def error_message(self) -> str:
        return f"No backend declares it can answer {self.statement}."

    def suggest_correction(self) -> str:
        return "Add a backend that can answer statements of this kind."
