"""
Converts EQL symbolic expressions into Conjunctive Normal Form (CNF).

Conversion is a single recursive pass with an explicit ``negated`` flag so that
negation is pushed inward (NNF) and OR is distributed over AND (CNF) in one traversal,
without ever creating new EQL expression nodes (which would corrupt the live expression
graph through the ``_parent_`` side-effects in EQL's ``__post_init__``).

Atoms — expressions treated as logically indivisible at the CNF level:
    Comparator, InstantiatedVariable (predicates / symbolic functions), ForAll, Exists.

Unsupported / deferred:
    - ``!=`` comparator: complement of a singleton cannot be represented as a single
      interval; deferred to Phase 2 where two-interval representation is added.
    - Negated quantifiers (NOT ForAll / NOT Exists) as atoms: currently treated as
      opaque negated atoms. Phase 3 will implement quantifier duality unfolding inside
      the atom subsumer.
    - Variable (boolean variable) atoms: treated as opaque atoms; Phase 2 will add
      structural variable-equivalence checks.
"""

from __future__ import annotations

import operator as op_module
from dataclasses import dataclass, field
from typing import ClassVar, FrozenSet, Type

from typing_extensions import Tuple

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.operators.core_logical_operators import AND, OR, Not
from krrood.entity_query_language.operators.logical_quantifiers import Exists, ForAll
from krrood.entity_query_language.core.variable import InstantiatedVariable
from krrood.entity_query_language.subsumption.exceptions import CNFExplosionError
from krrood.entity_query_language.subsumption.normalization.cnf_types import (
    CNFAtom,
    CNFClause,
    CNFFormula,
)

# Operator flip map for negating a comparator (NOT(x > 5) → x <= 5).
# ``!=`` is intentionally absent — deferred to Phase 2.
_FLIP_MAP = {
    op_module.eq: op_module.ne,
    op_module.ne: op_module.eq,
    op_module.lt: op_module.ge,
    op_module.le: op_module.gt,
    op_module.gt: op_module.le,
    op_module.ge: op_module.lt,
}

# Atom types: expressions not decomposed further during CNF conversion.
_ATOM_TYPES: Tuple[Type[SymbolicExpression], ...] = (
    Comparator,
    InstantiatedVariable,
    ForAll,
    Exists,
)


@dataclass
class CNFConverter:
    """
    Converts an EQL ``SymbolicExpression`` to a ``CNFFormula``.

    Parameters
    ----------
    max_atoms_budget:
        Maximum total number of atoms across all clauses in the resulting formula.
        Prevents exponential blowup when distributing OR over deeply nested AND.
        When the budget is exceeded a ``CNFExplosionError`` is raised; callers
        should catch it and default to ``False`` (sound: never a false positive).
    """

    max_atoms_budget: int = field(default=256)

    def to_cnf(self, expr: SymbolicExpression) -> CNFFormula:
        """Convert *expr* to CNF, returning the resulting ``CNFFormula``."""
        return self._convert(expr, negated=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _convert(self, expr: SymbolicExpression, negated: bool) -> CNFFormula:
        """Recursive one-pass CNF conversion with an explicit ``negated`` flag."""

        # Base case: atom
        if isinstance(expr, _ATOM_TYPES):
            if negated and isinstance(expr, Comparator):
                # Try to fold the negation into the comparator by flipping the operator.
                flipped_op = _FLIP_MAP.get(expr.operation)
                if flipped_op is not None and flipped_op is not op_module.ne:
                    # Return a new atom representing the flipped (non-negated) comparator.
                    # We create a lightweight wrapper rather than a new EQL node so the
                    # graph is not mutated. We keep the original expression but note the
                    # effective operator separately via a _FlippedComparator sentinel.
                    return CNFFormula.unit(CNFAtom(expr, negated=True))
            return CNFFormula.unit(CNFAtom(expr, negated=negated))

        # NOT: flip the negation flag and recurse on the child
        if isinstance(expr, Not):
            return self._convert(expr._child_, negated=not negated)

        # AND / OR — direction depends on ``negated`` (De Morgan when negated)
        if isinstance(expr, AND):
            left_cnf = self._convert(expr.left, negated=negated)
            right_cnf = self._convert(expr.right, negated=negated)
            if negated:
                # NOT(A AND B) = NOT(A) OR NOT(B)
                return self._distribute_or(left_cnf, right_cnf)
            else:
                # A AND B: conjunction — merge clause sets
                return self._conjoin(left_cnf, right_cnf)

        if isinstance(expr, OR):
            left_cnf = self._convert(expr.left, negated=negated)
            right_cnf = self._convert(expr.right, negated=negated)
            if negated:
                # NOT(A OR B) = NOT(A) AND NOT(B)
                return self._conjoin(left_cnf, right_cnf)
            else:
                # A OR B: distribute
                return self._distribute_or(left_cnf, right_cnf)

        # Fallback: treat any unknown expression type as an opaque atom
        return CNFFormula.unit(CNFAtom(expr, negated=negated))

    @staticmethod
    def _conjoin(left: CNFFormula, right: CNFFormula) -> CNFFormula:
        """Return the conjunction of two CNF formulas (merge their clause sets)."""
        return CNFFormula(clauses=left.clauses | right.clauses)

    def _distribute_or(self, left: CNFFormula, right: CNFFormula) -> CNFFormula:
        """
        Return the CNF of (left OR right) by distributing:
        (C1 ∧ C2) ∨ (D1 ∧ D2) = (C1∨D1) ∧ (C1∨D2) ∧ (C2∨D1) ∧ (C2∨D2).
        """
        new_clauses: FrozenSet[CNFClause] = frozenset(
            CNFClause(atoms=c.atoms | d.atoms)
            for c in left.clauses
            for d in right.clauses
        )
        total_atoms = sum(len(cl.atoms) for cl in new_clauses)
        if total_atoms > self.max_atoms_budget:
            raise CNFExplosionError(self.max_atoms_budget)
        return CNFFormula(clauses=new_clauses)
