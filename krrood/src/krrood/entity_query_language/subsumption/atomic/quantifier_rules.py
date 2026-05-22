"""
Atomic subsumption rules for quantifier expressions (ForAll, Exists).

ForAllMonotonicityRule
    ForAll(x, P) ⊆ ForAll(x, Q)  if  P ⊆ Q  (both must quantify the same variable).

ExistsMonotonicityRule
    Exists(x, P) ⊆ Exists(x, Q)  if  P ⊆ Q  (both must quantify the same variable).

Both rules are based on the monotonicity of quantifiers: if the inner condition becomes
more restrictive (smaller extension), the quantified expression does too.

Deferred / unsupported (see Phase 3 notes):
    - ForAll(x, P) ⊆ Exists(x, P): valid under a non-empty domain assumption, but
      requires knowing the domain is non-empty at subsumption-check time.
    - Negated quantifier atoms (NOT ForAll / NOT Exists): quantifier duality unfolding
      (NOT ForAll(x, P) = Exists(x, NOT P)) is partially handled by the CNF converter
      via De Morgan on AND/OR, but NOT applied recursively into ForAll/Exists conditions.
      Full support deferred to Phase 3.
    - Cross-type quantifier subsumption (ForAll ⊆ Exists): deferred to Phase 3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from krrood.entity_query_language.operators.logical_quantifiers import Exists, ForAll
from krrood.entity_query_language.subsumption.normalization.cnf_types import CNFAtom

if TYPE_CHECKING:
    from krrood.entity_query_language.subsumption.engine import EQLSubsumptionEngine


class ForAllMonotonicityRule:
    """
    ForAll(x, P) ⊆ ForAll(x, Q)  iff  P ⊆ Q.

    Both atoms must be non-negated ForAll expressions quantifying the same variable.
    """

    def applies(self, atom_a: CNFAtom, atom_b: CNFAtom) -> bool:
        return (
            not atom_a.negated
            and not atom_b.negated
            and isinstance(atom_a.expression, ForAll)
            and isinstance(atom_b.expression, ForAll)
        )

    def check(
        self,
        atom_a: CNFAtom,
        atom_b: CNFAtom,
        engine: EQLSubsumptionEngine,
    ) -> Optional[bool]:
        fa: ForAll = atom_a.expression
        fb: ForAll = atom_b.expression
        if fa.variable._id_ != fb.variable._id_:
            return None  # different variables — cannot determine
        return engine.is_subsumed_by(fa.condition, fb.condition)


class ExistsMonotonicityRule:
    """
    Exists(x, P) ⊆ Exists(x, Q)  iff  P ⊆ Q.

    Both atoms must be non-negated Exists expressions quantifying the same variable.
    """

    def applies(self, atom_a: CNFAtom, atom_b: CNFAtom) -> bool:
        return (
            not atom_a.negated
            and not atom_b.negated
            and isinstance(atom_a.expression, Exists)
            and isinstance(atom_b.expression, Exists)
        )

    def check(
        self,
        atom_a: CNFAtom,
        atom_b: CNFAtom,
        engine: EQLSubsumptionEngine,
    ) -> Optional[bool]:
        ea: Exists = atom_a.expression
        eb: Exists = atom_b.expression
        if ea.variable._id_ != eb.variable._id_:
            return None  # different variables — cannot determine
        return engine.is_subsumed_by(ea.condition, eb.condition)
