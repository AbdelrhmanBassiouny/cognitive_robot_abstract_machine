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
1.  **[Architecture Overview](architecture_overview.md)**: A high-level view of the system's design, focusing on the separation between builders and execution graphs.
2.  **[Expression Hierarchy](expression_hierarchy.md)**: An exploration of the symbolic structure and the base classes for all EQL operations.
3.  **[Variable System](variable_system.md)**: A deep dive into how symbolic variables and domains are handled internally.
4.  **[Execution Engine](execution_engine.md)**: Details on the mechanics of query evaluation and result binding.
5.  **[Graph and Visualization](graph_and_visualization.md)**: Tools and techniques for debugging and visualizing query plans and execution graphs.
6.  **[Inference Explanation Internals](inference_explanation.md)**: How the `InferenceExplanation` system is implemented, including the observer pipeline, Symbol inheritance design, weakref lifecycle management, and the `lru_cache` memory-leak fix.
7.  **[Verbalization Internals](verbalization.md)**: How the EQL verbalization pipeline works, including the fragment type hierarchy, rule dispatch via MRO-depth sorting, `VerbalizationContext` state management, source reference linking, and how to extend the system with new rules or output formats.
8.  **[Conclusion-Asking Internals](eql_rdr_conclusion_asking.md)**: The SOLID split behind no-ground-truth fitting — how `Expert`, `ExpertInterface`, `ConclusionDomain`, and `ConclusionAid` collaborate, the UNSET sentinel, the layered validator, and how to add new aids or I/O back-ends.
9.  **[@rdr Decorator Internals](rdr_decorator.md)**: How the `@rdr` decorator generates FunctionCase subclasses from function signatures, the load-or-generate lifecycle, auto-save mechanics, and extension points.