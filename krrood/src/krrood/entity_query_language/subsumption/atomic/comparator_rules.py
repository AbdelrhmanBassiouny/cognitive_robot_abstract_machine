"""
Atomic subsumption rules for ``Comparator`` expressions.

Two rules are implemented:

ComparatorOrderingRule
    Handles ordered comparisons (==, <, <=, >, >=) where one operand is a Variable
    and the other is a Literal constant. Subsumption is checked via interval containment
    on the real-number line (or any totally ordered domain).

MembershipRule
    Handles the ``in_`` / ``contains`` membership comparator (operator.contains) where
    the right operand is a Variable and the left operand is a Literal collection.
    Subsumption is S1 ⊆ S2 (set containment) or {value} ⊆ S (element membership).

Deferred / unsupported (see Phase 2 notes):
    - ``!=`` comparator: the complement of a singleton cannot be expressed as a single
      closed interval; deferred to Phase 2. Negated comparators of other types (handled
      by flipping the operator in the atom's ``negated`` flag) are supported.
    - Variable-to-variable comparisons (x == y): both operands are Variables; no interval
      can be derived without domain knowledge.  Treated as not subsumed (returns False).
    - ``not_contains`` (item not in container): treated as not subsumed in Phase 1.
"""

from __future__ import annotations

import operator as op_module
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Tuple

from krrood.entity_query_language.core.variable import Literal, Variable
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.subsumption.normalization.cnf_types import CNFAtom

if TYPE_CHECKING:
    from krrood.entity_query_language.subsumption.engine import EQLSubsumptionEngine

# ---------------------------------------------------------------------------
# Operator → interval endpoint configuration
# ---------------------------------------------------------------------------

# (lower_bound, lower_inclusive, upper_bound, upper_inclusive)
# None means unbounded (−∞ or +∞).
# The literal value is inserted in place of the placeholder (True/False/None).
#
# Convention: the Variable is on the LEFT side (x op literal).
# If the Variable is on the RIGHT side (literal op x) the operator is swapped via
# _REVERSE_OP_MAP before lookup.
_OP_TO_INTERVAL = {
    op_module.gt: ("literal", False, None, True),   # x > a  → (a, +∞)
    op_module.ge: ("literal", True, None, True),    # x >= a → [a, +∞)
    op_module.lt: (None, True, "literal", False),   # x < a  → (-∞, a)
    op_module.le: (None, True, "literal", True),    # x <= a → (-∞, a]
    op_module.eq: ("literal", True, "literal", True),  # x == a → [a, a]
}

# When the literal is on the LEFT (literal op variable), swap the relational direction.
_REVERSE_OP_MAP = {
    op_module.lt: op_module.gt,
    op_module.le: op_module.ge,
    op_module.gt: op_module.lt,
    op_module.ge: op_module.le,
    op_module.eq: op_module.eq,
}

# Flip map: operator to use when the CNFAtom has ``negated=True``.
# ``ne`` is absent — deferred to Phase 2.
_FLIP_MAP = {
    op_module.gt: op_module.le,
    op_module.ge: op_module.lt,
    op_module.lt: op_module.ge,
    op_module.le: op_module.gt,
    op_module.eq: op_module.ne,   # results in ``ne`` → returns None below (deferred)
}


