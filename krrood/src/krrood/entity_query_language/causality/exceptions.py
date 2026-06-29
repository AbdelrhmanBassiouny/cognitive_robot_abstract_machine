from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from typing_extensions import Any

from krrood.exceptions import DataclassException


@dataclass
class CausalModelCannotExplainInstanceError(DataclassException, ABC):
    """Base error for a :class:`~krrood.entity_query_language.causality.causal_model.CausalModel`
    that is asked to explain an instance it cannot account for."""

    instance: Any
    """The instance the causal model failed to explain."""


@dataclass
class NotAnInferredInstanceError(CausalModelCannotExplainInstanceError):
    """Raised when the inference-explanation causal model is asked about an instance that was never
    inferred (it carries no recorded inference explanation)."""

    def error_message(self) -> str:
        return (
            f"{self.instance!r} has no inference explanation: it was not produced by an "
            f"inference query, so there is no recorded cause to report."
        )

    def suggest_correction(self) -> str:
        return (
            "Only ask 'why' about instances inferred through inference(...); build the target of "
            "'why' from an inference query rather than a directly constructed object."
        )
