from __future__ import annotations

import datetime
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, TYPE_CHECKING

import inflect

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.verbalization.fragments.base import VerbFragment

_engine = inflect.engine()


class ArticleSelection(Enum):
    """
    Signal from :class:`VerbalizationContext` to the verbalizer: which article form to use.

    :cvar NONE: Numbered variable (e.g. ``Robot 1``) — no article prepended.
    :cvar DEFINITE: Subsequent mention of a single-typed variable → ``"the"``.
    :cvar INDEFINITE: First mention of a single-typed variable → ``"a"`` / ``"an"``.
    """

    NONE       = auto()  # numbered variable — no article
    DEFINITE   = auto()  # subsequent mention → "the"
    INDEFINITE = auto()  # first mention → "a" / "an"


def _article(type_name: str) -> str:
    return _engine.a(type_name).split()[0]


def _build_disambiguation_map(expr) -> Dict[uuid.UUID, str]:
    """
    Pre-scan *expr* and return a mapping of variable._id_ → display label.

    Types appearing once keep the plain type name; types appearing two or more
    times get "TypeName 1", "TypeName 2", … labels in encounter order.
    Literal nodes are excluded.
    """
    from krrood.entity_query_language.core.variable import Variable, Literal
    from krrood.entity_query_language.query.query import Query

    if isinstance(expr, Query):
        expr.build()

    type_to_ids: Dict[str, List[uuid.UUID]] = defaultdict(list)
    seen_ids: set = set()

    for node in expr._all_expressions_:
        if isinstance(node, Variable) and not isinstance(node, Literal):
            type_name = node._type_.__name__ if getattr(node, "_type_", None) else node.__class__.__name__
            if node._id_ not in seen_ids:
                seen_ids.add(node._id_)
                type_to_ids[type_name].append(node._id_)

    result: Dict[uuid.UUID, str] = {}
    for type_name, ids in type_to_ids.items():
        if len(ids) == 1:
            result[ids[0]] = type_name
        else:
            for n, vid in enumerate(ids, 1):
                result[vid] = f"{type_name} {n}"
    return result


