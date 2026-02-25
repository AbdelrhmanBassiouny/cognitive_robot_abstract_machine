---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Graph and Visualization

EQL represents queries as Directed Acyclic Graphs (DAGs). While this graph is primarily used for internal execution, EQL provides tools to visualize these structures for debugging and educational purposes.

## The `QueryGraph`

Unlike previous versions of EQL, there is no longer a global singleton graph. Each query now constructs its own local {py:class}`~krrood.entity_query_language.query_graph.QueryGraph` during the building phase.

### Key Features:
- **Local Scope**: Every query has its own graph, preventing side effects between different queries.
- **Node-Edge Structure**: Each {py:class}`~krrood.entity_query_language.core.base_expressions.SymbolicExpression` is a node, and relationships (like child-parent) are edges.

```{hint}
You can access a query's graph after it has been built to inspect its structure.
```

## Visualization with `rustworkx`

EQL uses the `rustworkx` library as an optional dependency to provide high-performance graph layout and rendering.

### The `.visualize()` Method
If you have `rustworkx` and `matplotlib` installed, you can visualize any query or expression.

```python
# Create a query graph from an expression
from krrood.entity_query_language.query_graph import QueryGraph
graph = QueryGraph(query)

# Render the graph
graph.visualize()
```

```{note}
The visualization layer uses a "tidy" layout by default, which is optimized for tree-like structures common in EQL queries.
```

## Color Coding and Legends

The {py:class}`~krrood.entity_query_language.query_graph.ColorLegend` class provides automatic color-coding for different types of nodes.

## Full Example: Visualizing a Structural Match

This example shows how to generate a visualization for a nested structural query.

```{code-cell} ipython3
from krrood.entity_query_language.factories import match_variable, match, entity, an
from krrood.entity_query_language.query_graph import QueryGraph
from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class Robot:
    name: str
    battery: int
    
robots = [Robot("R2D2", 100), Robot("C3PO", 0)]

# Define a complex nested query
query = match_variable(Robot, domain=robots)(name="R2D2", battery=100)

# Visualize
query_graph = QueryGraph(query)

# Note: This requires rustworkx and matplotlib
# query_graph.visualize()

print("Graph constructed with", len(query_graph.graph.nodes()), "nodes.")
```

<iframe src="../../_static/files/match_query_graph.pdf"
        width="100%"
        height="600px">
</iframe>

## API Reference
- {py:class}`~krrood.entity_query_language.query_graph.QueryGraph`
- {py:class}`~krrood.entity_query_language.query_graph.QueryNode`
- {py:class}`~krrood.entity_query_language.query_graph.ColorLegend`
