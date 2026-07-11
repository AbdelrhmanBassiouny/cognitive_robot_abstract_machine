"""Ripple-Down-Rules engine for the Entity Query Language."""

from krrood.entity_query_language.rdr.backward_inference import (
    BackwardInferenceIndex,
    ConclusionKnowledge,
    GuardCondition,
    SufficientConditionSet,
    what_do_we_know_about,
)
from krrood.entity_query_language.rdr.condition_resolver import (
    ChainConditionResolver,
    ConditionResolver,
    CornerCaseKnowledgeResolver,
    ResolvedCondition,
    ResolutionMode,
    TargetKnowledgeResolver,
)
from krrood.entity_query_language.rdr.function_case import FunctionCase
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    ExpertAbort,
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
    load_rdr,
    rdr_to_python,
    save_rdr,
    save_rdr_with_case,
)
from krrood.entity_query_language.rdr.underspecified import (
    MultipleInferenceTargets,
    NoInferenceTarget,
    UnderspecifiedMatch,
    UnsupportedInferenceTarget,
    is_ellipsis_target,
)
