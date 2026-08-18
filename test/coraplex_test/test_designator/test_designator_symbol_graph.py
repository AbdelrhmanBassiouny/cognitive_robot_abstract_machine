"""
Tests that coraplex designators are Symbols: their instances are tracked in krrood's
SymbolGraph and can be queried through the entity query language.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.factories import an, entity, variable
from krrood.symbol_graph.symbol_graph import Symbol, SymbolGraph

from coraplex.plans.designator import Designator
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from semantic_digital_twin.spatial_types.spatial_types import Pose


@pytest.fixture(autouse=True)
def fresh_symbol_graph():
    """
    Give each test its own SymbolGraph so instances created elsewhere in the test
    session do not leak into the assertions.
    """
    SymbolGraph.clear()
    SymbolGraph(packages=["coraplex", "krrood", "semantic_digital_twin"])
    yield
    SymbolGraph.clear()


# %% designators are symbols
class TestDesignatorsAreSymbols:
    """
    Every designator (and with it every action) is a :class:`Symbol`, so its instances
    are tracked in the SymbolGraph and take part in symbol-level reasoning.
    """

    def test_every_designator_is_a_symbol(self):
        assert issubclass(Designator, Symbol)

    def test_every_action_is_a_symbol(self):
        assert issubclass(ActionDescription, Symbol)

    def test_a_new_action_is_tracked_by_the_symbol_graph(self):
        action = NavigateAction(target_location=Pose())

        instances = list(SymbolGraph().get_instances_of_type(ActionDescription))

        assert instances == [action]
        assert instances[0] is action


# %% actions are queryable
class TestActionsAreQueryable:
    """
    An action instance can be found by an entity query ranging over its type, with the
    SymbolGraph as the implicit domain.
    """

    def test_an_action_answers_an_entity_query_over_its_type(self):
        action = NavigateAction(target_location=Pose())

        query = an(entity(variable(NavigateAction, domain=None)))
        results = list(query.evaluate())

        assert results == [action]
        assert results[0] is action