@dataclass
class VerbalizationContext:
    """
    Carries per-verbalization state: coreference tracking, constraint deferral,
    and binding overrides.

    A single :class:`VerbalizationContext` instance is threaded through an entire
    :meth:`~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer.verbalize`
    call.  It ensures the same variable is rendered as ``"a Robot"`` on first
    mention and ``"the Robot"`` on every subsequent mention, and that
    :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`
    field-reference fragments are re-used instead of re-verbalized.

    Create via :meth:`from_expression` to pre-load the disambiguation map.

    :ivar seen: Maps expression ``_id_`` → display label for every expression
        already verbalized in this pass.
    :ivar compact_predicates: When ``True``, comparators omit the copula *"is"*
        (e.g. *"greater than"* instead of *"is greater than"*).  Set temporarily
        by :class:`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer`
        while rendering HAVING conditions.
    :ivar constraint_exprs: Stack of deferred-expression frames.  Each frame
        belongs to one nesting level of
        :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`
        verbalization.
    :ivar disambiguation_map: Maps variable ``_id_`` → display label,
        pre-computed before verbalization begins.  Single-type variables keep
        the plain type name; colliding types get ``"TypeName 1"``, ``"TypeName 2"`` labels.
    :ivar binding_overrides: Maps a child expression's ``_id_`` → a
        ``VerbFragment`` that substitutes for it on subsequent encounters.
        Populated by ``_verbalize_instantiated_natural`` and checked by
        :meth:`~krrood.entity_query_language.verbalization.rule_engine.RuleEngine.build`
        before any rule dispatches.
    """

    seen: dict = field(default_factory=dict)
    compact_predicates: bool = False
    constraint_exprs: List[List["SymbolicExpression"]] = field(default_factory=list)
    disambiguation_map: Dict[uuid.UUID, str] = field(default_factory=dict)
    binding_overrides: Dict[uuid.UUID, "VerbFragment"] = field(default_factory=dict)

    @classmethod
    def from_expression(cls, expr) -> "VerbalizationContext":
        """
        Create a context pre-loaded with a disambiguation map for *expr*.

        Scans the full expression tree to determine which variable type names
        appear more than once, then assigns numbered labels (``"TypeName 1"``,
        ``"TypeName 2"``, …) to disambiguate them.

        :param expr: Root EQL expression or
            :class:`~krrood.entity_query_language.query.query.Query` to scan.
        :returns: A fresh :class:`VerbalizationContext` with :attr:`disambiguation_map` populated.
        :rtype: VerbalizationContext
        """
        return cls(disambiguation_map=_build_disambiguation_map(expr))

    def push_constraint_frame(self) -> None:
        """
        Open a new constraint frame for the current
        :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`.

        All expressions passed to :meth:`defer_constraint` until the matching
        :meth:`pop_constraint_frame` are collected in this frame.
        """
        self.constraint_exprs.append([])

    def pop_constraint_frame(self) -> "List[SymbolicExpression]":
        """
        Close the current frame and return its deferred expressions.

        Returns an empty list when no frame is open (defensive behaviour; should
        not occur in well-formed verbalization calls).

        :returns: Deferred expressions from the closed frame, in deferral order.
        :rtype: list
        """
        return self.constraint_exprs.pop() if self.constraint_exprs else []

    def defer_constraint(self, expr: "SymbolicExpression") -> None:
        """
        Defer *expr* into the top constraint frame.

        No-op when no frame is open (i.e. when verbalization is not currently
        inside an :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`
        rendering pass).

        :param expr: EQL expression to defer.
        :type expr: ~krrood.entity_query_language.core.base_expressions.SymbolicExpression
        """
        if self.constraint_exprs:
            self.constraint_exprs[-1].append(expr)

    def noun_for_parts(self, var) -> "tuple[ArticleSelection, str]":
        """
        Return ``(ArticleSelection, label)`` for *var*.

        Consults :attr:`disambiguation_map` to determine the display label, then
        :attr:`seen` to determine first vs. subsequent mention.

        * :attr:`~ArticleSelection.NONE` — numbered variable (``"Robot 1"``); no article.
        * :attr:`~ArticleSelection.DEFINITE` — subsequent mention → ``"the"``.
        * :attr:`~ArticleSelection.INDEFINITE` — first mention → ``"a"`` / ``"an"``.

        :param var: A :class:`~krrood.entity_query_language.core.variable.Variable` instance.
        :returns: Tuple of ``(ArticleSelection, display_label)``.
        :rtype: tuple
        """
        type_name = var._type_.__name__ if getattr(var, "_type_", None) else var.__class__.__name__
        label = self.disambiguation_map.get(var._id_, type_name)
        is_numbered = label != type_name
        if var._id_ in self.seen:
            return (ArticleSelection.NONE if is_numbered else ArticleSelection.DEFINITE), label
        self.seen[var._id_] = label
        return (ArticleSelection.NONE if is_numbered else ArticleSelection.INDEFINITE), label

    def flatten_same_type(self, expr, operator_type) -> List:
        """
        Recursively flatten a homogeneous binary chain into a flat list.

        For example, ``AND(AND(a, b), c)`` with ``operator_type=AND`` yields
        ``[a, b, c]``.  Non-matching nodes are returned as a single-element list.

        :param expr: Root of the expression tree to flatten.
        :param operator_type: The binary operator class whose chains to flatten
            (e.g. :class:`~krrood.entity_query_language.operators.core_logical_operators.AND`).
        :returns: Flat list of operand expressions.
        :rtype: list
        """
        if not isinstance(expr, operator_type):
            return [expr]
        left = self.flatten_same_type(expr.left, operator_type)
        right = self.flatten_same_type(expr.right, operator_type)
        return left + right

    def type_name_of_value(self, value: Any) -> str:
        """
        Render a Python value as a human-readable string.

        Conversion rules:

        * A bare ``type`` object → its ``__name__`` (e.g. ``Apple`` → ``"Apple"``).
        * A tuple of ``type`` objects → ``"A or B or C"``.
        * A :class:`datetime.datetime` with no time component → ``"May 23, 2026"``.
        * A :class:`datetime.datetime` with a time component → ``"May 23, 2026 at 14:30"``.
        * Anything else → ``repr(value)``.

        :param value: Python value from a
            :class:`~krrood.entity_query_language.core.variable.Literal` node.
        :returns: Human-readable string representation.
        :rtype: str
        """
        if isinstance(value, type):
            return value.__name__
        if isinstance(value, tuple) and all(isinstance(v, type) for v in value):
            return " or ".join(v.__name__ for v in value)
        if isinstance(value, datetime.datetime):
            if value.time() == datetime.time.min:
                return value.strftime("%B %-d, %Y")
            return value.strftime("%B %-d, %Y at %H:%M")
        return repr(value)
