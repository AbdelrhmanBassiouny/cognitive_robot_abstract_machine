"""
The decision-query surface: explanation-bearing result handles and ``explain(result)``.

A decision is an underspecified query over a partially-specified decision object —
``an(InsertionAction)(slot=...).evaluate(backend=rdr_backend)`` — and choosing is filling
its ``...`` by evaluating with an RDR backend. This module carries the *asking why* half of
that pattern:

* :class:`ExplainedUnificationDict` is the result handle the explaining backend yields — an
  ordinary :class:`~krrood.entity_query_language.core.base_expressions.UnificationDict` that
  additionally carries the :class:`~krrood.entity_query_language.rdr.why.RDRConclusionExplanation`
  of its inferred value (fresh per yield, so no two handles alias one explanation).
* :func:`explain` reads that explanation back, routing an RDR conclusion through the same
  surface as an :func:`~krrood.entity_query_language.factories.inference`-created instance.
"""

from __future__ import annotations

from typing_extensions import Any, Optional

from krrood.entity_query_language.core.base_expressions import UnificationDict
from krrood.entity_query_language.explanation.explanation import (
    Explanation,
    explain_inference,
)
from krrood.entity_query_language.rdr.exceptions import UnexplainedResult
from krrood.entity_query_language.rdr.why import RDRConclusionExplanation


class ExplainedUnificationDict(UnificationDict):
    """A unification-dict result handle that also carries its value's RDR explanation.

    Being a :class:`~krrood.entity_query_language.core.base_expressions.UnificationDict`, it
    is read exactly like any yielded result; :attr:`conclusion_explanation` additionally
    exposes why the inferred value was reached.
    """

    conclusion_explanation: Optional[RDRConclusionExplanation] = None
    """The explanation of the inferred value, or ``None`` when no rule fired."""


def explain(result: Any) -> Explanation:
    """Explain how ``result`` got its value, through one surface for RDR and inference alike.

    :param result: A result handle — an :class:`ExplainedUnificationDict` from an RDR
        decision query, or an
        :func:`~krrood.entity_query_language.factories.inference`-created instance.
    :return: The :class:`~krrood.entity_query_language.explanation.explanation.Explanation`
        of how ``result`` was produced.
    :raises UnexplainedResult: When ``result`` carries no explanation (no rule fired, and it
        was not produced by inference).
    """
    if isinstance(result, ExplainedUnificationDict):
        explanation = result.conclusion_explanation
        if explanation is None:
            raise UnexplainedResult(result)
        return explanation
    inference_explanation = explain_inference(result)
    if inference_explanation is None:
        raise UnexplainedResult(result)
    return inference_explanation
