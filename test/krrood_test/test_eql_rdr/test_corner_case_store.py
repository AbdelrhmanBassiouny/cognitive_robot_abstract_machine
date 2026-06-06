"""
Phase 1 — Unit tests for ``CornerCaseStore``.

Each test verifies exactly one contract of the store in isolation.  No EQLSingleClassRDR
is constructed here; the only dependency on the wider EQL system is the ``_id_`` UUID that
every ``SymbolicExpression`` carries.

All tests are expected to fail with ``ImportError`` until
``krrood/src/krrood/entity_query_language/rdr/corner_case.py`` is created.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Set, Tuple, Type

import pytest

from krrood.entity_query_language.rdr.corner_case import CornerCaseStore  # noqa: E402
from krrood.entity_query_language.factories import entity, variable
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal, Species


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class MinimalCase:
    """Pattern: MinimalCase — the smallest possible case instance for corner-case tests.

    Avoids pulling in zoo data; contains only attributes needed to build a
    distinguishing EQL condition (``milk``).
    """

    name: str
    milk: bool


def _make_condition_node(case_type=Animal):
    """Return a single EQL comparator node built over a fresh case variable.

    The node has a stable ``_id_`` (UUID) that can be used as a store key.
    """
    av = variable(case_type, domain=[])
    return av.milk == True  # noqa: E712  — produces a SymbolicExpression


def _trivial_emit(case: object) -> Tuple[str, Set[Type]]:
    """Minimal ``emit`` callable: returns the str representation and an empty type set."""
    return (str(case), set())


# ---------------------------------------------------------------------------
# Test 1 — record and retrieve by node id
# ---------------------------------------------------------------------------


def test_record_and_get_by_node_id():
    """``get(node._id_)`` returns the case recorded for that node."""
    store = CornerCaseStore()
    node = _make_condition_node()
    case = MinimalCase(name="test_case", milk=True)

    store.record(node, case)

    assert store.get(node._id_) is case


# ---------------------------------------------------------------------------
# Test 2 — get returns None for an unknown UUID
# ---------------------------------------------------------------------------


def test_get_none_for_missing_node_id():
    """``get`` with an unknown UUID returns ``None`` (no KeyError)."""
    store = CornerCaseStore()

    result = store.get(uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# Test 3 — get returns None for None input
# ---------------------------------------------------------------------------


def test_get_none_for_none_input():
    """``get(None)`` returns ``None`` without raising."""
    store = CornerCaseStore()

    result = store.get(None)

    assert result is None


# ---------------------------------------------------------------------------
# Test 4 — to_ordered_sources only includes nodes that have recorded cases
# ---------------------------------------------------------------------------


def test_to_ordered_sources_only_includes_recorded_nodes():
    """
    When only nodes 0 and 2 (by position in the ordered list) have recorded corner
    cases, ``to_ordered_sources`` returns a dict with keys ``{0, 2}`` — key 1 is absent.
    """
    store = CornerCaseStore()
    n0 = _make_condition_node()
    n1 = _make_condition_node()
    n2 = _make_condition_node()
    case_a = MinimalCase(name="a", milk=True)
    case_c = MinimalCase(name="c", milk=False)

    store.record(n0, case_a)
    store.record(n2, case_c)

    result = store.to_ordered_sources([n0, n1, n2], _trivial_emit)

    assert set(result.keys()) == {0, 2}
    assert 1 not in result


# ---------------------------------------------------------------------------
# Test 5 — to_ordered_sources passes the recorded case instance to emit
# ---------------------------------------------------------------------------


def test_to_ordered_sources_calls_emit_with_the_case():
    """The ``emit`` callable receives the exact case instance that was recorded."""
    store = CornerCaseStore()
    node = _make_condition_node()
    sentinel_case = MinimalCase(name="sentinel", milk=True)
    store.record(node, sentinel_case)

    received: list = []

    def spy_emit(case: object) -> Tuple[str, Set[Type]]:
        received.append(case)
        return (str(case), set())

    store.to_ordered_sources([node], spy_emit)

    assert len(received) == 1
    assert received[0] is sentinel_case


# ---------------------------------------------------------------------------
# Test 6 — from_ordered_cases round-trip
# ---------------------------------------------------------------------------


def test_from_ordered_cases_roundtrip():
    """
    ``CornerCaseStore.from_ordered_cases([n0, n1], {0: case_a, 1: case_b})`` produces a
    store where ``get(n0._id_) is case_a`` and ``get(n1._id_) is case_b``.
    """
    n0 = _make_condition_node()
    n1 = _make_condition_node()
    case_a = MinimalCase(name="a", milk=True)
    case_b = MinimalCase(name="b", milk=False)

    store = CornerCaseStore.from_ordered_cases([n0, n1], {0: case_a, 1: case_b})

    assert store.get(n0._id_) is case_a
    assert store.get(n1._id_) is case_b


# ---------------------------------------------------------------------------
# Test 7 — from_ordered_cases skips indices not present in the dict
# ---------------------------------------------------------------------------


def test_from_ordered_cases_skips_missing_indices():
    """
    ``from_ordered_cases([n0, n1, n2], {1: case_b})`` yields a store where only
    ``n1._id_`` has an entry; ``n0`` and ``n2`` are absent.
    """
    n0 = _make_condition_node()
    n1 = _make_condition_node()
    n2 = _make_condition_node()
    case_b = MinimalCase(name="b", milk=False)

    store = CornerCaseStore.from_ordered_cases([n0, n1, n2], {1: case_b})

    assert store.get(n1._id_) is case_b
    assert store.get(n0._id_) is None
    assert store.get(n2._id_) is None


# ---------------------------------------------------------------------------
# Test 8 — recording a second case for the same node overwrites the first
# ---------------------------------------------------------------------------


def test_record_overwrites_previous_entry():
    """A second ``record`` call for the same node replaces the previously stored case."""
    store = CornerCaseStore()
    node = _make_condition_node()
    first_case = MinimalCase(name="first", milk=True)
    second_case = MinimalCase(name="second", milk=False)

    store.record(node, first_case)
    store.record(node, second_case)

    assert store.get(node._id_) is second_case
    assert store.get(node._id_) is not first_case
