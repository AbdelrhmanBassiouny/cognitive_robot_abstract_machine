"""
An aggregator in a where condition over variables the query does not otherwise use is a
subquery: it is computed once over its own variables and compared as a single value.

One over the query's own variables has no single value per row, so it is still refused.
"""

import pytest

from krrood.entity_query_language.exceptions import AggregatorInWhereConditionsError
from krrood.entity_query_language.factories import average, entity, variable

from ...dataset.department_and_employee import Department, Employee
from ...dataset.semantic_world_like_classes import Body


@pytest.fixture
def bodies():
    return [Body(f"Body{size}", size=size) for size in range(1, 6)]


@pytest.fixture
def employees():
    department = Department("Robotics")
    return [
        Employee("Ada", department, salary=2.0),
        Employee("Bob", department, salary=4.0),
    ]


def overall_value(aggregator):
    """
    :return: The single value the aggregator takes over its own variables.
    """
    return next(iter(aggregator.evaluate()))


# %% an aggregator over variables the query does not otherwise use


def test_unrelated_aggregator_on_the_right_filters_by_its_overall_value(
    bodies, employees
):
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    mean_salary = overall_value(average(employee.salary))
    query = entity(body).where(body.size > average(employee.salary))
    assert query.tolist() == [b for b in bodies if b.size > mean_salary]


def test_unrelated_aggregator_on_the_left_filters_by_its_overall_value(
    bodies, employees
):
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    mean_salary = overall_value(average(employee.salary))
    query = entity(body).where(average(employee.salary) > body.size)
    assert query.tolist() == [b for b in bodies if mean_salary > b.size]


# %% an aggregator over the query's own variables


def test_aggregator_over_the_selected_variable_is_refused(bodies):
    body = variable(Body, domain=bodies)
    with pytest.raises(AggregatorInWhereConditionsError):
        entity(body).where(body.size > average(body.size)).tolist()


def test_aggregator_related_by_another_condition_is_refused(bodies, employees):
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    with pytest.raises(AggregatorInWhereConditionsError):
        entity(body).where(
            body.size > average(employee.salary), employee.salary < body.size
        ).tolist()


def test_aggregator_related_by_a_later_condition_is_refused(bodies, employees):
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    query = entity(body).where(body.size > average(employee.salary))
    with pytest.raises(AggregatorInWhereConditionsError):
        query.where(employee.salary < body.size)
