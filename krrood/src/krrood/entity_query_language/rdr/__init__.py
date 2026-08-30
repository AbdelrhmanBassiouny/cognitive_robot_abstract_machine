"""
EQL-native Ripple Down Rules.

The rule tree is a live EQL expression DAG (``Refinement`` / ``Alternative`` / ``Add``)
and classification is plain EQL evaluation. The RDR attaches to evaluation through the
aspect-oriented :class:`~krrood.entity_query_language.evaluation.EvaluationObserver`
hooks rather than driving a bespoke traversal.
"""

from krrood.entity_query_language.rdr.backend import (
    GroundTruth,
    ModelKey,
    RDRBackend,
)
from krrood.entity_query_language.rdr.backward_inference import (
    BackwardInferenceIndex,
    ConclusionSufficientConditionSets,
    SufficientConditionSet,
    get_conclusion_sufficient_conditions_from_a_rule_tree,
)
from krrood.entity_query_language.rdr.condition_resolver import (
    ChainConditionResolver,
    ConditionResolver,
    CornerCaseKnowledgeResolver,
    ResolutionMode,
    ResolvedCondition,
    TargetSufficientConditionsBasedResolver,
)
from krrood.entity_query_language.rdr.exceptions import (
    ExpertAbort,
    MultipleInferenceTargets,
    NoConclusionProvided,
    NoConditionsProvided,
    NoInferenceTarget,
    RDRDidNotConvergeError,
    UnsupportedInferenceTarget,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.function_case import FunctionCase
from krrood.entity_query_language.rdr.guard_condition import GuardCondition
from krrood.entity_query_language.rdr.interactive import IPythonInterface
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    ExpertInterface,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.observer import (
    ClassificationTrace,
    ConclusionObserver,
    FiredConclusion,
    classify_case,
    trace_case,
)
from krrood.entity_query_language.rdr.progress import (
    IPythonProgressBar,
    NullProgressReporter,
    ProgressReporter,
)
from krrood.entity_query_language.rdr.rule_tree import (
    insert_alternative,
    insert_refinement,
)
from krrood.entity_query_language.rdr.rule_tree_view import (
    RuleStatus,
    RuleView,
    render_rule_tree,
    walk_rules,
)
from krrood.entity_query_language.rdr.serialization import (
    FileModelSaver,
    ModelSaver,
    NullModelSaver,
    TemporaryModelSaver,
    load_rdr,
    rdr_to_python,
    save_rdr,
    save_rdr_with_case,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.underspecified import (
    UnderspecifiedMatch,
    is_ellipsis_target,
)
