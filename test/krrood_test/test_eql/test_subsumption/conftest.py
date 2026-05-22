"""
Shared fixtures for EQL subsumption tests.

Variables are created once per test via function-scoped fixtures so that each test
gets fresh UUIDs and there is no cross-test state pollution.
"""

import pytest

from krrood.entity_query_language.factories import variable, for_all, exists
from krrood.entity_query_language.subsumption import EQLSubsumptionEngine


@pytest.fixture
def engine() -> EQLSubsumptionEngine:
    return EQLSubsumptionEngine.default()


@pytest.fixture
def x():
    """Integer variable ranging over 0..9."""
    return variable(int, range(10))


@pytest.fixture
def y():
    """Integer variable ranging over 0..9 (distinct from x)."""
    return variable(int, range(10))


@pytest.fixture
def z():
    """Float variable."""
    return variable(float, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
