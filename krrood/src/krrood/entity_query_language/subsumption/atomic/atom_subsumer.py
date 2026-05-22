"""
AtomSubsumer — dispatches atomic-level subsumption checks to registered rules.

Reflexivity (same expression object) is checked first as a fast path.
Rules are tried in registration order; the first non-None result wins.
If no rule matches, the subsumption is unknown and False is returned (sound).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from krrood.entity_query_language.subsumption.normalization.cnf_types import CNFAtom

if TYPE_CHECKING:
    from krrood.entity_query_language.subsumption.engine import EQLSubsumptionEngine


class AtomSubsumptionRule:
    """
    Abstract interface for a single atomic subsumption rule.

    A rule inspects a pair of ``CNFAtom`` objects and returns:
    - ``True``  if  atom_a ⊆ atom_b  can be positively determined,
    - ``False`` if  atom_a ⊄ atom_b  can be positively determined,
    - ``None``  if  the rule does not apply or the result is undetermined.
    """

    def applies(self, atom_a: CNFAtom, atom_b: CNFAtom) -> bool:
        raise NotImplementedError

    def check(
        self,
        atom_a: CNFAtom,
        atom_b: CNFAtom,
        engine: EQLSubsumptionEngine,
    ) -> Optional[bool]:
        raise NotImplementedError


@dataclass
class AtomSubsumer:
    """
    Dispatches atomic subsumption checks to a prioritised list of rules.

    Usage::

        subsumer = AtomSubsumer(rules=[ComparatorOrderingRule(), MembershipRule(), ...])
        result = subsumer.is_subsumed_by(atom_a, atom_b, engine)
    """

    rules: List[AtomSubsumptionRule] = field(default_factory=list)

    def is_subsumed_by(
        self,
        atom_a: CNFAtom,
        atom_b: CNFAtom,
        engine: EQLSubsumptionEngine,
    ) -> bool:
        """
        Return True iff atom_a ⊆ atom_b.

        Reflexivity fast-path: if both atoms reference the same expression object
        with the same negation flag, the result is immediately True.
        """
        if (
            atom_a.expression._id_ == atom_b.expression._id_
            and atom_a.negated == atom_b.negated
        ):
            return True

        for rule in self.rules:
            if rule.applies(atom_a, atom_b):
                result = rule.check(atom_a, atom_b, engine)
                if result is not None:
                    return result

        return False  # no rule could determine subsumption — default to False (sound)
