"""
EQL-native Ripple Down Rules.

The rule tree is a live EQL expression DAG (``Refinement`` / ``Alternative`` / ``Add``)
and classification is plain EQL evaluation. The RDR attaches to evaluation through the
aspect-oriented :class:`~krrood.entity_query_language.evaluation.EvaluationObserver`
hooks rather than driving a bespoke traversal.
"""

from krrood.entity_query_language.rdr.observer import (
    ConclusionObserver,
    FiredConclusion,
    classify_case,
)

__all__ = ["ConclusionObserver", "FiredConclusion", "classify_case"]
