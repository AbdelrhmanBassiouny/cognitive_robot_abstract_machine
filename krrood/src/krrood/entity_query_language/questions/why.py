from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Iterator, Optional

from krrood.entity_query_language.causality.causal_model import CausalModel
from krrood.entity_query_language.causality.inference_explanation_causal_model import (
    InferenceExplanationCausalModel,
)
from krrood.entity_query_language.core.base_expressions import (
    OperationResult,
    SymbolicExpression,
    UnaryExpression,
)


@dataclass(eq=False, repr=False)
class Why(UnaryExpression):
    """Question operator that explains why the bindings of its child expression were inferred.

    Denotation: ``why(x)`` evaluates the child and, for each inferred instance it produces, yields
    the :class:`~krrood.entity_query_language.questions.cause.CauseSet` that :attr:`causal_model`
    attributes to that instance — the conditions (with bindings) whose satisfaction caused the
    inference. The cause set is the value bound to this operator, so ``why(x).first()`` returns it
    directly.
    """

    causal_model: CausalModel = field(
        default_factory=InferenceExplanationCausalModel, kw_only=True
    )
    """The causal model consulted to explain each binding. Defaults to inference-explanation
    introspection; inject another :class:`CausalModel` to explain instances produced by other
    tools (the action library, the physics simulator, ...)."""

    explained_proposition: Optional[SymbolicExpression] = field(
        default=None, kw_only=True
    )
    """The proposition surfaced when the question is verbalized — the relation whose inference is
    questioned (e.g. *"a MontessoriObject is in the square hole"*). Defaults to the child itself."""

    def _evaluate__(self, sources: OperationResult) -> Iterator[OperationResult]:
        for child_result in self._child_._evaluate_(sources):
            instance = self._child_._process_result_(child_result)
            cause_set = self.causal_model.explain(instance)
            yield OperationResult(
                child_result.bindings | {self._id_: cause_set},
                False,
                self,
                child_result,
            )
