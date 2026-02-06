import pytest

import krrood.entity_query_language.entity_result_processors as eql
from krrood.entity_query_language.entity_result_processors import an, a
from krrood.entity_query_language.entity import (
    variable,
    variable_from,
    entity,
    set_of,
    contains,
)
from krrood.entity_query_language.failures import (
    NonAggregatedSelectedVariablesError,
    AggregatorInWhereConditionsError,
)
from ..dataset.department_and_employee import Department, Employee
from ..dataset.semantic_world_like_classes import Cabinet, Body


def test_count(handles_and_containers_world):
    world = handles_and_containers_world
    body = variable(type_=Body, domain=world.bodies)
    query = an(
        entity(eql.count(body)).where(
            contains(body.name, "Handle"),
        )
    )
    assert list(query.evaluate())[0] == len(
        [b for b in world.bodies if "Handle" in b.name]
    )


def test_sum(handles_and_containers_world):
    heights = [1, 2, 3, 4, 5]
    heights_var = variable(int, domain=heights)
    query = an(entity(eql.sum(heights_var)))
    assert list(query.evaluate())[0] == sum(heights)


def test_average(handles_and_containers_world):
    heights = [1, 2, 3, 4, 5]
    heights_var = variable(int, domain=heights)
    query = an(entity(eql.average(heights_var)))
    assert list(query.evaluate())[0] == sum(heights) / len(heights)


def test_sum_on_empty_list(handles_and_containers_world):
    empty_list = []
    empty_var = variable(int, domain=empty_list)
    query = an(entity(eql.sum(empty_var)))
    assert len(list(query.evaluate())) == 0


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