# ---------------------------------------------------------------------------
# Interval helper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Interval:
    """
    A closed/open interval on an ordered domain.

    ``None`` for ``lower`` means −∞; ``None`` for ``upper`` means +∞.
    """

    lower: Optional[Any]
    lower_inclusive: bool
    upper: Optional[Any]
    upper_inclusive: bool

    def is_subset_of(self, other: _Interval) -> bool:
        """Return True iff every value in *self* is also in *other*."""
        try:
            return self._lower_ok(other) and self._upper_ok(other)
        except TypeError:
            # Incomparable types (e.g. mixing str and int) → cannot determine
            return False

    def _lower_ok(self, other: _Interval) -> bool:
        if other.lower is None:
            return True
        if self.lower is None:
            return False
        if self.lower > other.lower:
            return True
        if self.lower == other.lower:
            # self's lower bound is the same as other's.
            # self ⊆ other at the lower end iff other accepts self's boundary.
            # [x, …) ⊆ [x, …) ✓, (x, …) ⊆ [x, …) ✓, [x, …) ⊆ (x, …) ✗
            return other.lower_inclusive or not self.lower_inclusive
        return False  # self.lower < other.lower → self extends further left

    def _upper_ok(self, other: _Interval) -> bool:
        if other.upper is None:
            return True
        if self.upper is None:
            return False
        if self.upper < other.upper:
            return True
        if self.upper == other.upper:
            return other.upper_inclusive or not self.upper_inclusive
        return False  # self.upper > other.upper → self extends further right


# ---------------------------------------------------------------------------
# Shared extraction helper
# ---------------------------------------------------------------------------

def _extract_var_and_literal(
    comparator: Comparator,
) -> Optional[Tuple[Variable, Any, bool]]:
    """
    Return ``(variable, literal_value, var_is_left)`` if exactly one side is a
    non-Literal Variable and the other is a Literal, else ``None``.

    ``var_is_left=True`` means the variable is on the left: ``variable op literal``.
    ``var_is_left=False`` means the variable is on the right: ``literal op variable``.
    """
    left, right = comparator.left, comparator.right
    left_is_lit = isinstance(left, Literal)
    right_is_lit = isinstance(right, Literal)
    left_is_var = isinstance(left, Variable) and not left_is_lit
    right_is_var = isinstance(right, Variable) and not right_is_lit

    if left_is_var and right_is_lit:
        return left, right._value_, True
    if left_is_lit and right_is_var:
        return right, left._value_, False
    return None


def _get_interval(atom: CNFAtom) -> Optional[Tuple[Variable, _Interval]]:
    """
    Derive the variable and effective interval for an ordering ``CNFAtom``.

    Returns ``None`` when the atom is not a supported ordering comparator.
    """
    if not isinstance(atom.expression, Comparator):
        return None

    comparator = atom.expression
    extracted = _extract_var_and_literal(comparator)
    if extracted is None:
        return None

    variable, literal_value, var_is_left = extracted
    effective_op = comparator.operation

    if not var_is_left:
        # literal op variable → swap direction (e.g. 3 < x means x > 3)
        effective_op = _REVERSE_OP_MAP.get(effective_op)
        if effective_op is None:
            return None

    if atom.negated:
        # Fold NOT into the operator (e.g. NOT(x > 5) → x <= 5)
        effective_op = _FLIP_MAP.get(effective_op)
        if effective_op is None:
            return None  # e.g. NOT(x == 5) → x != 5, deferred

    # ``ne`` (!=) is not representable as a single interval — deferred to Phase 2.
    if effective_op is op_module.ne:
        return None

    interval_spec = _OP_TO_INTERVAL.get(effective_op)
    if interval_spec is None:
        return None

    lower_raw, lower_inc, upper_raw, upper_inc = interval_spec
    lower = literal_value if lower_raw == "literal" else None
    upper = literal_value if upper_raw == "literal" else None
    return variable, _Interval(lower, lower_inc, upper, upper_inc)


# ---------------------------------------------------------------------------
# ComparatorOrderingRule
# ---------------------------------------------------------------------------

