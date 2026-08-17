"""
How the symbol graph keeps track of the instances it caches, while they are created and
after they died.
"""

import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from krrood.symbol_graph.symbol_graph import SymbolGraph

from .dataset.example_classes import KRROODPosition

# %% racing threads

THREAD_COUNT = 2
"""
How many threads share the symbol graph singleton at once.
"""

ROUNDS_PER_THREAD = 300
"""
How often each thread creates a batch of symbols and then clears out the dead ones.
"""

SYMBOLS_PER_ROUND = 50
"""
How many symbols one round creates and drops again.
"""

FAST_THREAD_SWITCH_INTERVAL = 1e-6
"""
Seconds the interpreter runs one thread before offering the others a turn, short enough
that the threads interleave inside the graph's bookkeeping rather than around it.
"""


@pytest.fixture
def rapid_thread_switching():
    """
    Make the interpreter switch between threads often, so an interleaving that a race
    depends on is actually reached.
    """
    original_interval = sys.getswitchinterval()
    sys.setswitchinterval(FAST_THREAD_SWITCH_INTERVAL)
    yield
    sys.setswitchinterval(original_interval)


def _create_and_drop_symbols() -> None:
    """
    Create symbols that die immediately and clear them out of the graph again, over and
    over.
    """
    for _ in range(ROUNDS_PER_THREAD):
        for value in range(SYMBOLS_PER_ROUND):
            KRROODPosition(value, value, value)
        SymbolGraph().remove_dead_instances()


def test_dead_instances_are_removed_once_when_threads_share_the_graph(
    rapid_thread_switching,
):
    """
    Two threads clearing dead instances out of the shared graph must not each try to
    remove the same instance from the per-type cache.
    """
    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        for finished in [
            pool.submit(_create_and_drop_symbols) for _ in range(THREAD_COUNT)
        ]:
            finished.result()

    SymbolGraph().remove_dead_instances()

    assert list(SymbolGraph().get_instances_of_type(KRROODPosition)) == []


# %% the index from instance id to wrapper


def test_removing_a_dead_instance_drops_its_entry_from_the_instance_index():
    """
    The index that maps an instance's id to its wrapper must not keep the wrapper of an
    instance that died, or the graph grows for as long as the process runs.
    """
    symbol_graph = SymbolGraph()
    symbol_graph.remove_dead_instances()
    indexed_before = len(symbol_graph._instance_index)

    KRROODPosition(1, 2, 3)
    symbol_graph.remove_dead_instances()

    assert len(symbol_graph._instance_index) == indexed_before
