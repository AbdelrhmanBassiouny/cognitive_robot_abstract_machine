"""
Rule structure analysis for EQL verbalization.

Classifies the parts of an Entity-over-inference query into antecedents (IF) and
a consequent (THEN) so the verbalizer can produce the "If ..., then ..." form.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, FrozenSet, Optional, Tuple, Any

import inflect

_engine = inflect.engine()


class AggregationStatus(Enum):
    GROUP_KEY = auto()   # this expression is one of the grouped_by keys
    AGGREGATED = auto()  # present but not a group key → plural in output
    NONE = auto()        # no grouping context


@dataclass
class AntecedentInfo:
    """One antecedent variable in the IF clause."""
    root: Any                      # Variable or Entity (unwrapped from ResultQuantifier)
    type_name: str
    aggregation_status: AggregationStatus
    conditions: List[Any] = field(default_factory=list)
    """All conditions attributed to this antecedent (own WHERE clause + matched outer WHERE)."""


@dataclass
class ConsequentBinding:
    """One field binding in the THEN clause."""
    field_name: str
    value_expr: Any                # SymbolicExpression
    is_plural_field: bool
    aggregation_status: AggregationStatus


@dataclass
class RuleStructure:
    primary_antecedents: List[AntecedentInfo]    # have conditions → appear in IF clause
    secondary_antecedents: List[AntecedentInfo]  # no conditions → only register in ctx.seen
    consequent_type: str
    consequent_bindings: List[ConsequentBinding]
    unmatched_conditions: List[Any]              # outer WHERE not attributable to any antecedent
    group_key_ids: FrozenSet[uuid.UUID]


# ── Module-level helpers (pure domain-analysis utilities) ─────────────────────

def _antecedent_var_id_(ant: AntecedentInfo) -> Optional[object]:
    """Return the stable _id_ of the underlying variable for an antecedent."""
    from krrood.entity_query_language.query.query import Entity as _Entity
    root = ant.root
    if isinstance(root, _Entity):
        root.build()
        sel = root.selected_variable
        return getattr(sel, "_id_", None)
    return getattr(root, "_id_", None)


def _condition_left_owner_id_(cond) -> Optional[object]:
    """
    Return the _id_ of the root variable on the left-hand side of an equality condition,
    or None if the condition is not a simple attribute equality.
    """
    from krrood.entity_query_language.operators.comparator import Comparator
    from krrood.entity_query_language.core.mapped_variable import MappedVariable
    from krrood.entity_query_language.query.quantifiers import ResultQuantifier
    import operator as _op

    if not isinstance(cond, Comparator) or cond.operation is not _op.eq:
        return None
    current = cond.left
    while isinstance(current, MappedVariable):
        current = current._child_
    while isinstance(current, ResultQuantifier):
        current = current._child_
    return getattr(current, "_id_", None)


class RuleAnalyzer:
    """Analyses an Entity-over-inference query and returns a RuleStructure."""

    def can_handle(self, entity) -> bool:
        from krrood.entity_query_language.core.variable import InstantiatedVariable
        entity.build()
        return isinstance(entity.selected_variable, InstantiatedVariable)

    def analyze(self, entity) -> RuleStructure:
        from krrood.entity_query_language.core.variable import InstantiatedVariable

        entity.build()
        inferred: InstantiatedVariable = entity.selected_variable
        type_name = getattr(inferred._type_, "__name__", str(inferred._type_))

        # ── Group-key IDs ──────────────────────────────────────────────────────
        grouped_expr = entity._grouped_by_expression_
        group_key_ids: FrozenSet[uuid.UUID] = frozenset()
        if grouped_expr is not None and grouped_expr.variables_to_group_by:
            group_key_ids = frozenset(v._id_ for v in grouped_expr.variables_to_group_by)
        has_grouping = bool(group_key_ids)

        # ── Walk consequent bindings ───────────────────────────────────────────
        seen_root_ids: dict = {}          # root_id → AntecedentInfo
        consequent_bindings: List[ConsequentBinding] = []

        for field_name, child_expr in inferred._child_vars_.items():
            is_plural = bool(_engine.singular_noun(field_name))

            if child_expr._id_ in group_key_ids:
                binding_agg = AggregationStatus.GROUP_KEY
            elif has_grouping:
                binding_agg = AggregationStatus.AGGREGATED
            else:
                binding_agg = AggregationStatus.NONE

            consequent_bindings.append(ConsequentBinding(
                field_name=field_name,
                value_expr=child_expr,
                is_plural_field=is_plural,
                aggregation_status=binding_agg,
            ))

            root = self._find_root(child_expr)
            if root is None or root._id_ in seen_root_ids:
                continue

            root_type_name, own_conditions = self._extract_root_info(root)

            if root._id_ in group_key_ids:
                var_agg = AggregationStatus.GROUP_KEY
            elif has_grouping:
                var_agg = AggregationStatus.AGGREGATED
            else:
                var_agg = AggregationStatus.NONE

            seen_root_ids[root._id_] = AntecedentInfo(
                root=root,
                type_name=root_type_name,
                aggregation_status=var_agg,
                conditions=own_conditions,
            )

        # ── Attribute outer WHERE conditions to antecedents ────────────────────
        where_expr = entity._where_expression_
        extra: List[Any] = []
        if where_expr is not None:
            extra = self._flatten_and(where_expr.condition)

        primary, secondary, unmatched = self._attribute_conditions_(
            list(seen_root_ids.values()), extra
        )

        return RuleStructure(
            primary_antecedents=primary,
            secondary_antecedents=secondary,
            consequent_type=type_name,
            consequent_bindings=consequent_bindings,
            unmatched_conditions=unmatched,
            group_key_ids=group_key_ids,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _attribute_conditions_(
        antecedents: List[AntecedentInfo],
        extra_conditions: List[Any],
    ) -> Tuple[List[AntecedentInfo], List[AntecedentInfo], List[Any]]:
        """
        Distribute extra outer-WHERE conditions to their owning antecedents,
        then classify antecedents as primary (have conditions) or secondary (none).
        Returns (primary, secondary, unmatched).
        """
        id_to_ant = {_antecedent_var_id_(a): a for a in antecedents}
        unmatched: List[Any] = []

        for cond in extra_conditions:
            owner_id = _condition_left_owner_id_(cond)
            if owner_id is not None and owner_id in id_to_ant:
                id_to_ant[owner_id].conditions.append(cond)
            else:
                unmatched.append(cond)

        primary = [a for a in antecedents if a.conditions]
        secondary = [a for a in antecedents if not a.conditions]
        return primary, secondary, unmatched

    @staticmethod
    def _find_root(expr) -> Optional[Any]:
        from krrood.entity_query_language.core.mapped_variable import MappedVariable
        from krrood.entity_query_language.core.variable import Variable
        from krrood.entity_query_language.query.quantifiers import ResultQuantifier
        from krrood.entity_query_language.query.query import Entity

        current = expr
        while isinstance(current, MappedVariable):
            current = current._child_
        while isinstance(current, ResultQuantifier):
            current = current._child_
        if isinstance(current, (Variable, Entity)):
            return current
        return None

    @staticmethod
    def _extract_root_info(root) -> Tuple[str, List[Any]]:
        """Return (type_name, own_conditions) for a root Variable or Entity."""
        from krrood.entity_query_language.core.variable import Variable
        from krrood.entity_query_language.query.query import Entity

        if isinstance(root, Entity):
            root.build()
            var = root.selected_variable
            type_name = var._type_.__name__ if var and getattr(var, "_type_", None) else "entity"
            conditions = []
            if root._where_expression_ is not None:
                conditions = RuleAnalyzer._flatten_and(root._where_expression_.condition)
            return type_name, conditions

        if isinstance(root, Variable):
            type_name = root._type_.__name__ if getattr(root, "_type_", None) else "variable"
            return type_name, []

        return "entity", []

    @staticmethod
    def _flatten_and(expr) -> List[Any]:
        from krrood.entity_query_language.operators.core_logical_operators import AND
        if isinstance(expr, AND):
            return RuleAnalyzer._flatten_and(expr.left) + RuleAnalyzer._flatten_and(expr.right)
        return [expr]
