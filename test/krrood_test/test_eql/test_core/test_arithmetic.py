"""
Tests for symbolic arithmetic operations in the Entity Query Language.

Arithmetic is written with the normal Python operators on EQL variables (``a + b``, ``-x`` …). The
computation is routed through the backend selected by
:class:`~krrood.entity_query_language.configuration.EqlConfiguration` (Python by default, symbolic on
request).
"""

import operator
import statistics

import pytest

import krrood.entity_query_language.factories as eql
from krrood.entity_query_language.factories import (
    EqlConfiguration,
    MathBackend,
    an,
    entity,
    variable,
)

from ...dataset.department_and_employee import Department, Employee


@pytest.fixture(autouse=True)
def python_backend_by_default():
    """Isolate every test by forcing the default Python backend before and after it runs."""
    EqlConfiguration().math_backend = MathBackend.PYTHON
    yield
    EqlConfiguration().math_backend = MathBackend.PYTHON


@pytest.fixture
def symbolic_backend():
    """Activate the symbolic-math backend, skipping when ``casadi`` is unavailable."""
    pytest.importorskip("casadi")
    EqlConfiguration().math_backend = MathBackend.SYMBOLIC
    yield
    EqlConfiguration().math_backend = MathBackend.PYTHON


# --- each operator matches plain Python semantics ----------------------------

@pytest.mark.parametrize(
    "python_operator",
    [
        operator.add,
        operator.sub,
        operator.mul,
        operator.truediv,
        operator.floordiv,
        operator.mod,
        operator.pow,
    ],
)
def test_binary_operator_matches_python(python_operator):
    left_values = [10, 20, 30]
    right_value = 4
    left = variable(int, domain=left_values)
    query = an(entity(python_operator(left, right_value)))
    assert query.tolist() == [python_operator(value, right_value) for value in left_values]


def test_unary_negation():
    numbers = variable(int, domain=[1, -2, 3])
    assert an(entity(-numbers)).tolist() == [-1, 2, -3]


# --- reflected / non-commutative operators preserve operand order ------------

def test_reflected_non_commutative_operators():
    numbers = variable(int, domain=[2, 4])
    assert an(entity(10 - numbers)).tolist() == [8, 6]
    assert an(entity(20 // numbers)).tolist() == [10, 5]
    assert an(entity(10 % numbers)).tolist() == [0, 2]
    assert an(entity(2 ** numbers)).tolist() == [4, 16]


def test_literal_operand_in_either_position():
    numbers = variable(int, domain=[2, 3])
    assert an(entity(numbers * 10)).tolist() == [20, 30]
    assert an(entity(10 * numbers)).tolist() == [20, 30]


# --- composes with the rest of EQL -------------------------------------------

def test_chained_arithmetic():
    numbers = variable(int, domain=[1, 2, 3])
    assert an(entity((numbers + 1) * 2)).tolist() == [4, 6, 8]


def test_comparison_of_arithmetic_filters_results():
    department = Department(name="research")
    employees = [
        Employee(name="ada", department=department, salary=1000, starting_salary=900),
        Employee(name="bob", department=department, salary=3000, starting_salary=500),
    ]
    employee = variable(Employee, domain=employees)
    query = an(entity(employee).where((employee.salary - employee.starting_salary) > 1000))
    assert [result.name for result in query.tolist()] == ["bob"]


def test_aggregation_over_arithmetic():
    numbers = variable(int, domain=[1, 2, 3])
    assert eql.sum(numbers + 1).tolist()[0] == sum(value + 1 for value in [1, 2, 3])
    assert eql.average(numbers * 2).tolist()[0] == statistics.mean([2, 4, 6])


# --- backend selection -------------------------------------------------------

def test_default_backend_is_python():
    EqlConfiguration.clear_instance()
    assert EqlConfiguration().math_backend is MathBackend.PYTHON


def test_symbolic_backend_builds_a_symbolic_expression(symbolic_backend):
    from krrood.symbolic_math.symbolic_math import Scalar

    numbers = variable(int, domain=[3])
    result = an(entity(numbers * 2)).tolist()
    assert isinstance(result[0], Scalar)
    assert result[0].to_np().item() == 6.0


def test_division_by_zero_diverges_between_backends(symbolic_backend):
    numerator = variable(int, domain=[1])
    denominator = variable(int, domain=[0])

    # The symbolic backend yields a (non-finite) value instead of raising.
    assert len(an(entity(numerator / denominator)).tolist()) == 1

    EqlConfiguration().math_backend = MathBackend.PYTHON
    with pytest.raises(ZeroDivisionError):
        an(entity(numerator / denominator)).tolist()
