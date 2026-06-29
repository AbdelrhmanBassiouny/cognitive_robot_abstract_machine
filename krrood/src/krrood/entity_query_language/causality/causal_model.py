from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import Any

from krrood.entity_query_language.questions.cause import CauseSet


@dataclass
class CausalModel(ABC):
    """Port to a causal model embodied in a cognitive robot's tool.

    Each tool that holds a causal model (the inference engine, the action library, the physics
    simulator, the event log, ...) implements this single method so a question operator can ask it
    for the cause set behind an instance, without depending on how that tool represents causation.
    This is the dependency-inversion seam: new tools plug in new ``CausalModel`` implementations
    without changing the operators that consume them.
    """

    @abstractmethod
    def explain(self, instance: Any) -> CauseSet:
        """:return: The cause set explaining why *instance* holds.

        :raises CausalModelCannotExplainInstanceError: When *instance* cannot be explained by this
            model.
        """
