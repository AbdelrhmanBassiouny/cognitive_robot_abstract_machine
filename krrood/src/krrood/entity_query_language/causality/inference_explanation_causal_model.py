from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any

from krrood.entity_query_language.causality.causal_model import CausalModel
from krrood.entity_query_language.causality.exceptions import NotAnInferredInstanceError
from krrood.entity_query_language.explanation.explanation import explain_inference
from krrood.entity_query_language.questions.cause import Cause, CauseSet


@dataclass
class InferenceExplanationCausalModel(CausalModel):
    """Causal model backed by EQL inference explanations.

    Explains an instance by introspecting the
    :class:`~krrood.entity_query_language.explanation.explanation.InferenceExplanation` recorded when
    the instance was inferred: each satisfied condition (with its bindings) becomes a
    :class:`~krrood.entity_query_language.questions.cause.Cause`. The explanation is the computation
    that produced the binding, so the cause set is faithful to it by construction.
    """

    def explain(self, instance: Any) -> CauseSet:
        explanation = explain_inference(instance)
        if explanation is None:
            raise NotAnInferredInstanceError(instance=instance)
        causes = tuple(
            Cause(
                condition=condition_and_bindings.condition,
                bindings=condition_and_bindings.bindings,
            )
            for condition_and_bindings in explanation.get_satisfied_conditions_and_their_bindings()
        )
        return CauseSet(instance=instance, causes=causes)