def test_non_aggregated_conditions_with_aggregated_ones(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)
    query = a(
        set_of(cabinet, eql.max(drawer.handle.name))
        .where(cabinet.container.name.startswith("C"))
        .grouped_by(cabinet)
    )
    _ = list(query.evaluate())
    with pytest.raises(AggregatorInWhereConditionsError):
        query = a(
            set_of(cabinet, max_handle_name := eql.max(drawer.handle.name))
            .where(max_handle_name.startswith("H"))
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


def test_having_with_max(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)

    query = a(
        set_of(
            cabinet,
            drawer_count := eql.count(drawer),
            eql.max(drawer, key=lambda d: d.handle.name),
        )
        .grouped_by(cabinet)
        .having(drawer_count > 1)
    )
    query.visualize()
    results = list(query.evaluate())
    assert len(results) == 1


def test_multiple_grouped_variables(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)

    # Group by both cabinet and drawer (silly, but tests multiple variables)
    query = a(set_of(cabinet, count:= eql.count(drawer), drawer).grouped_by(cabinet, drawer))
    results = list(query.evaluate())

    # Each result should have count=1 because each (cabinet, drawer) pair is unique here
    for res in results:
        assert res[count] == 1
        assert res[cabinet] is not None
        assert res[drawer] is not None


def test_sum_grouped_by(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    drawer = variable_from(cabinet.drawers)
    # Give drawers a numeric property to sum. They don't have one, but we can use a key func.
    # Let's sum the length of handle names per cabinet.

    query = a(set_of(total_characters:=eql.sum(drawer, key=lambda d: len(d.handle.name)), cabinet).grouped_by(cabinet))
    results = list(query.evaluate())

    expected_cabinets = [c for c in world.views if isinstance(c, Cabinet)]
    assert len(results) == len(expected_cabinets)

    for res in results:
        c = res[cabinet]
        s = res[total_characters]
        assert s == sum(len(d.handle.name) for d in c.drawers)


def test_count_grouped_by(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    cabinet_drawers = variable_from(cabinet.drawers)
    query = an(entity(eql.count(cabinet_drawers)).grouped_by(cabinet))
    result = list(query.evaluate())
    expected = [len(c.drawers) for c in world.views if isinstance(c, Cabinet)]
    assert result == expected

    # without grouped_by should be all drawers of all cabinets
    query_all = an(entity(eql.count(cabinet_drawers)))
    results = list(query_all.evaluate())
    assert len(results) == 1
    result_all = results[0]
    expected_all = sum(len(c.drawers) for c in world.views if isinstance(c, Cabinet))
    assert result_all == expected_all


def test_max_count_grouped_by(handles_and_containers_world):
    world = handles_and_containers_world
    cabinet = variable(Cabinet, domain=world.views)
    cabinet_drawers = variable_from(cabinet.drawers)
    count_query = an(entity(eql.count(cabinet_drawers)).grouped_by(cabinet))
    query = an(entity(eql.max(count_query)))
    # query = an(entity(eql.max(eql.count(cabinet_drawers)).grouped_by(cabinet)))
    result = list(query.evaluate())
    assert len(result) == 1
    result_max = result[0]
    expected = 0
    for c in world.views:
        if isinstance(c, Cabinet) and len(c.drawers) > expected:
            expected = len(c.drawers)
    assert result_max == expected


def test_max_min_no_variable():
    values = [2, 1, 3, 5, 4]
    value = variable(int, domain=values)

    max_query = an(entity(eql.max(entity(value))))
    assert list(max_query.evaluate())[0] == max(values)

    min_query = an(entity(eql.min(entity(value))))
    assert list(min_query.evaluate())[0] == min(values)


def test_max_min_without_entity():
    values = [2, 1, 3, 5, 4]
    value = variable(int, domain=values)

    max_query = an(entity(eql.max(value)))
    assert list(max_query.evaluate())[0] == max(values)

    min_query = an(entity(eql.min(value)))
    assert list(min_query.evaluate())[0] == min(values)


def test_max_min_with_empty_list():
    empty_list = []
    value = variable(int, domain=empty_list)

    max_query = an(entity(eql.max(entity(value))))
    assert len(list(max_query.evaluate())) == 0

    min_query = an(entity(eql.min(entity(value))))
    assert len(list(min_query.evaluate())) == 0


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
    query = a(
        set_of(department, avg_salary := eql.average(emp.salary))
        .where(department.name.startswith("F"))
        .grouped_by(department)
        .having(avg_salary > 20000)
    )
    query.visualize()
    results = list(query.evaluate())
    assert len(results) == 1
    assert results[0][department] == next(
        d for d in departments if d.name.startswith("F")
    )


def test_multiple_aggregations_per_group(departments_and_employees):
    departments, employees = departments_and_employees

    emp = variable(Employee, domain=None)
    department = emp.department
    avg_salary = eql.average(emp.salary)
    avg_starting_salary = eql.average(emp.starting_salary)
    query = a(
        set_of(avg_salary, avg_starting_salary, department)
        .grouped_by(department)
        .having(avg_salary == avg_starting_salary)
    )
    results = list(query.evaluate())
    assert len(results) == 1
    assert results[0][department] == next(
        d for d in departments if d.name.startswith("I")
    )


def test_having_node_hierarchy(departments_and_employees):
    from krrood.entity_query_language.symbolic import Having, GroupBy

    emp = variable(Employee, domain=None)
    department = emp.department
    avg_salary = eql.average(emp.salary)

    query = a(
        set_of(department, avg_salary).grouped_by(department).having(avg_salary > 20000)
    )

    descriptor = query._child_
    # Graph hierarchy check
    assert isinstance(descriptor._child_, Having)
    assert isinstance(descriptor._child_.group_by, GroupBy)
    assert descriptor._child_.conditions._name_ == ">"


def test_complex_having_success(departments_and_employees):
    departments, employees = departments_and_employees
    emp = variable(Employee, domain=None)
    department = emp.department
    avg_salary = eql.average(emp.salary)

    query = a(
        set_of(department, avg_salary).grouped_by(department).having(avg_salary > 30000)
    )

    results = list(query.evaluate())
    # Should only return Finance department (avg 35000)
    assert len(results) == 1
    assert results[0][department].name == "Finance"
