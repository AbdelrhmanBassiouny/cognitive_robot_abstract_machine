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

# Introduction to EQL

Entity Query Language (EQL) is a Pythonic, intuitive, and expressive relational query language. It is not only a query
language, but also a description language that lets you write description-logic-style statements directly in Python. You
can also use any user-defined Python function inside a query.

Unlike SQL, EQL does not require explicit joins. It works naturally with Python’s built-in data structures, which can be
nested arbitrarily.

EQL operates directly on user-defined objects, without the need for an additional representation layer such as an 
Object-Relational Mapper (ORM).

The core idea behind EQL is simple: express your intent with minimal extra detail. If you want to find an object with
certain properties, you describe it directly using standard Python syntax.

## The "Hello World" of EQL

Let's start with a simple example: finding a specific body in a "world".

### 1. Define your domain model
EQL works seamlessly with standard Python dataclasses.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class Body:
    name: str

@dataclass
class World:
    bodies: List[Body]
```

### 2. Prepare some data
```python
world = World(bodies=[Body("Robot"), Body("Human")])
```

### 3. Build and run the query
We want to find a body named "Robot".

```python
from krrood.entity_query_language.factories import entity, variable, an

# 1. Define a symbolic variable representing any Body from world.bodies
body = variable(Body, domain=world.bodies)

# 2. Create a query: we want "an" entity "body" WHERE "body.name" is "Robot"
query = an(entity(body).where(body.name == "Robot"))

# 3. Evaluate the query to get results
results = list(query.evaluate())
print(results)
```

## Bit-by-Bit Explanation

*   **`variable(Body, domain=world.bodies)`**: This creates a symbolic placeholder. It tells EQL that we are interested
in objects of type `Body` that are found in the `world.bodies` collection. See {py:func}`~krrood.entity_query_language.factories.variable`.
*   **`entity(body)`**: This starts the selection. We are saying "I want to select the objects represented by the `body`
variable". See {py:func}`~krrood.entity_query_language.factories.entity`.
*   **`.where(body.name == "Robot")`**: This adds a filter. Notice how we use standard Python comparison operators. EQL
captures these and translates them into symbolic constraints.
*   **`an(...)`**: This is an optional result quantifier. It tells EQL that we expect zero or more results. If no
quantifier is provided, `an()` is assumed. See {py:func}`~krrood.entity_query_language.factories.an`.
*   **`.evaluate()`**: This triggers the execution engine. It returns a generator of results that satisfy all conditions.

📝 **Note**: All logic in EQL is deferred. The query is only executed when you call `.evaluate()` and iterate over it,
or when you call `.tolist()`, or `.first()`.

## Full Example

```{code-cell} ipython3
from dataclasses import dataclass
from typing import List
from krrood.entity_query_language.factories import entity, variable, an

@dataclass
class Body:
    name: str

@dataclass
class World:
    bodies: List[Body]

world = World(bodies=[Body("Robot"), Body("Human")])

# Define the variable and build the query
body = variable(Body, domain=world.bodies)
query = an(entity(body).where(body.name == "Robot"))

# Execute and print results
for result in query.evaluate():
    print(f"Found: {result.name}")
```

## Automatic Domain Discovery with Symbol

EQL provides a mechanism to automatically discover the domain of a variable. This is especially useful when 
your objects are part of a global state.

### Caching with `Symbol`
By inheriting from `Symbol`, instances of your classes are automatically cached in a graph called the `SymbolGraph`. 
This allows EQL to automatically create the domain if no explicit domain is provided for your variables.

```{code-cell} ipython3
from dataclasses import dataclass
from krrood.entity_query_language.factories import entity, variable, Symbol, an

@dataclass
class Body(Symbol):
    name: str

# Instances are automatically cached in SymbolGraph upon creation
robot = Body("Robot")
human = Body("Human")

# No explicit domain provided to variable(); it's inferred from SymbolGraph
body = variable(Body)
query = an(entity(body).where(body.name == "Robot"))

for result in query.evaluate():
    print(f"Found: {result.name}")
```

## Documentation Roadmap

The EQL documentation is organized into two main paths: one for users who want to query their data, and one for developers who want to understand or extend the core engine.

### User Guide
For most users, we recommend following the documentation in this order:
1.  **[Writing Basic Queries](writing_queries.md)**: Learn the fundamentals of EQL, including defining variables, selecting entities, and applying basic filters.
2.  **[Mapped Variables and Attribute Access](mapped_variable.md)**: Discover how to traverse object relationships, access attributes symbolically, and handle nested data collections.
3.  **[EQL for SQL Experts](eql_for_sql_experts.md)**: A comparative guide for those with a relational database background, mapping EQL concepts to SQL equivalents.
4.  **[Comparators](comparators.md)** and **[Logical Operators](logical_operators.md)**: Detailed references for the symbolic comparison and logical operators used to build query conditions.
5.  **[Aggregators](aggregators.md)**: Learn how to perform calculations like `count` and `average` over your result sets.
6.  **[Result Quantifiers](result_quantifiers.md)** and **[Result Processors](result_processors.md)**: Tools for controlling the expected cardinality (e.g., `an`, `the`) and the final presentation (sorting, limiting, grouping) of your results.
7.  **[Predicates and Symbolic Functions](predicate_and_symbolic_function.md)**: Instructions on how to integrate custom Python logic and predicates directly into your symbolic queries.
8.  **[Pattern Matching](match.md)** and **[Writing Rule Trees](writing_rule_trees.md)**: Advanced features for complex reasoning and matching against structured data.

### Developer Guide
If you are interested in the internals of EQL or wish to extend it:
1.  **[Architecture Overview](../developer/architecture_overview.md)**: A high-level view of the system's design, focusing on the separation between builders and execution graphs.
2.  **[Expression Hierarchy](../developer/expression_hierarchy.md)**: An exploration of the symbolic tree structure and the base classes for all EQL operations.
3.  **[Variable System](../developer/variable_system.md)**: A deep dive into how symbolic variables and domains are handled internally.
4.  **[Execution Engine](../developer/execution_engine.md)**: Details on the mechanics of query evaluation and result binding.
5.  **[Graph and Visualization](../developer/graph_and_visualization.md)**: Tools and techniques for debugging and visualizing query plans and execution graphs.
