"""
Level 4 — OR (disjunction) subsumption.

Inclusion:
  A ⊆ (A OR B)              — any condition is subsumed by a disjunction it is part of
  B ⊆ (A OR B)

Merging:
  (A OR B) ⊆ C              iff A ⊆ C AND B ⊆ C
  (A OR B) ⊆ (C OR D)       when each disjunct of the left is subsumed by some disjunct
                              on the right (handled via CNF clause distribution)

Non-subsumption:
  (A OR B) ⊄ C              when A ⊄ C (even if B ⊆ C)
"""

import pytest

from krrood.entity_query_language.factories import and_, or_, variable
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


class TestORSubsumption:
    # --- Inclusion ---

    def test_left_subsumed_by_disjunction(self, engine, x, y):
        assert engine.is_subsumed_by(x > 5, or_(x > 5, y > 2))

    def test_right_subsumed_by_disjunction(self, engine, x, y):
        assert engine.is_subsumed_by(y > 2, or_(x > 5, y > 2))

    def test_tighter_left_subsumed_by_disjunction(self, engine, x, y):
        # x > 7 ⊆ x > 5 ⊆ (x > 5 OR y > 2)
        assert engine.is_subsumed_by(x > 7, or_(x > 5, y > 2))

    # --- Merging ---

    def test_disjunction_subsumed_by_wider_condition_both_sides(self, engine, x):
        # (x > 7 OR x > 5) ⊆ x > 3  (both x > 7 ⊆ x > 3 and x > 5 ⊆ x > 3)
        assert engine.is_subsumed_by(or_(x > 7, x > 5), x > 3)

    def test_disjunction_not_subsumed_when_one_side_fails(self, engine, x, y):
        # (x > 5 OR y > 2) ⊄ x > 3  because y > 2 ⊄ x > 3
        assert not engine.is_subsumed_by(or_(x > 5, y > 2), x > 3)

    def test_disjunction_subsumed_by_disjunction_all_pairs_covered(self, engine, x):
        # (x > 7 OR x > 5) ⊆ (x > 5 OR x > 3)
        assert engine.is_subsumed_by(or_(x > 7, x > 5), or_(x > 5, x > 3))

    def test_disjunction_not_subsumed_by_disjunction_when_pair_missing(
        self, engine, x, y
    ):
        # (x > 5 OR y > 2) ⊄ (x > 3 OR x > 1) because y > 2 is not ⊆ any rhs disjunct
        assert not engine.is_subsumed_by(or_(x > 5, y > 2), or_(x > 3, x > 1))

    # --- Three-way disjunction ---

    def test_triple_disjunction_subsumed_all_three_covered(self, engine, x):
        assert engine.is_subsumed_by(or_(x > 7, x > 5, x > 4), x > 3)

    def test_triple_disjunction_not_subsumed_one_uncovered(self, engine, x):
        assert not engine.is_subsumed_by(or_(x > 7, x > 5, x > 2), x > 3)
