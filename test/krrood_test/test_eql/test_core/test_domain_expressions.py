"""
Tests for variables whose domain is an expression: the variable ranges, for each binding
of the expression, over the elements of the value it evaluates to.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import (
    a,
    an,
    set_of,
    variable,
    variable_from,
)

from ...dataset.semantic_world_like_classes import (
    Body,
    Container,
    Connection,
    FixedConnection,
    Handle,
    PrismaticConnection,
    World,
)

# %% fixtures


@dataclass
class TwoWorlds:
    """
    Two worlds, each with one fixed and one prismatic connection of its own.
    """

    first: World
    """
    The first world.
    """

    second: World
    """
    The second world.
    """

    @property
    def worlds(self) -> list[World]:
        """
        :return: Both worlds, the first one first.
        """
        return [self.first, self.second]


def world_with_connections(identifier: int) -> World:
    """
    :param identifier: The identifier of the world.
    :return: A world with a fixed and a prismatic connection between a container and a
        handle.
    """
    container = Container(f"container {identifier}")
    handle = Handle(f"handle {identifier}")
    return World(
        id=identifier,
        bodies=[container, handle],
        connections=[
            FixedConnection(parent=container, child=handle),
            PrismaticConnection(parent=container, child=handle),
        ],
    )


@pytest.fixture
def two_worlds() -> TwoWorlds:
    """
    :return: Two fresh worlds for each test.
    """
    return TwoWorlds(first=world_with_connections(1), second=world_with_connections(2))


# %% typed domains


def test_variable_ranges_over_the_elements_of_its_domain_expression(two_worlds):
    world = variable(World, two_worlds.worlds)

    result = a(variable(Connection, world.connections)).tolist()

    assert result == [*two_worlds.first.connections, *two_worlds.second.connections]


def test_variable_keeps_only_the_elements_of_its_type(two_worlds):
    world = variable(World, two_worlds.worlds)

    result = a(variable(FixedConnection, world.connections)).tolist()

    assert result == [
        two_worlds.first.connections[0],
        two_worlds.second.connections[0],
    ]


def test_each_element_is_bound_with_the_binding_it_came_from(two_worlds):
    world = variable(World, two_worlds.worlds)
    connection = variable(FixedConnection, world.connections)

    result = set_of(world, connection).tolist()

    assert [(row[world], row[connection]) for row in result] == [
        (two_worlds.first, two_worlds.first.connections[0]),
        (two_worlds.second, two_worlds.second.connections[0]),
    ]


def test_domain_expression_can_be_filtered_by_its_elements(two_worlds):
    world = variable(World, two_worlds.worlds)
    body = variable(Body, world.bodies)

    result = an(body).where(body.name == "handle 2").tolist()

    assert result == [two_worlds.second.bodies[1]]


# %% untyped domains


def test_variable_from_an_expression_ranges_over_its_elements(two_worlds):
    world = variable(World, two_worlds.worlds)

    result = a(variable_from(world.bodies)).tolist()

    assert result == [*two_worlds.first.bodies, *two_worlds.second.bodies]


def test_variable_from_an_expression_keeps_values_that_are_not_collections(
    two_worlds,
):
    body = variable(Body, two_worlds.first.bodies)

    result = a(variable_from(body.name)).tolist()

    assert result == [live_body.name for live_body in two_worlds.first.bodies]
