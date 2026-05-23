"""
EQL-native Ripple Down Rules.

The rule tree is a live EQL expression DAG (``Refinement`` / ``Alternative`` / ``Add``)
and classification is plain EQL evaluation. The RDR attaches to evaluation through the
aspect-oriented :class:`~krrood.entity_query_language.evaluation.EvaluationObserver`
hooks rather than driving a bespoke traversal.
"""

from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interactive import IPythonExpert
from krrood.entity_query_language.rdr.observer import (
    ConclusionObserver,
    FiredConclusion,
    classify_case,
)
from krrood.entity_query_language.rdr.rule_tree import (
    insert_alternative,
    insert_refinement,
)
from krrood.entity_query_language.rdr.serialization import (
    load_rdr,
    rdr_to_python,
    save_rdr,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

__all__ = [
    "ConclusionObserver",
    "FiredConclusion",
    "classify_case",
    "Expert",
    "IPythonExpert",
    "insert_alternative",
    "insert_refinement",
    "EQLSingleClassRDR",
    "rdr_to_python",
    "save_rdr",
    "load_rdr",
]
