import pytest

import krrood.entity_query_language.entity_result_processors as eql
from krrood.entity_query_language.entity import (
    entity,
    let, set_of, )
from krrood.entity_query_language.failures import UnquantifiedMatchError
from krrood.entity_query_language.match import (
    matching,
    match_any,
    select,
    match_all,
)
from krrood.entity_query_language.predicate import HasType
from krrood.entity_query_language.entity_result_processors import the, a, count
from krrood.entity_query_language.symbolic import UnificationDict, SetOf
from ..dataset.semantic_world_like_classes import (
    FixedConnection,
    Container,
    Handle,
    Cabinet,
    Drawer,
)


def test_match(handles_and_containers_world):
    world = handles_and_containers_world

    fixed_connection_query = the(
        matching(FixedConnection)(
            parent=matching(Container)(name="Container1"),
            child=matching(Handle)(name="Handle1"),
        ).from_(world.connections)
    )

    fixed_connection_query_manual = the(
        entity(
            fc := let(FixedConnection, domain=None),
            HasType(fc.parent, Container),
            HasType(fc.child, Handle),
            fc.parent.name == "Container1",
            fc.child.name == "Handle1",
        )
    )

    fixed_connection = fixed_connection_query.evaluate()
    fixed_connection_manual = fixed_connection_query_manual.evaluate()
    assert fixed_connection == fixed_connection_manual
    assert isinstance(fixed_connection, FixedConnection)
    assert fixed_connection.parent.name == "Container1"
    assert isinstance(fixed_connection.child, Handle)
    assert fixed_connection.child.name == "Handle1"


def test_select(handles_and_containers_world):
    world = handles_and_containers_world

    # Method 1
    fixed_connection = the(matching(FixedConnection)(
        parent=matching(Container)(name="Container1"),
        child=matching(Handle)(name="Handle1"),
    ).from_(world.connections))
    container_and_handle = select(container := fixed_connection.parent,
                                  handle := fixed_connection.child)

    # Method 2
    fixed_connection_2 = let(FixedConnection, domain=world.connections)
    container_and_handle_2 = the(
        set_of((container_2 := fixed_connection_2.parent, handle_2 := fixed_connection_2.child),
               HasType(container_2, Container),
               HasType(handle_2, Handle),
               container_2.name == "Container1",
               handle_2.name == "Handle1",
               ))

    assert set(container_and_handle_2.evaluate().values()) == set(container_and_handle.evaluate().values())
    assert isinstance(container_and_handle.expression._child_, SetOf)

    answers = container_and_handle.evaluate()
    assert isinstance(answers, UnificationDict)
    assert answers[container].name == "Container1"
    assert answers[handle].name == "Handle1"


def test_select_where(handles_and_containers_world):
    world = handles_and_containers_world

    # Method 1
    fixed_connection = the(matching(FixedConnection)(
        parent=matching(Container),
        child=matching(Handle),
    ).from_(world.connections))
    container_and_handle = select(container := fixed_connection.parent,
                                  handle := fixed_connection.child).where(container.size > 1)

    # Method 2
    fixed_connection_2 = let(FixedConnection, domain=world.connections)
    container_and_handle_2 = the(
        set_of((container_2 := fixed_connection_2.parent, handle_2 := fixed_connection_2.child),
               HasType(container_2, Container),
               HasType(handle_2, Handle),
               container_2.size > 1
               ))

    assert set(container_and_handle_2.evaluate().values()) == set(container_and_handle.evaluate().values())
    assert isinstance(container_and_handle.expression._child_, SetOf)

    answers = container_and_handle.evaluate()
    assert isinstance(answers, UnificationDict)
    assert answers[container].name == "Container3"
    assert answers[handle].name == "Handle3"


@pytest.fixture
def world_and_cabinets_and_specific_drawer(handles_and_containers_world):
    world = handles_and_containers_world
    my_drawer = Drawer(handle=Handle("Handle2"), container=Container("Container1"))
    drawers = list(filter(lambda v: isinstance(v, Drawer), world.views))
    my_cabinet_1 = Cabinet(
        container=Container("container2"), drawers=[my_drawer] + drawers
    )
    my_cabinet_2 = Cabinet(container=Container("container2"), drawers=[my_drawer])
    my_cabinet_3 = Cabinet(container=Container("container2"), drawers=drawers)
    return world, [my_cabinet_1, my_cabinet_2, my_cabinet_3], my_drawer


def test_match_any(world_and_cabinets_and_specific_drawer):
    world, cabinets, my_drawer = world_and_cabinets_and_specific_drawer
    cabinet = a(matching(Cabinet)(drawers=match_any([my_drawer])).from_(cabinets))
    found_cabinets = list(cabinet.evaluate())
    assert len(found_cabinets) == 2
    assert cabinets[0] in found_cabinets
    assert cabinets[1] in found_cabinets


def test_match_all(world_and_cabinets_and_specific_drawer):
    world, cabinets, my_drawer = world_and_cabinets_and_specific_drawer
    cabinet = the(matching(Cabinet)(drawers=match_all([my_drawer])).from_(cabinets))
    found_cabinet = cabinet.evaluate()
    assert found_cabinet is cabinets[1]


def test_match_any_on_collection_returns_unique_parent_entities():
    # setup from the notebook example
    c1 = Container("Container1")
    other_c = Container("ContainerX")
    h1 = Handle("Handle1")

    drawer1 = Drawer(handle=h1, container=c1)
    drawer2 = Drawer(handle=Handle("OtherHandle"), container=other_c)
    cabinet1 = Cabinet(container=c1, drawers=[drawer1, drawer2])
    cabinet2 = Cabinet(container=other_c, drawers=[drawer2])
    views = [drawer1, drawer2, cabinet1, cabinet2]

    q = a(matching(Cabinet)(drawers=match_any([drawer1, drawer2])).from_(views))

    results = list(q.evaluate())
    # Expect exactly the two cabinets, no duplicates
    assert len(results) == 2
    assert {id(x) for x in results} == {id(cabinet1), id(cabinet2)}


def test_count_wih_match(handles_and_containers_world):
    world = handles_and_containers_world
    fixed_connections = a(matching(FixedConnection).from_(world.connections))
    assert count(fixed_connections).evaluate() == len([con for con in world.connections if isinstance(con, FixedConnection)])


def test_max_with_match(handles_and_containers_world):
    world = handles_and_containers_world
    assert eql.max(entity(let(Container, world.bodies).size)).evaluate() == 2
    container = a(matching(Container).from_(world.bodies))
    max_size_container = select(eql.max(container.size)).evaluate()
    assert max_size_container == 2

def test_unquantified_match_error(handles_and_containers_world):
    world = handles_and_containers_world
    container = matching(Container).from_(world.bodies)
    with pytest.raises(UnquantifiedMatchError):
        container.size
