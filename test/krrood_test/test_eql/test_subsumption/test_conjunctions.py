"""
Level 3 — AND (conjunction) subsumption.

CNF handles these via clause set union; no explicit AND rules are needed.

Absorption:
  (A AND B) ⊆ A          — conjunction implies each conjunct
  (A AND B) ⊆ B
  (A AND B) ⊆ C          — via absorption + transitivity (A ⊆ C or B ⊆ C)

Splitting:
  X ⊆ (A AND B)          iff X ⊆ A AND X ⊆ B

Conjunction tightening:
  (A AND B) ⊆ (C AND D)  when A ⊆ C and B ⊆ D

Non-subsumption:
  A ⊄ (A AND B)          — A does not imply B in general
  (A AND B) ⊄ C          — when neither A ⊆ C nor B ⊆ C can be derived
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


class TestANDSubsumption:
    # --- Absorption ---

    def test_conjunction_subsumed_by_left_conjunct(self, engine, x, y):
        assert engine.is_subsumed_by(and_(x > 5, y > 2), x > 5)

    def test_conjunction_subsumed_by_right_conjunct(self, engine, x, y):
        assert engine.is_subsumed_by(and_(x > 5, y > 2), y > 2)

    def test_conjunction_subsumed_by_wider_condition_via_left(self, engine, x, y):
        # x > 5 ⊆ x > 3, so (x > 5 AND y > 2) ⊆ x > 3
        assert engine.is_subsumed_by(and_(x > 5, y > 2), x > 3)

    def test_conjunction_subsumed_by_wider_condition_via_right(self, engine, x, y):
        # y > 2 ⊆ y > 1, so (x > 5 AND y > 2) ⊆ y > 1
        assert engine.is_subsumed_by(and_(x > 5, y > 2), y > 1)

    # --- Splitting ---

    def test_single_condition_not_subsumed_by_conjunction_extra_var(self, engine, x, y):
        # x > 5 ⊄ (x > 3 AND y > 1) because x > 5 does not imply y > 1
        assert not engine.is_subsumed_by(x > 5, and_(x > 3, y > 1))

    def test_conjunction_subsumed_by_conjunction_both_wider(self, engine, x, y):
        # (x > 5 AND y > 2) ⊆ (x > 3 AND y > 1)
        assert engine.is_subsumed_by(and_(x > 5, y > 2), and_(x > 3, y > 1))

    def test_conjunction_not_subsumed_by_conjunction_one_fails(self, engine, x, y):
        # (x > 5 AND y > 2) ⊄ (x > 7 AND y > 1) because x > 5 ⊄ x > 7
        assert not engine.is_subsumed_by(and_(x > 5, y > 2), and_(x > 7, y > 1))

    # --- Three-way conjunction ---

    def test_triple_conjunction_subsumed_by_one_conjunct(self, engine, x, y):
        z = variable(int, range(10))
        assert engine.is_subsumed_by(and_(x > 5, y > 2, z > 1), x > 3)

    def test_triple_conjunction_subsumed_by_all_three_wider(self, engine, x, y):
        z = variable(int, range(10))
        assert engine.is_subsumed_by(
            and_(x > 5, y > 2, z > 1),
            and_(x > 3, y > 1, z > 0),
        )

    # --- Non-subsumption ---

    def test_single_not_subsumed_by_conjunction_missing_constraint(self, engine, x, y):
        assert not engine.is_subsumed_by(x > 5, and_(x > 3, y > 2))

    def test_conjunction_not_subsumed_by_unrelated_condition(self, engine, x, y):
        assert not engine.is_subsumed_by(and_(x > 5, y > 2), x > 7)
