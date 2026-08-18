"""
Tests that segmind events and detectors are Symbols: their instances are tracked in
krrood's SymbolGraph and can be queried through the entity query language.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.factories import an, entity, variable
from krrood.symbol_graph.symbol_graph import Symbol, SymbolGraph

from segmind.datastructures.events import DetectionEvent, SupportEvent
from segmind.detectors.atomic_event_detectors_nodes import ContactDetector
from segmind.detectors.base import AbstractDetector
from semantic_digital_twin.world_description.world_entity import Body


@pytest.fixture(autouse=True)
def fresh_symbol_graph():
    """
    Give each test its own SymbolGraph so instances created elsewhere in the test
    session do not leak into the assertions.
    """
    SymbolGraph.clear()
    SymbolGraph(packages=["segmind", "krrood", "semantic_digital_twin", "giskardpy"])
    yield
    SymbolGraph.clear()


# %% events are symbols
class TestEventsAreSymbols:
    """
    Every detection event is a :class:`Symbol`, so its instances are tracked in the
    SymbolGraph and can be found by an entity query with the SymbolGraph as the implicit
    domain.
    """

    def test_every_event_is_a_symbol(self):
        assert issubclass(DetectionEvent, Symbol)

    def test_a_new_event_is_tracked_by_the_symbol_graph(self):
        event = SupportEvent(tracked_object=Body())

        instances = list(SymbolGraph().get_instances_of_type(SupportEvent))

        assert instances == [event]
        assert instances[0] is event

    def test_an_event_answers_an_entity_query_over_its_type(self):
        event = SupportEvent(tracked_object=Body())

        query = an(entity(variable(SupportEvent, domain=None)))
        results = list(query.evaluate())

        assert results == [event]
        assert results[0] is event


# %% detectors are symbols
class TestDetectorsAreSymbols:
    """
    Every detector is a :class:`Symbol`, so its instances are tracked in the SymbolGraph
    and can be found by an entity query with the SymbolGraph as the implicit domain.
    """

    def test_every_detector_is_a_symbol(self):
        assert issubclass(AbstractDetector, Symbol)

    def test_a_new_detector_is_tracked_by_the_symbol_graph(self):
        detector = ContactDetector()

        instances = list(SymbolGraph().get_instances_of_type(ContactDetector))

        assert instances == [detector]
        assert instances[0] is detector

    def test_a_detector_answers_an_entity_query_over_its_type(self):
        detector = ContactDetector()

        query = an(entity(variable(ContactDetector, domain=None)))
        results = list(query.evaluate())

        assert results == [detector]
        assert results[0] is detector
