"""
EQLSubsumptionEngine — the main entry point for EQL subsumption checking.

Usage::

    from krrood.entity_query_language.subsumption import EQLSubsumptionEngine

    engine = EQLSubsumptionEngine.default()
    result = engine.is_subsumed_by(condition_a, condition_b)
    # True  →  every binding satisfying condition_a also satisfies condition_b
    # False →  subsumption could not be established (sound: never a false positive)

Algorithm (CNF-based subsumption):
    1. Convert both expressions to CNF via CNFConverter.
    2. Check A_cnf ⊆ B_cnf: for every clause D in B, some clause C in A satisfies C ⊆ D.
    3. Clause-level ⊆ delegates to AtomSubsumer for individual atom pairs.
    4. AtomSubsumer dispatches to registered AtomSubsumptionRules.

If CNF conversion exceeds the atom budget, CNFExplosionError is caught and False is returned
(sound: conservatively assumes no subsumption when the structure is too complex).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.subsumption.atomic.atom_subsumer import AtomSubsumer
from krrood.entity_query_language.subsumption.atomic.comparator_rules import (
    ComparatorOrderingRule,
    MembershipRule,
)
from krrood.entity_query_language.subsumption.atomic.quantifier_rules import (
    ExistsMonotonicityRule,
    ForAllMonotonicityRule,
)
from krrood.entity_query_language.subsumption.exceptions import CNFExplosionError
from krrood.entity_query_language.subsumption.normalization.cnf_converter import (
    CNFConverter,
)


@dataclass
class EQLSubsumptionEngine:
    """
    Checks whether EQL condition ``a`` is subsumed by EQL condition ``b``
    (i.e. ``a ⊆ b`` — every binding satisfying ``a`` also satisfies ``b``).

    Parameters
    ----------
    converter:
        CNFConverter instance used to normalise expressions.
    atom_subsumer:
        AtomSubsumer instance holding the registered atomic rules.
    """

    converter: CNFConverter = field(default_factory=CNFConverter)
    atom_subsumer: AtomSubsumer = field(default_factory=AtomSubsumer)

    def is_subsumed_by(
        self, a: SymbolicExpression, b: SymbolicExpression
    ) -> bool:
        """
        Return True iff condition ``a`` is subsumed by condition ``b`` (``a ⊆ b``).

        The check is *sound but incomplete*: True is never returned erroneously,
        but False may be returned when subsumption holds but cannot be derived
        syntactically (e.g. due to unsupported operators or complex nesting).
        """
        try:
            a_cnf = self.converter.to_cnf(a)
            b_cnf = self.converter.to_cnf(b)
        except CNFExplosionError:
            return False

        return a_cnf.is_subsumed_by(b_cnf, self.atom_subsumer, self)

    @classmethod
    def default(cls) -> EQLSubsumptionEngine:
        """
        Create an engine pre-configured with all Phase-1 rules.

        Rule priority (first applicable rule wins at the atom level):
        1. ComparatorOrderingRule  — interval-based ordered comparisons
        2. MembershipRule          — ``in_`` / ``contains`` set membership
        3. ForAllMonotonicityRule  — ForAll(x, P) ⊆ ForAll(x, Q) if P ⊆ Q
        4. ExistsMonotonicityRule  — Exists(x, P) ⊆ Exists(x, Q) if P ⊆ Q
        """
        atom_subsumer = AtomSubsumer(
            rules=[
                ComparatorOrderingRule(),
                MembershipRule(),
                ForAllMonotonicityRule(),
                ExistsMonotonicityRule(),
            ]
        )
        return cls(
            converter=CNFConverter(),
            atom_subsumer=atom_subsumer,
        )
