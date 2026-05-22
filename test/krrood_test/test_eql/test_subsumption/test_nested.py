"""
Level 7 — Nested and mixed expressions.

These tests exercise the full pipeline: CNF conversion of complex nested expressions
combined with atomic subsumption rules, including quantifiers wrapping compound conditions.

Selected cases:
  (x > 5 AND y > 2) ⊆ (x > 3 OR y > 1)
      A_cnf = {x>5} ∧ {y>2}
      B_cnf = {x>3, y>1}
      For D={x>3,y>1}: C={x>5} — x>5 ⊆ x>3 ✓  →  result True

  (x > 5 AND y > 2) ⊄ (x > 7 OR y > 1)
      For D={x>7,y>1}: C={x>5} — x>5 ⊄ x>7, x>5 ⊄ y>1; C={y>2} — y>2 ⊄ x>7, y>2 ⊄ y>1
      →  result False

  NOT(x > 5 OR y > 2) ⊆ NOT(x > 5)
      NOT(OR) = AND(NOT) so {NOT(x>5)} ∧ {NOT(y>2)} ⊆ {NOT(x>5)} ✓

  Exists(x, (x > 5 AND y > 2)) ⊆ Exists(x, x > 3)
      Inner: (x>5 AND y>2) ⊆ x>3  (via absorption x>5 ⊆ x>3)  →  True

  ForAll(x, (x > 5 OR y > 2)) ⊆ ForAll(x, x > 3)
      Inner: (x>5 OR y>2) ⊆ x>3?  x>5 ⊆ x>3 but y>2 ⊄ x>3  →  False

  Deeply nested AND(AND(…), AND(…)) ⊆ wider condition
"""

import pytest

from krrood.entity_query_language.factories import (
    and_,
    exists,
    for_all,
    in_,
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


class TestNestedMixed:
    def test_conjunction_subsumed_by_disjunction(self, engine, x, y):
        # (x>5 AND y>2) ⊆ (x>3 OR y>1)
        assert engine.is_subsumed_by(and_(x > 5, y > 2), or_(x > 3, y > 1))

    def test_conjunction_not_subsumed_by_disjunction_no_cover(self, engine, x, y):
        # (x>5 AND y>2) ⊄ (x>7 OR y>4)
        # Counterexample: x=6, y=3 satisfies A but 6>7 is False and 3>4 is False.
        # Note: y>1 would be wrong here because y>2 implies y>1, making it actually True.
        assert not engine.is_subsumed_by(and_(x > 5, y > 2), or_(x > 7, y > 4))

    def test_not_or_subsumed_by_not_single(self, engine, x, y):
        # NOT(x>5 OR y>2) = NOT(x>5) AND NOT(y>2) ⊆ NOT(x>5)
        assert engine.is_subsumed_by(not_(or_(x > 5, y > 2)), not_(x > 5))

    def test_not_or_not_subsumed_by_not_single_reverse(self, engine, x, y):
        # NOT(x>5) ⊄ NOT(x>5 OR y>2) because NOT(x>5) does not imply NOT(y>2)
        assert not engine.is_subsumed_by(not_(x > 5), not_(or_(x > 5, y > 2)))

    def test_exists_with_compound_inner(self, engine, x, y):
        # Exists(x, (x>5 AND y>2)) ⊆ Exists(x, x>3)
        # Inner: (x>5 AND y>2) ⊆ x>3 via absorption (x>5 ⊆ x>3)
        assert engine.is_subsumed_by(exists(x, and_(x > 5, y > 2)), exists(x, x > 3))

    def test_forall_with_disjunction_inner_not_subsumed(self, engine, x, y):
        # ForAll(x, (x>5 OR y>2)) ⊄ ForAll(x, x>3)
        # Inner: (x>5 OR y>2) ⊄ x>3 because y>2 ⊄ x>3
        assert not engine.is_subsumed_by(
            for_all(x, or_(x > 5, y > 2)), for_all(x, x > 3)
        )

    def test_deeply_nested_and(self, engine, x, y):
        z = variable(int, range(10))
        # ((x>5 AND y>2) AND z>1) ⊆ x>3
        assert engine.is_subsumed_by(and_(and_(x > 5, y > 2), z > 1), x > 3)

    def test_deeply_nested_and_all_conjuncts_covered(self, engine, x, y):
        z = variable(int, range(10))
        # ((x>5 AND y>2) AND z>1) ⊆ ((x>3 AND y>1) AND z>0)
        assert engine.is_subsumed_by(
            and_(and_(x > 5, y > 2), z > 1),
            and_(and_(x > 3, y > 1), z > 0),
        )

    def test_conjunction_with_membership_subsumed_by_disjunction(self, engine, x, y):
        # (x in {1,2} AND y > 3) ⊆ (x in {1,2,3} OR y > 2)
        # Via: x in {1,2} ⊆ x in {1,2,3}  →  cnf clause {x∈{1,2}} covered by {x∈{1,2,3}, y>2}
        assert engine.is_subsumed_by(
            and_(in_(x, [1, 2]), y > 3),
            or_(in_(x, [1, 2, 3]), y > 2),
        )

    def test_not_and_subsumed_by_disjunction(self, engine, x, y):
        # NOT(x>5 AND y>2) = NOT(x>5) OR NOT(y>2)
        # Is this ⊆ (NOT(x>7) OR NOT(y>4))?
        # NOT(x>5)=(-∞,5] ⊆ NOT(x>7)=(-∞,7] ✓ → clause {NOT(x>5),NOT(y>2)} covers D={NOT(x>7),NOT(y>4)}
        assert engine.is_subsumed_by(
            not_(and_(x > 5, y > 2)),
            not_(and_(x > 7, y > 4)),
        )

    def test_forall_exists_nested_conditions(self, engine, x, y):
        # ForAll(x, Exists(y, y > 5)) ⊆ ForAll(x, Exists(y, y > 3))
        # Outer: ForAll monotonicity → check inner: Exists(y,y>5) ⊆ Exists(y,y>3)
        # Inner: Exists monotonicity → check condition: y>5 ⊆ y>3 ✓
        assert engine.is_subsumed_by(
            for_all(x, exists(y, y > 5)),
            for_all(x, exists(y, y > 3)),
        )