class ComparatorOrderingRule:
    """
    Checks subsumption for ordered comparison atoms sharing the same variable.

    Applies when both atoms are Comparators with the same variable on one side and
    a Literal constant on the other, using a supported ordering operator.

    ``atom_a ⊆ atom_b`` iff ``interval(atom_a) ⊆ interval(atom_b)``.
    """

    def applies(self, atom_a: CNFAtom, atom_b: CNFAtom) -> bool:
        return (
            isinstance(atom_a.expression, Comparator)
            and isinstance(atom_b.expression, Comparator)
            and atom_a.expression.operation is not op_module.contains
            and atom_b.expression.operation is not op_module.contains
        )

    def check(
        self,
        atom_a: CNFAtom,
        atom_b: CNFAtom,
        engine: EQLSubsumptionEngine,  # noqa: ARG002 — not needed for interval checks
    ) -> Optional[bool]:
        """Return True/False if rule applies, None if undetermined."""
        iv_a = _get_interval(atom_a)
        iv_b = _get_interval(atom_b)
        if iv_a is None or iv_b is None:
            return None
        var_a, interval_a = iv_a
        var_b, interval_b = iv_b
        if var_a._id_ != var_b._id_:
            return None  # different variables — cannot determine
        return interval_a.is_subset_of(interval_b)


# ---------------------------------------------------------------------------
# MembershipRule
# ---------------------------------------------------------------------------

class MembershipRule:
    """
    Checks subsumption for ``in_`` / ``contains`` membership atoms.

    Applies when:
      - Both atoms use ``operator.contains`` with a Variable on the right and a Literal
        collection on the left, sharing the same variable (``x in S1 ⊆ x in S2``).
      - One atom is an ordering ``==`` comparator and the other is a membership comparator
        with the same variable (``x == a ⊆ x in S``).

    Deferred: ``not_contains`` and negated membership atoms are not handled in Phase 1.
    """

    def applies(self, atom_a: CNFAtom, atom_b: CNFAtom) -> bool:
        a_is_mem = self._is_membership(atom_a)
        b_is_mem = self._is_membership(atom_b)
        a_is_eq = self._is_equality(atom_a)
        return (a_is_mem and b_is_mem) or (a_is_eq and b_is_mem)

    @staticmethod
    def _is_membership(atom: CNFAtom) -> bool:
        if atom.negated:
            return False
        c = atom.expression
        return (
            isinstance(c, Comparator)
            and c.operation is op_module.contains
            and isinstance(c.right, Variable)
            and not isinstance(c.right, Literal)
            and isinstance(c.left, Literal)
        )

    @staticmethod
    def _is_equality(atom: CNFAtom) -> bool:
        iv = _get_interval(atom)
        if iv is None:
            return False
        _, interval = iv
        # Equality interval: lower == upper, both inclusive
        return (
            interval.lower is not None
            and interval.upper is not None
            and interval.lower == interval.upper
            and interval.lower_inclusive
            and interval.upper_inclusive
        )

    def check(
        self,
        atom_a: CNFAtom,
        atom_b: CNFAtom,
        engine: EQLSubsumptionEngine,  # noqa: ARG002
    ) -> Optional[bool]:
        a_is_mem = self._is_membership(atom_a)
        b_is_mem = self._is_membership(atom_b)

        if a_is_mem and b_is_mem:
            return self._check_mem_subset_mem(atom_a, atom_b)
        if b_is_mem:
            return self._check_eq_subset_mem(atom_a, atom_b)
        return None

    @staticmethod
    def _check_mem_subset_mem(atom_a: CNFAtom, atom_b: CNFAtom) -> Optional[bool]:
        """x in S1 ⊆ x in S2 iff S1 ⊆ S2."""
        ca, cb = atom_a.expression, atom_b.expression
        if ca.right._id_ != cb.right._id_:
            return None  # different variables
        try:
            s1 = set(ca.left._value_)
            s2 = set(cb.left._value_)
            return s1.issubset(s2)
        except TypeError:
            return None

    @staticmethod
    def _check_eq_subset_mem(atom_a: CNFAtom, atom_b: CNFAtom) -> Optional[bool]:
        """x == a ⊆ x in S iff a ∈ S."""
        iv_a = _get_interval(atom_a)
        if iv_a is None:
            return None
        var_a, interval_a = iv_a
        cb = atom_b.expression
        if var_a._id_ != cb.right._id_:
            return None
        try:
            return interval_a.lower in set(cb.left._value_)
        except TypeError:
            return None
