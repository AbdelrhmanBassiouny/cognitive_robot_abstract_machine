"""
Evaluate a query on a thread other than the main one and report whether that thread ends.

Meant to be run as a script in a fresh interpreter: evaluating a query loads the backend
module, and only the load that finds it missing reaches the behaviour under test. Exits with
status 0 when the worker thread could be joined and 1 when it stayed alive after its target
had returned.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass

from krrood.entity_query_language.factories import an, entity, variable
from krrood.symbol_graph.symbol_graph import Symbol

JOIN_TIMEOUT_IN_SECONDS = 120.0
"""
How long to wait for the worker thread, generously above the time the backend module takes to
load, so that a timeout means the thread will never end rather than that it is still busy.
"""

SHAPE_COUNT = 4
"""
How many shapes the query selects from; every second one is inserted.
"""


@dataclass(unsafe_hash=True)
class Shape(Symbol):
    """
    A shape the query can select.
    """

    name: str
    """
    What the shape is called.
    """

    inserted: bool
    """
    Whether the shape sits in its hole.
    """


def evaluate_query():
    """
    Evaluate a query selecting the inserted shapes, keeping them alive for its duration.
    """
    shapes = [Shape(f"shape_{index}", index % 2 == 0) for index in range(SHAPE_COUNT)]
    query = an(entity(shape := variable(Shape)).where(shape.inserted == True))
    assert len(list(query.evaluate())) == len(shapes) // 2


worker = threading.Thread(target=evaluate_query, daemon=True)
worker.start()
worker.join(JOIN_TIMEOUT_IN_SECONDS)
sys.exit(1 if worker.is_alive() else 0)
