"""
Constructs for querying a probabilistic model directly from the Entity Query Language:
``distribution_of`` and ``probability_of``.

A third case -- the expectation of an attribute -- reuses the existing
:class:`~krrood.entity_query_language.operators.aggregators.Average` aggregator
(``average(...)``) instead of a bespoke construct here:
:class:`~krrood.entity_query_language.backends.ProbabilisticBackend` recognizes a bare
``average(...)`` selection and answers it in closed form via
``ProbabilisticModel.moment`` instead of sampling and averaging rows, so the same
declarative call reads correctly under either backend. See
:meth:`~krrood.entity_query_language.backends.ProbabilisticBackend._resolve_average`.

Bundled in one module rather than one file each (unlike ``operators/causal.py``, which
is one coupled do()-intervention feature) because these are parallel operations on the
same base, the same shape ``operators/aggregators.py`` bundles ``Sum``/``Max``/``Min``/
... in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing_extensions import Any, Iterator, Tuple, TYPE_CHECKING

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.variable import Literal
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.exceptions import (
    BackendCannotEvaluateProbabilisticQuery,
    NoSolutionFound,
)
if TYPE_CHECKING:
    from krrood.entity_query_language.core.mapped_variable import Attribute
    from krrood.entity_query_language.factories import ConditionType
    from krrood.entity_query_language.query.match import Match
    from krrood.parametrization.model_registries import ModelRegistry
    from krrood.parametrization.parameterizer import (
        ConditionParameters,
        UnderspecifiedParameters,
    )

# krrood.parametrization.parameterizer reaches back to this module's own package
# (krrood.entity_query_language.factories imports Distribution/Probability from here),
# so importing it at module level -- like operators/causal.py's leaf-module imports --
# would be circular. Each _resolve_ imports it locally instead, deferred until a
# ProbabilisticBackend actually evaluates the query, by which point every module
# involved has finished loading.


@dataclass(eq=False, repr=False)
class ProbabilisticQuery(Evaluable, ABC):
    """
    Shared base for EQL constructs that query a probabilistic model directly --
    ``distribution_of``, ``probability_of`` -- rather than selecting or generating
    rows/instances.

    This is a probabilistic operation, not a data selection, so none of these ever
    resolve natively or under any backend other than
    :class:`~krrood.entity_query_language.backends.ProbabilisticBackend`, which
    dispatches to :meth:`_resolve_` for whichever subclass it is given.
    """

    def _evaluate_natively_(self) -> Iterator:
        raise BackendCannotEvaluateProbabilisticQuery(self)

    @abstractmethod
    def _resolve_(self, model_registry: ModelRegistry) -> Any:
        """
        Resolve this query against a model obtained from ``model_registry``.

        :param model_registry: The registry to resolve a model with.
        :return: Whatever the underlying ``ProbabilisticModel`` operation naturally
            returns -- a plain value, unwrapped.
        """


@dataclass(eq=False, repr=False)
class Probability(ProbabilisticQuery):
    """
    Requests the probability of a condition, e.g. ``probability_of(x.A > 5)`` for
    ``x = variable(MyClass)``. The condition may be any expression a ``.where(...)``
    condition already accepts (comparators combined with ``and_``/``or_``/``not_``,
    ranges, ...) -- it is translated into a
    {py:class}`~random_events.product_algebra.Event` the same way.

    ``ConditionType`` also allows a bare ``bool`` (``probability_of(True)``); a plain
    Python ``bool`` carries no attribute/chain, so it's wrapped in a
    :class:`~krrood.entity_query_language.core.variable.Literal` on construction, the
    same normalization ``and_``/``or_``/``not_`` already apply to a bare-bool operand
    -- this keeps ``condition`` always a real EQL expression, so it verbalizes (*"the
    probability that True"*) with no special-casing needed downstream. It still won't
    *evaluate*, though: a content-free condition names no class, so there is no model
    to resolve it against --
    :class:`~krrood.parametrization.exceptions.JointQueryAcrossClassesNotSupported`
    (empty ``owner_classes``) is raised at resolution time, same as any other
    condition that references no attributes.
    """

    condition: ConditionType
    """
    The condition to compute the probability of.
    """

    def __post_init__(self):
        if not isinstance(self.condition, SymbolicExpression):
            self.condition = Literal(_value_=self.condition)

    def _resolve_(self, model_registry: ModelRegistry) -> float:
        from krrood.parametrization.parameterizer import ConditionParameters

        parameters = ConditionParameters(self.condition)
        model = model_registry.get_model(parameters)
        return model.probability(parameters.event)

    def __repr__(self) -> str:
        return f"probability_of({self.condition!r})"


@dataclass(eq=False, repr=False)
class Distribution(ProbabilisticQuery):
    """
    Requests the distribution a :class:`~krrood.entity_query_language.query.match.Match`'s
    conditions describe -- the probabilistic interpretation of
    :py:func:`~krrood.entity_query_language.factories.a`/:py:func:`~krrood.entity_query_language.factories.an`/
    :py:func:`~krrood.entity_query_language.factories.the`. Exactly the same sequence
    :class:`~krrood.entity_query_language.backends.ProbabilisticBackend` already
    applies before *sampling* from a match -- literal-valued kwargs condition the
    circuit (``arm=0.3``), ``.where(...)`` conditions truncate it, and underspecified
    (``...``) fields are the joint's free variables -- just returned directly instead
    of sampled from:

    ``distribution_of(a(Pick)(arm=0.3, outcome=...))`` -- the distribution over
    ``outcome`` given ``arm == 0.3``.

    Optional trailing ``*variables`` narrow the result to a subset of the match's free
    variables (further marginalization), e.g.
    ``distribution_of(match, match.variable.outcome)``. Without them, every one of the
    match's free variables is kept.
    """

    match: Match
    """
    The match whose conditions describe the distribution.
    """

    variables: Tuple[Attribute, ...] = ()
    """
    The match's variables to narrow the result to. Empty keeps every one of the
    match's free variables.
    """

    def _resolve_(self, model_registry: ModelRegistry) -> Any:
        from krrood.parametrization.parameterizer import UnderspecifiedParameters

        parameters = UnderspecifiedParameters(self.match)
        model = model_registry.get_model(parameters)
        result = parameters.resolve_conditioned_and_truncated_model(model)
        if result is None:
            raise NoSolutionFound(self)

        if self.variables:
            selected = [parameters.variables[v._name_] for v in self.variables]
            result = result.marginal(selected)
            if result is None:
                raise NoSolutionFound(self)

        return result

    def __repr__(self) -> str:
        args = "".join(f", {v!r}" for v in self.variables)
        return f"distribution_of({self.match!r}{args})"
