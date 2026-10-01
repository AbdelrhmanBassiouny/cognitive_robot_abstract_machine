"""
An aggregator in a where condition over variables the query does not otherwise use is a
subquery: it is computed once over its own variables and compared as a single value.

One over the query's own variables has no single value per row, so it is still refused.
"""

import pytest

from krrood.entity_query_language.exceptions import AggregatorInWhereConditionsError
from krrood.entity_query_language.factories import average, entity, set_of, variable

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
    assert query.tolist() == [
        candidate for candidate in bodies if candidate.size > mean_salary
    ]


def test_unrelated_aggregator_on_the_left_filters_by_its_overall_value(
    bodies, employees
):
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    mean_salary = overall_value(average(employee.salary))
    query = entity(body).where(average(employee.salary) > body.size)
    assert query.tolist() == [
        candidate for candidate in bodies if mean_salary > candidate.size
    ]


# %% an aggregator over the query's own variables


def test_aggregator_over_the_selected_variable_is_refused(bodies):
    body = variable(Body, domain=bodies)
    with pytest.raises(AggregatorInWhereConditionsError):
        entity(body).where(body.size > average(body.size)).tolist()


def test_aggregator_over_another_selected_variable_is_refused(bodies, employees):
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    with pytest.raises(AggregatorInWhereConditionsError):
        set_of(body, employee).where(body.size > average(employee.salary)).tolist()


# %% an aggregator over a variable only the conditions use


def test_aggregator_over_a_variable_only_the_conditions_use_is_a_subquery(
    bodies, employees
):
    """
    A variable the query does not select is not bound by it, so an aggregator over it is
    still computed over its own variables, whatever the other conditions say.
    """
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    mean_salary = overall_value(average(employee.salary))
    query = (
        entity(body)
        .where(body.size > average(employee.salary), employee.salary < body.size)
        .distinct()
    )
    assert query.tolist() == [
        candidate
        for candidate in bodies
        if candidate.size > mean_salary
        and any(worker.salary < candidate.size for worker in employees)
    ]


def test_unrelated_aggregator_in_a_later_where_is_a_subquery(bodies, employees):
    body = variable(Body, domain=bodies)
    employee = variable(Employee, domain=employees)
    mean_salary = overall_value(average(employee.salary))
    query = (
        entity(body).where(body.size > 1).where(body.size > average(employee.salary))
    )
    assert query.tolist() == [
        candidate
        for candidate in bodies
        if candidate.size > 1 and candidate.size > mean_salary
    ]
