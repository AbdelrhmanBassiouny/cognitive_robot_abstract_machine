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

# Developer Guide
If you are interested in the internals of EQL or wish to extend it:
1.  **[Architecture Overview](../developer/architecture_overview.md)**: A high-level view of the system's design, focusing on the separation between builders and execution graphs.
2.  **[Expression Hierarchy](../developer/expression_hierarchy.md)**: An exploration of the symbolic tree structure and the base classes for all EQL operations.
3.  **[Variable System](../developer/variable_system.md)**: A deep dive into how symbolic variables and domains are handled internally.
4.  **[Execution Engine](../developer/execution_engine.md)**: Details on the mechanics of query evaluation and result binding.
5.  **[Graph and Visualization](../developer/graph_and_visualization.md)**: Tools and techniques for debugging and visualizing query plans and execution graphs.