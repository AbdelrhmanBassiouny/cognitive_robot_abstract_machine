"""
Immutable data structures representing a formula in Conjunctive Normal Form (CNF).

A CNF formula is a conjunction (AND) of clauses, where each clause is a disjunction (OR)
of atoms. An atom is an EQL expression treated as logically indivisible at the CNF level
(e.g., a Comparator, ForAll, Exists, or InstantiatedVariable / Predicate).

Subsumption check (A ⊆ B):
    A_cnf.is_subsumed_by(B_cnf, atom_subsumer, engine)

    For every clause D in B_cnf there must exist a clause C in A_cnf such that C ⊆ D.
    C ⊆ D means: for every atom L in C there exists an atom M in D with L ⊆ M atomically.

These types never create or mutate EQL expression nodes; they only hold references to them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, FrozenSet

from krrood.entity_query_language.core.base_expressions import SymbolicExpression

if TYPE_CHECKING:
    from krrood.entity_query_language.subsumption.atomic.atom_subsumer import AtomSubsumer
    from krrood.entity_query_language.subsumption.engine import EQLSubsumptionEngine


@dataclass(frozen=True)
class CNFAtom:
    """
    A single atom in a CNF formula — an EQL expression treated as logically indivisible,
    optionally negated.

    The ``negated`` flag tracks logical negation without creating a new ``Not()`` EQL node,
    which would corrupt the live expression graph.
    """

    expression: SymbolicExpression
    negated: bool = False

    def __hash__(self) -> int:
        return hash((self.expression._id_, self.negated))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CNFAtom):
            return NotImplemented
        return self.expression._id_ == other.expression._id_ and self.negated == other.negated

    def __repr__(self) -> str:
        prefix = "NOT " if self.negated else ""
        return f"CNFAtom({prefix}{self.expression!r})"


@dataclass(frozen=True)
class CNFClause:
    """
    A disjunction of atoms: L1 ∨ L2 ∨ … ∨ Ln.

    A unit clause (single atom) represents the atom itself.
    An empty clause represents ⊥ (unsatisfiable) — avoided in practice.
    """

    atoms: FrozenSet[CNFAtom] = field(default_factory=frozenset)

    def is_subsumed_by(
        self,
        other: CNFClause,
        atom_subsumer: AtomSubsumer,
        engine: EQLSubsumptionEngine,
    ) -> bool:
        """
        Return True if self ⊆ other as conditions (self is at least as restrictive as other).

        For every atom L in self there must be an atom M in other such that L ⊆ M atomically.
        A clause with fewer disjuncts is more restrictive, hence a subset of a wider clause.
        """
        return all(
            any(atom_subsumer.is_subsumed_by(l, m, engine) for m in other.atoms)
            for l in self.atoms
        )

    @classmethod
    def unit(cls, atom: CNFAtom) -> CNFClause:
        """Create a unit clause containing a single atom."""
        return cls(atoms=frozenset({atom}))

    def __repr__(self) -> str:
        return " ∨ ".join(repr(a) for a in self.atoms)


@dataclass(frozen=True)
class CNFFormula:
    """
    A conjunction of clauses: C1 ∧ C2 ∧ … ∧ Cn.

    An empty formula represents ⊤ (tautology — satisfied by everything).
    """

    clauses: FrozenSet[CNFClause] = field(default_factory=frozenset)

    def is_subsumed_by(
        self,
        other: CNFFormula,
        atom_subsumer: AtomSubsumer,
        engine: EQLSubsumptionEngine,
    ) -> bool:
        """
        Return True if self ⊆ other (self is at least as restrictive as other).

        For every clause D in other there must exist a clause C in self with C ⊆ D.
        A conjunction (more clauses) is more restrictive, so it covers fewer models.
        """
        if not other.clauses:
            return True  # other is ⊤; everything is a subset
        return all(
            any(c.is_subsumed_by(d, atom_subsumer, engine) for c in self.clauses)
            for d in other.clauses
        )

    @classmethod
    def unit(cls, atom: CNFAtom) -> CNFFormula:
        """Create a formula with a single unit clause containing one atom."""
        return cls(clauses=frozenset({CNFClause.unit(atom)}))

    def __repr__(self) -> str:
        return " ∧ ".join(f"({c!r})" for c in self.clauses)
