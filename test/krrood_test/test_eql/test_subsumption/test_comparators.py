"""
Level 2 — Comparator subsumption.

Tests the interval model for ordered comparisons and set-membership comparisons.

Interval cases:
  x > 5  ⊆  x > 3    (tighter lower bound → subset)
  x > 3  ⊄  x > 5    (wider lower bound → not subset)
  x >= 5 ⊆  x >= 5   (same bound, same inclusivity → equal)
  x >= 5 ⊆  x > 3    (lower bound 5 > 3, operator difference OK)
  x >= 5 ⊄  x > 5    ([5,∞) ⊄ (5,∞) — 5 is in lhs but not rhs)
  x == 5 ⊆  x >= 5   ([5,5] ⊆ [5,∞))
  x == 5 ⊆  x > 3    ([5,5] ⊆ (3,∞))
  x == 5 ⊄  x > 5    ([5,5] ⊄ (5,∞))
  x < 3  ⊆  x < 5    ((-∞,3) ⊆ (-∞,5))
  x <= 3 ⊆  x <= 5   ((-∞,3] ⊆ (-∞,5])
  x <= 3 ⊄  x < 3    ((-∞,3] ⊄ (-∞,3))
  x < 3  ⊆  x <= 3   ((-∞,3) ⊆ (-∞,3])

Membership cases:
  x in {1}     ⊆  x in {1, 2, 3}
  x in {1, 2}  ⊄  x in {1}
  x == 1       ⊆  x in {1, 2, 3}
  x == 4       ⊄  x in {1, 2, 3}

Different-variable cases (should never return True):
  x > 5  ⊄  y > 3   (different variables)
"""

import pytest

from krrood.entity_query_language.factories import in_, variable
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


# ---------------------------------------------------------------------------
# Ordered comparisons
# ---------------------------------------------------------------------------

class TestOrderedComparatorSubsumption:
    def test_gt_tighter_bound_is_subsumed(self, engine, x):
        assert engine.is_subsumed_by(x > 5, x > 3)

    def test_gt_wider_bound_not_subsumed(self, engine, x):
        assert not engine.is_subsumed_by(x > 3, x > 5)

    def test_gt_equal_bound_is_subsumed(self, engine, x):
        assert engine.is_subsumed_by(x > 5, x > 5)

    def test_ge_subsumed_by_ge_tighter(self, engine, x):
        assert engine.is_subsumed_by(x >= 5, x >= 3)

    def test_ge_not_subsumed_by_ge_wider(self, engine, x):
        assert not engine.is_subsumed_by(x >= 3, x >= 5)

    def test_ge_subsumed_by_gt_when_strictly_above(self, engine, x):
        # x >= 5 ⊆ x > 3  ([5,∞) ⊆ (3,∞)): lower 5 > 3 ✓
        assert engine.is_subsumed_by(x >= 5, x > 3)

    def test_ge_not_subsumed_by_gt_same_bound(self, engine, x):
        # x >= 5 ⊄ x > 5 ([5,∞) ⊄ (5,∞)): 5 is in lhs but not rhs
        assert not engine.is_subsumed_by(x >= 5, x > 5)

    def test_gt_subsumed_by_ge_same_bound(self, engine, x):
        # x > 5 ⊆ x >= 5  ((5,∞) ⊆ [5,∞))
        assert engine.is_subsumed_by(x > 5, x >= 5)

    def test_lt_tighter_upper_is_subsumed(self, engine, x):
        assert engine.is_subsumed_by(x < 3, x < 5)

    def test_lt_wider_upper_not_subsumed(self, engine, x):
        assert not engine.is_subsumed_by(x < 5, x < 3)

    def test_le_subsumed_by_le_tighter(self, engine, x):
        assert engine.is_subsumed_by(x <= 3, x <= 5)

    def test_le_not_subsumed_by_lt_same_bound(self, engine, x):
        # x <= 3 ⊄ x < 3 ((-∞,3] ⊄ (-∞,3))
        assert not engine.is_subsumed_by(x <= 3, x < 3)

    def test_lt_subsumed_by_le_same_bound(self, engine, x):
        # x < 3 ⊆ x <= 3 ((-∞,3) ⊆ (-∞,3])
        assert engine.is_subsumed_by(x < 3, x <= 3)

    def test_eq_subsumed_by_ge(self, engine, x):
        assert engine.is_subsumed_by(x == 5, x >= 5)

    def test_eq_subsumed_by_gt_strict(self, engine, x):
        # x == 5 ⊆ x > 3 ([5,5] ⊆ (3,∞))
        assert engine.is_subsumed_by(x == 5, x > 3)

    def test_eq_not_subsumed_by_gt_same_value(self, engine, x):
        # x == 5 ⊄ x > 5 ([5,5] ⊄ (5,∞): 5 not in (5,∞))
        assert not engine.is_subsumed_by(x == 5, x > 5)

    def test_eq_subsumed_by_le(self, engine, x):
        assert engine.is_subsumed_by(x == 3, x <= 3)

    def test_eq_subsumed_by_lt_strict(self, engine, x):
        assert engine.is_subsumed_by(x == 3, x < 5)

    def test_eq_not_subsumed_by_lt_same_value(self, engine, x):
        assert not engine.is_subsumed_by(x == 3, x < 3)

    def test_different_variables_not_subsumed(self, engine, x, y):
        assert not engine.is_subsumed_by(x > 5, y > 3)


# ---------------------------------------------------------------------------
# Membership comparisons
# ---------------------------------------------------------------------------

class TestMembershipSubsumption:
    def test_singleton_subset_of_larger_set(self, engine, x):
        assert engine.is_subsumed_by(in_(x, [1]), in_(x, [1, 2, 3]))

    def test_subset_of_superset(self, engine, x):
        assert engine.is_subsumed_by(in_(x, [1, 2]), in_(x, [1, 2, 3]))

    def test_equal_sets_subsumed(self, engine, x):
        assert engine.is_subsumed_by(in_(x, [1, 2]), in_(x, [1, 2]))

    def test_superset_not_subsumed_by_subset(self, engine, x):
        assert not engine.is_subsumed_by(in_(x, [1, 2, 3]), in_(x, [1]))

    def test_disjoint_sets_not_subsumed(self, engine, x):
        assert not engine.is_subsumed_by(in_(x, [4, 5]), in_(x, [1, 2, 3]))

    def test_eq_subsumed_by_membership_containing_value(self, engine, x):
        assert engine.is_subsumed_by(x == 1, in_(x, [1, 2, 3]))

    def test_eq_not_subsumed_by_membership_missing_value(self, engine, x):
        assert not engine.is_subsumed_by(x == 4, in_(x, [1, 2, 3]))

    def test_different_variables_not_subsumed(self, engine, x, y):
        assert not engine.is_subsumed_by(in_(x, [1, 2]), in_(y, [1, 2, 3]))
