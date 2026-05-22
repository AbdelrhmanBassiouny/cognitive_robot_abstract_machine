"""
Level 6 — Quantifier (ForAll, Exists) subsumption.

ForAllMonotonicityRule:
  ForAll(x, P) ⊆ ForAll(x, Q)  if P ⊆ Q

ExistsMonotonicityRule:
  Exists(x, P) ⊆ Exists(x, Q)  if P ⊆ Q

Non-subsumption:
  ForAll(x, P) ⊄ ForAll(x, Q)  when P ⊄ Q
  Exists(x, P) ⊄ Exists(x, Q)  when P ⊄ Q
  ForAll(x, P) ⊄ Exists(y, Q)  when x ≠ y (different variable)

Deferred (Phase 3):
  ForAll(x, P) ⊆ Exists(x, P)  under non-empty domain assumption — not tested here.

The inner condition P is also tested with compound expressions so that the recursive
engine call exercises both comparator and AND/OR rules.
"""

import pytest

from krrood.entity_query_language.factories import (
    and_,
    exists,
    for_all,
    or_,
    variable,
)
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


class TestForAllSubsumption:
    def test_forall_monotonicity_gt(self, engine, x, y):
        # ForAll(y, y > 5) ⊆ ForAll(y, y > 3)
        assert engine.is_subsumed_by(for_all(y, y > 5), for_all(y, y > 3))

    def test_forall_not_subsumed_reverse(self, engine, x, y):
        assert not engine.is_subsumed_by(for_all(y, y > 3), for_all(y, y > 5))

    def test_forall_reflexivity(self, engine, x, y):
        cond = for_all(y, y > 5)
        assert engine.is_subsumed_by(cond, cond)

    def test_forall_compound_inner_condition(self, engine, x, y):
        # ForAll(y, y > 5 AND x > 2) ⊆ ForAll(y, y > 3 AND x > 1)
        assert engine.is_subsumed_by(
            for_all(y, and_(y > 5, x > 2)),
            for_all(y, and_(y > 3, x > 1)),
        )

    def test_forall_inner_or_condition(self, engine, x, y):
        # ForAll(y, y > 7) ⊆ ForAll(y, y > 5 OR x > 2)
        # because y > 7 ⊆ y > 5 ⊆ (y > 5 OR x > 2)
        assert engine.is_subsumed_by(
            for_all(y, y > 7),
            for_all(y, or_(y > 5, x > 2)),
        )

    def test_forall_different_variables_not_subsumed(self, engine, x, y):
        assert not engine.is_subsumed_by(for_all(x, x > 5), for_all(y, y > 3))


class TestExistsSubsumption:
    def test_exists_monotonicity_gt(self, engine, x, y):
        assert engine.is_subsumed_by(exists(y, y > 5), exists(y, y > 3))

    def test_exists_not_subsumed_reverse(self, engine, x, y):
        assert not engine.is_subsumed_by(exists(y, y > 3), exists(y, y > 5))

    def test_exists_reflexivity(self, engine, x, y):
        cond = exists(y, y > 5)
        assert engine.is_subsumed_by(cond, cond)

    def test_exists_compound_inner_condition(self, engine, x, y):
        assert engine.is_subsumed_by(
            exists(y, and_(y > 5, x > 2)),
            exists(y, and_(y > 3, x > 1)),
        )

    def test_exists_different_variables_not_subsumed(self, engine, x, y):
        assert not engine.is_subsumed_by(exists(x, x > 5), exists(y, y > 3))


class TestCrossQuantifierSubsumption:
    def test_forall_not_subsumed_by_exists_different_type(self, engine, x, y):
        # ForAll and Exists are different atom types — no cross-rule in Phase 1
        assert not engine.is_subsumed_by(for_all(y, y > 5), exists(y, y > 3))

    def test_exists_not_subsumed_by_forall(self, engine, x, y):
        assert not engine.is_subsumed_by(exists(y, y > 5), for_all(y, y > 3))
