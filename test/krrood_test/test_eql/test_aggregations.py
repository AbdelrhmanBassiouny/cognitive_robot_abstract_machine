import pytest

import krrood.entity_query_language.entity_result_processors as eql
from krrood.entity_query_language.entity_result_processors import an, a
from krrood.entity_query_language.entity import (
    variable,
    variable_from,
    entity,
    set_of,
)
from krrood.entity_query_language.failures import NonAggregatedSelectedVariablesError
from ..dataset.department_and_employee import Department, Employee
from ..dataset.semantic_world_like_classes import Cabinet


def test_non_aggregated_selectables_with_aggregated_ones(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)
    with pytest.raises(NonAggregatedSelectedVariablesError):
        query = a(
            set_of(drawer, eql.max(drawer))
            .where(drawer.handle.name.startswith("H"))
            .grouped_by(cabinet)
        )
        _ = list(query.evaluate())


def test_max_grouped_by(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)

    # We want to find the drawer with the "largest" handle name (alphabetically) per cabinet.
    # drawers_by_cabinet = variable_from(cabinet.drawers).grouped_by(cabinet)
    query = a(
        set_of(
            cabinet, max_drawer := eql.max(drawer, key=lambda d: d.handle.name)
        ).grouped_by(cabinet)
    )
    results = list(query.evaluate())

    # expected: for each cabinet, one result which is the drawer with max handle name
    expected_cabinets = [c for c in world.views if isinstance(c, Cabinet)]
    assert len(results) == len(expected_cabinets)

    for res in results:
        # res should have cabinet and the drawer in bindings
        c = res[cabinet]
        d = res[max_drawer]
        assert d in c.drawers
        assert d.handle.name == max(cd.handle.name for cd in c.drawers)


def test_multiple_per_variables(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)

    # Group by both cabinet and drawer (silly, but tests multiple variables)
    count = eql.count(drawer).per(cabinet, drawer)
    results = list(count.evaluate())

    # Each result should have count=1 because each (cabinet, drawer) pair is unique here
    for res in results:
        assert res[count] == 1
        assert res[cabinet] is not None
        assert res[drawer] is not None


def test_sum_per(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)
    # Give drawers a numeric property to sum. They don't have one, but we can use a key func.
    # Let's sum the length of handle names per cabinet.

    total_characters = eql.sum(drawer, key=lambda d: len(d.handle.name)).per(cabinet)
    results = list(total_characters.evaluate())

    expected_cabinets = [c for c in world.views if isinstance(c, Cabinet)]
    assert len(results) == len(expected_cabinets)

    for res in results:
        c = res[cabinet]
        s = res[total_characters]
        assert s == sum(len(d.handle.name) for d in c.drawers)


def test_count_per(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    cabinet_drawers = variable_from(cabinet.drawers)
    query = eql.count(cabinet_drawers).per(cabinet)
    result = list(query.evaluate())
    expected = [len(c.drawers) for c in world.views if isinstance(c, Cabinet)]
    assert [r[query] for r in result] == expected

    # without per should be all drawers of all cabinets
    query_all = eql.count(cabinet_drawers)
    results = list(query_all.evaluate())
    assert len(results) == 1
    result_all = results[0]
    expected_all = sum(len(c.drawers) for c in world.views if isinstance(c, Cabinet))
    assert result_all == expected_all


def test_max_count_per(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    cabinet_drawers = variable_from(cabinet.drawers)
    query = eql.max(eql.count(cabinet_drawers).per(cabinet))
    result = list(query.evaluate())
    assert len(result) == 1
    result_max = result[0][query]
    expected = 0
    for c in world.views:
        if isinstance(c, Cabinet) and len(c.drawers) > expected:
            expected = len(c.drawers)
    assert result_max == expected


def test_max_min_no_variable():
    values = [2, 1, 3, 5, 4]
    value = variable(int, domain=values)

    max_query = eql.max(entity(value))
    assert list(max_query.evaluate())[0] == max(values)

    min_query = eql.min(entity(value))
    assert list(min_query.evaluate())[0] == min(values)


def test_max_min_without_entity():
    values = [2, 1, 3, 5, 4]
    value = variable(int, domain=values)

    max_query = eql.max(value)
    assert list(max_query.evaluate())[0] == max(values)

    min_query = eql.min(value)
    assert list(min_query.evaluate())[0] == min(values)


def test_max_min_with_empty_list():
    empty_list = []
    value = variable(int, domain=empty_list)

    max_query = eql.max(entity(value))
    assert list(max_query.evaluate())[0] is None

    min_query = eql.min(entity(value))
    assert list(min_query.evaluate())[0] is None


@pytest.fixture
def departments_and_employees():
    d1 = Department("HR")
    d2 = Department("IT")
    d3 = Department("Finance")

    e1 = Employee("John", d1, 10000)
    e2 = Employee("Anna", d1, 20000)

    e3 = Employee("Anna", d2, 20000, 20000)
    e4 = Employee("Mary", d2, 30000, 30000)

    e5 = Employee("Peter", d3, 30000)
    e6 = Employee("Paul", d3, 40000)

    departments = [d1, d2, d3]
    employees = [e1, e2, e3, e4, e5, e6]
    return departments, employees


def test_average_with_condition(departments_and_employees):
    departments, employees = departments_and_employees

    emp = variable(Employee, domain=None)

    department = emp.department
    avg_salary = eql.average(
        entity(emp.salary).where(department.name.startswith("F"))
    ).per(department)
    query = eql.an(entity(department).where(avg_salary > 20000))
    results = list(query.evaluate())
    assert len(results) == 1
    assert results[0] == next(d for d in departments if d.name.startswith("F"))


def test_multiple_aggregations_per_group(departments_and_employees):
    departments, employees = departments_and_employees

    emp = variable(Employee, domain=None)
    # emp_of_F = eql.an(entity(emp).where(emp.department.name.startswith("F")))
    department = emp.department
    avg_salary = eql.average(emp.salary)
    avg_starting_salary = eql.average(emp.starting_salary)
    salaries = eql.a(
        set_of(avg_salary, avg_starting_salary, department).grouped_by(department)
    )
    # print(list(avg_salary.evaluate()))
    # print(list(avg_starting_salary.evaluate()))
    query = eql.an(
        entity(salaries[department]).where(
            salaries[avg_salary] == salaries[avg_starting_salary]
        )
    )
    results = list(query.evaluate())
    assert len(results) == 1
    assert results[0] == next(d for d in departments if d.name.startswith("I"))
