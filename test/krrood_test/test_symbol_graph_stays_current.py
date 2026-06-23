from dataclasses import dataclass

from krrood.symbol_graph.symbol_graph import Symbol, SymbolGraph


def test_class_diagram_includes_symbol_defined_after_first_build():
    """A ``Symbol`` subclass defined after the class diagram was first built must appear in it.

    The single class diagram is cached, so without invalidation a late-defined subclass is frozen
    out and every graph-backed feature silently ignores it.
    """
    graph = SymbolGraph()
    graph.class_diagram

    @dataclass(eq=False)
    class SymbolDefinedAfterFirstBuild(Symbol):
        value: int

        def __hash__(self) -> int:
            return id(self)

    graph.class_diagram.get_wrapped_class(SymbolDefinedAfterFirstBuild)


def test_class_diagram_identity_stable_without_new_symbols():
    """Repeated access returns the same diagram while no new ``Symbol`` subclass is defined."""
    graph = SymbolGraph()
    assert graph.class_diagram is graph.class_diagram
