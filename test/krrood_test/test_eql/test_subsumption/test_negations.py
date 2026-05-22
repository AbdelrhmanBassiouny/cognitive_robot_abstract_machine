"""
Level 5 — NOT (negation) subsumption.

NOT is handled by the CNF converter via negation propagation:
  NOT(x > 5)  →  atom(x > 5, negated=True)  →  effective interval (-∞, 5]
  NOT(A AND B)  →  NOT(A) OR NOT(B)  (De Morgan via CNF distribution)
  NOT(A OR B)   →  NOT(A) AND NOT(B)  (De Morgan via CNF conjunction)

Contrapositive:
  NOT(A) ⊆ NOT(B)  iff  B ⊆ A

Specific cases:
  NOT(x > 5) ⊆ NOT(x > 7)   — because x > 7 ⊆ x > 5 (contrapositive holds)
  NOT(x > 7) ⊄ NOT(x > 5)   — because x > 5 ⊄ x > 7

Negated interval checks:
  NOT(x > 5) effective interval (-∞, 5] ⊆ NOT(x > 3) effective (-∞, 3]? NO
  NOT(x > 5) ⊆ NOT(x > 7) because (-∞, 5] ⊆ (-∞, 7]  ← tighter upper bound is subset

De Morgan in CNF:
  NOT(A AND B) ⊆ C  handled via CNF as (NOT(A) OR NOT(B)) ⊆ C
"""

import pytest

from krrood.entity_query_language.factories import and_, not_, or_, variable
from krrood.entity_query_language.subsumption import EQLSubsumptionEngine


@pytest.fixture
def engine():
    return EQLSubsumptionEngine.default()


@pytest.fixture
def x():
    return variable(int, range(10))


@pytest.fixture
def y():
    return variable(int, range(10))


class TestNOTSubsumption:
    # --- Contrapositive ---

    def test_not_gt5_subsumed_by_not_gt7(self, engine, x):
        # NOT(x > 5) effective (-∞,5] ⊆ NOT(x > 7) effective (-∞,7]? Wait:
        # NOT(x>5) = x<=5 = (-∞,5]; NOT(x>7) = x<=7 = (-∞,7]
        # (-∞,5] ⊆ (-∞,7]? YES (tighter upper bound)
        assert engine.is_subsumed_by(not_(x > 5), not_(x > 7))

    def test_not_gt7_not_subsumed_by_not_gt5(self, engine, x):
        # NOT(x>7) = (-∞,7]; NOT(x>5) = (-∞,5]; (-∞,7] ⊄ (-∞,5]
        assert not engine.is_subsumed_by(not_(x > 7), not_(x > 5))

    def test_not_ge_subsumed_by_not_ge_wider(self, engine, x):
        # NOT(x>=5) = x<5 = (-∞,5); NOT(x>=3) = x<3 = (-∞,3); (-∞,5) ⊄ (-∞,3)
        assert not engine.is_subsumed_by(not_(x >= 5), not_(x >= 3))

    def test_not_ge_subsumed_correct_direction(self, engine, x):
        # NOT(x>=7) = x<7 = (-∞,7); NOT(x>=5) = x<5 = (-∞,5); (-∞,7) ⊄ (-∞,5)
        # But NOT(x>=3) = x<3 = (-∞,3); (-∞,3) ⊆ (-∞,5) YES
        assert engine.is_subsumed_by(not_(x >= 5), not_(x >= 7))

    def test_not_eq_subsumed_by_not_eq_same(self, engine, x):
        # NOT(x==5) deferred (ne operator), but same object → reflexivity
        cond = not_(x == 5)
        assert engine.is_subsumed_by(cond, cond)

    # --- De Morgan via CNF ---

    def test_not_and_distributes_or_cnf(self, engine, x, y):
        # NOT(x>5 AND y>2) = NOT(x>5) OR NOT(y>2)
        # This should be subsumed by NOT(x>5) (via OR inclusion: A ⊆ A OR B)
        # but NOT by NOT(x>7) (NOT(y>2) ⊄ NOT(x>7))
        not_and = not_(and_(x > 5, y > 2))
        assert engine.is_subsumed_by(not_(x > 5), not_and)  # NOT(x>5) ⊆ NOT(AND)
        # Reverse: NOT(AND) ⊄ NOT(x>5) because y also contributes
        assert not engine.is_subsumed_by(not_and, not_(x > 5))

    def test_not_or_distributes_and_cnf(self, engine, x, y):
        # NOT(x>5 OR y>2) = NOT(x>5) AND NOT(y>2)
        # This should be subsumed by NOT(x>5) (conjunction is more restrictive)
        not_or = not_(or_(x > 5, y > 2))
        assert engine.is_subsumed_by(not_or, not_(x > 5))
        assert engine.is_subsumed_by(not_or, not_(y > 2))

    # --- Double negation ---

    def test_double_negation_reflexivity(self, engine, x):
        # NOT(NOT(x > 5)) normalises to x > 5 in CNF, so same as x > 5
        double_not = not_(not_(x > 5))
        assert engine.is_subsumed_by(double_not, double_not)

    def test_double_negation_subsumed_by_original(self, engine, x):
        # NOT(NOT(x > 5)) effectively reduces to x > 5 via CNF
        # NOT(NOT(A)) ⊆ A and A ⊆ NOT(NOT(A))
        original = x > 5
        double_not = not_(not_(x > 5))
        assert engine.is_subsumed_by(double_not, original)
        assert engine.is_subsumed_by(original, double_not)
