"""
Level 1 — Reflexivity.

A condition is always subsumed by itself: A ⊆ A.
Covered cases:
- Same Python object (identity).
- Structurally equal comparators built from the same variable and literal.
- Same AND / OR / NOT compound on the same variables.
- Same ForAll / Exists on the same variable.
"""

import pytest

from krrood.entity_query_language.factories import (
    and_,
    exists,
    for_all,
    not_,
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


class TestReflexivity:
    def test_same_comparator_object(self, engine, x):
        cond = x > 3
        assert engine.is_subsumed_by(cond, cond)

    def test_same_gt_comparator(self, engine, x):
        cond = x > 5
        assert engine.is_subsumed_by(cond, cond)

    def test_same_eq_comparator(self, engine, x):
        cond = x == 4
        assert engine.is_subsumed_by(cond, cond)

    def test_same_lt_comparator(self, engine, x):
        cond = x < 7
        assert engine.is_subsumed_by(cond, cond)

    def test_same_and_compound(self, engine, x, y):
        cond = and_(x > 3, y < 8)
        assert engine.is_subsumed_by(cond, cond)

    def test_same_or_compound(self, engine, x, y):
        cond = or_(x > 3, y < 8)
        assert engine.is_subsumed_by(cond, cond)

    def test_same_not_compound(self, engine, x):
        cond = not_(x > 3)
        assert engine.is_subsumed_by(cond, cond)

    def test_same_forall(self, engine, x, y):
        cond = for_all(x, x > 3)
        assert engine.is_subsumed_by(cond, cond)

    def test_same_exists(self, engine, x, y):
        cond = exists(x, x > 3)
        assert engine.is_subsumed_by(cond, cond)
