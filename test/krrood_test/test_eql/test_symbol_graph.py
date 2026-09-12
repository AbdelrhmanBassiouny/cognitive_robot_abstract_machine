import os
import sys
import threading
import time

import pytest

from krrood.entity_query_language.factories import entity, variable, an
from krrood.symbol_graph.symbol_graph import SymbolGraph
from ..dataset.example_classes import KRROODPosition

try:
    import pydot
    import pygraphviz
except ImportError:
    pydot = None
    pygraphviz = None


@pytest.mark.skipif(
    not (pydot and pygraphviz), reason="pydot and graphviz not installed"
)
def test_visualize_symbol_graph():
    SymbolGraph().clear()
    symbol_graph = SymbolGraph()
    symbol_graph.to_dot("symbol_graph.svg", format_="svg", graph_type="type")
    assert len(symbol_graph._class_diagram.wrapped_classes) >= 59
    if os.path.exists("symbol_graph.svg"):
        os.remove("symbol_graph.svg")


def test_memory_leak():
    """
    Test if the SymbolGraph does not artificially keep objects alive that would be
    garbage collected.
    """

    def create_data():
        point = KRROODPosition(1, 2, 3)
        return point

    create_data()

    q = an(entity(variable(KRROODPosition, domain=None)))
    result = list(q.evaluate())

    assert result == []

    assert len(SymbolGraph().wrapped_instances) == 0


# %% two threads at once

SWEEPING_SECONDS = 2.0
"""
How long the threads race over the graph.
"""

INSTANCES_PER_BURST = 50
"""
How many instances a filling thread makes and drops at once, so the graph holds many
dead nodes for the sweeps to meet on.
"""

FILLING_THREADS = 2
"""
How many threads fill the graph while it is swept.
"""

SWEEPING_THREADS = 4
"""
How many threads sweep the graph at once.
"""

SWITCH_INTERVAL_SECONDS = 1e-6
"""
How often the interpreter hands the threads over while they race, so the race is run
many times over rather than left to chance.
"""


def test_the_graph_survives_being_swept_by_two_threads_while_a_third_fills_it():
    """
    Every query evaluation sweeps the dead instances out of the graph, and a perception
    node answers queries on its own thread while the run asks its own: two sweeps at
    once found the same dead node and the second could not remove it.
    """
    SymbolGraph().clear()
    stop = threading.Event()
    failures: list[BaseException] = []
    usual_switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(SWITCH_INTERVAL_SECONDS)

    def fill() -> None:
        while not stop.is_set():
            [KRROODPosition(1, 2, 3) for _ in range(INSTANCES_PER_BURST)]

    def sweep() -> None:
        try:
            while not stop.is_set():
                SymbolGraph().remove_dead_instances()
        except BaseException as failure:
            failures.append(failure)

    threads = [threading.Thread(target=fill) for _ in range(FILLING_THREADS)] + [
        threading.Thread(target=sweep) for _ in range(SWEEPING_THREADS)
    ]
    for thread in threads:
        thread.start()
    time.sleep(SWEEPING_SECONDS)
    stop.set()
    for thread in threads:
        thread.join()
    sys.setswitchinterval(usual_switch_interval)

    assert failures == []
