"""
EQL Subsumption — checks whether one EQL condition is a subset of another.

Public API::

    from krrood.entity_query_language.subsumption import EQLSubsumptionEngine

    engine = EQLSubsumptionEngine.default()
    engine.is_subsumed_by(a, b)   # True iff every binding satisfying a also satisfies b

Semantics
---------
``a ⊆ b`` (read "a is subsumed by b") means that condition ``a`` is *more restrictive*
than condition ``b``: its extension (the set of bindings it accepts) is a subset of
the extension of ``b``.  This mirrors Description Logic's ``a ⊑ b``.

Algorithm
---------
Both expressions are normalised to Conjunctive Normal Form (CNF) — a conjunction of
disjunctions of atomic expressions.  Subsumption is then reduced to:

    A ⊆ B  iff  for every clause D in B_cnf,
                some clause C in A_cnf satisfies C ⊆ D
                (i.e. every atom in C is atomically subsumed by some atom in D).

Supported in Phase 1
--------------------
- Ordered comparisons (==, <, <=, >, >=) against literal constants — interval model.
- Membership (``in_`` / ``contains``) against literal collections — set containment.
- Logical connectives (AND, OR, NOT) — handled via CNF normalisation.
- Universal quantifier (ForAll) — monotonicity rule.
- Existential quantifier (Exists) — monotonicity rule.

Deferred to future phases
--------------------------
- ``!=`` comparator (two-interval complement representation).
- Predicate / type-hierarchy subsumption (``HasType(x, Dog) ⊆ HasType(x, Animal)``).
- Structural variable matching (different variable instances of the same type).
- ForAll ⊆ Exists under non-empty domain assumption.
"""

from krrood.entity_query_language.subsumption.engine import EQLSubsumptionEngine
from krrood.entity_query_language.subsumption.exceptions import CNFExplosionError

__all__ = ["EQLSubsumptionEngine", "CNFExplosionError"]
