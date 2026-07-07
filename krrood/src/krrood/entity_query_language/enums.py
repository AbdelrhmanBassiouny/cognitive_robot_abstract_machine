from __future__ import annotations

from enum import Enum, auto, StrEnum


class InferMode(Enum):
    """
    The infer mode of a predicate, whether to infer new relations or retrieve current relations.
    """

    Auto = auto()
    """
    Inference is done automatically depending on the world state.
    """
    Always = auto()
    """
    Inference is always performed.
    """
    Never = auto()
    """
    Inference is never performed.
    """


class EQLMode(Enum):
    """
    The modes of an entity query.
    """

    Rule = auto()
    """
    Means this is a Rule that infers new relations/instances.
    """
    Query = auto()
    """
    Means this is a Query that searches for matches
    """


class DomainSource(Enum):
    """
    The domain source of a variable.
    """

    EXPLICIT = auto()
    """
    Explicitly provided domain.
    """
    DEDUCTION = auto()
    """
    Inferred using deductive reasoning.
    """
    GROUPING = auto()
    """
    Derived from grouping operations.
    """


class EvaluationContextKey(StrEnum):
    """
    Enumeration of keys used in the evaluation context's data dictionary.
    """

    SATISFIED_IDS_KEY = "satisfied_condition_ids"
    """
    A reserved key in the evaluation context's data dictionary for tracking the set of satisfied condition expression IDs
    during the current evaluation iteration.
    """

    EVALUATED_IDS_KEY = "evaluated_expression_ids"
    """
    A reserved key in the evaluation context's data dictionary for tracking the cumulative set of all expression IDs
    evaluated so far during the current evaluation.
    """

    EVALUATED_SNAPSHOT_KEY = "evaluated_expression_ids_snapshot"
    """
    A reserved key caching the most recent immutable snapshot of the evaluated-id set as a
    ``(length, snapshot)`` pair. Because the evaluated-id set only grows, its length is a valid
    version key: results yielded while the set has a given length share one snapshot instead of
    each copying the whole set.
    """

    SUBQUERY_RESULT_CACHE_KEY = "subquery_result_cache"
    """
    A reserved key mapping a compiled query node's identifier to the lazily-cached stream of its
    results within the current top-level evaluation, so an uncorrelated subquery reached from many
    outer rows is computed once and replayed.
    """

    OUTERMOST_QUERY_ID_KEY = "outermost_query_id"
    """
    A reserved key holding the identifier of the first compiled query node to evaluate in the current
    top-level evaluation. Any other compiled query node that evaluates is a nested subquery, which the
    query scope isolates from the surrounding bindings.
    """
