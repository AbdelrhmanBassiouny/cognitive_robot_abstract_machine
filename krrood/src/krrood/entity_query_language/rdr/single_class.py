"""
EQL-native Single-Class Ripple Down Rules.

The rule tree is a live EQL query DAG over a shared case variable. Classification is
plain EQL evaluation (via :func:`classify_case`); fitting grows the DAG in place using
the observed firing rule as the anchor:

* wrong conclusion  -> add a **refinement** at the firing rule (it overrides)
* no rule fired     -> add an **alternative** at the conditions root

Single-class means conclusions are mutually exclusive: each case resolves to one value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, List, Optional, Type

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.factories import add, entity, variable
from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.observer import ConclusionObserver, classify_case
from krrood.entity_query_language.rdr.rule_tree import (
    insert_alternative,
    insert_refinement,
)


@dataclass
class EQLSingleClassRDR:
    """A single-class RDR whose rule tree is a live EQL expression DAG."""

    case_type: Type
    """The type of case the RDR classifies (e.g. ``Animal``)."""
    conclusion_attribute_name: str
    """The underspecified attribute the RDR predicts (e.g. ``"species"``)."""

    case_variable: Variable = field(init=False)
    """The shared EQL variable the whole rule tree ranges over."""
    conclusion_variable: CanBehaveLikeAVariable = field(init=False)
    """The attribute expression the rules conclude on (``case_variable.<attr>``)."""
    query: Optional[Query] = field(init=False, default=None)
    """The root rule-tree query; ``None`` until the first rule is added."""

    def __post_init__(self) -> None:
        self.case_variable = variable(self.case_type, domain=[])
        self.conclusion_variable = getattr(
            self.case_variable, self.conclusion_attribute_name
        )

    def classify(self, case: Any) -> Optional[Any]:
        """:return: The inferred conclusion for ``case``, or ``None`` if no rule fires."""
        if self.query is None:
            return None
        return self._observe(case).conclusion

    def _observe(self, case: Any) -> ConclusionObserver:
        return classify_case(
            self.query, self.case_variable, self.conclusion_variable, case
        )

    def fit_case(self, case: Any, target: Any, expert: Expert) -> Any:
        """
        Ensure the RDR classifies ``case`` as ``target``, asking ``expert`` for the
        conditions of a new rule when it does not.

        :return: ``target``.
        """
        if self.query is None:
            self._add_first_rule(case, target, expert)
            return target

        observer = self._observe(case)
        if observer.conclusion == target:
            return target

        condition = expert.ask_for_conditions(
            case, observer.conclusion, target, self.case_variable
        )
        if observer.conclusion is None:
            # Nothing fired: attach an alternative at the conditions root.
            insert_alternative(
                self.query._conditions_root_,
                condition,
                self.conclusion_variable,
                target,
            )
        else:
            # A rule fired with the wrong value: refine it so the new condition overrides.
            insert_refinement(
                observer.fired[-1].anchor,
                condition,
                self.conclusion_variable,
                target,
            )
        return target

    def _add_first_rule(self, case: Any, target: Any, expert: Expert) -> None:
        condition = expert.ask_for_conditions(case, None, target, self.case_variable)
        self.query = entity(self.case_variable).where(condition)
        with self.query:
            add(self.conclusion_variable, target)
        self.query.build()

    def fit(
        self, cases: List[Any], targets: List[Any], expert: Expert
    ) -> "EQLSingleClassRDR":
        """Fit the RDR over parallel ``cases`` / ``targets`` lists."""
        for case, target in zip(cases, targets):
            self.fit_case(case, target, expert)
        return self

    @property
    def conditions_root(self) -> Optional[SymbolicExpression]:
        """The root of the rule tree's condition DAG, or ``None`` if empty."""
        return self.query._conditions_root_ if self.query is not None else None
