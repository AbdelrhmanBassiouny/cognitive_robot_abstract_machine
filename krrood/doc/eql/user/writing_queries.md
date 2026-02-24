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

# Writing Basic Queries

This guide covers the fundamental building blocks of EQL: defining variables with `variable()`, selecting them with
`entity()`, and filtering them with `.where()`.

## Defining Variables

All EQL queries start with symbolic variables. A variable represents a set of possible values (the domain) of a certain
type.

### 1. Variables with Explicit Domains
The most common way to define a variable is to provide a type and a collection of objects (the domain).

```python
from krrood.entity_query_language.factories import variable

# Define a variable 'r' of type 'Robot' from a list
robots_list = [Robot("R1"), Robot("R2")]
r = variable(Robot, domain=robots_list)
```

### 2. Variables with Implicit Domains
If no domain is provided, EQL will attempt to use a default domain. For `Symbol` types, it uses the global `SymbolGraph`.

```python
# 'r' will use all Robots in the SymbolGraph
r = variable(Robot, domain=None)
```

💡 **Hint**: Always provide a domain if you know it. It significantly improves query performance by narrowing the search
space early.

## Selecting Entities

The `entity()` function specifies what you want to retrieve from the query. It returns a `Query` object that you can
further refine.

```python
from krrood.entity_query_language.factories import entity

# We want to select the objects represented by 'r'
query = entity(r)
```

📝 **Note**: If you need to select multiple variables at once, use {py:func}`~krrood.entity_query_language.factories.set_of` instead.

## Adding Filters with `.where()`

The `.where()` method is used to add constraints to your query. You can pass multiple conditions, which are treated as
a logical **AND**.

```python
# Select robots named 'R1'
query = entity(r).where(r.name == "R1")
```

## Full Example: Finding High-Battery Robots

Let's combine these concepts into a complete, runnable example.

```{code-cell} ipython3
from dataclasses import dataclass
from krrood.entity_query_language.factories import variable, entity, an, Symbol

# Define our model
@dataclass
class Robot:
    name: str
    battery: int

# Prepare data
robots = [Robot("R2D2", 100), Robot("C3PO", 20), Robot("BB8", 80)]

# 1. Define the variable
r = variable(Robot, domain=robots)

# 2. Build the query with filters
# We want robots with battery levels greater than 50
query = an(entity(r).where(r.battery > 50))

# 3. Execute and see the results
for robot in query.evaluate():
    print(f"Found {robot.name} with {robot.battery}% battery")
```

## API Reference
- {py:func}`~krrood.entity_query_language.factories.variable`
- {py:func}`~krrood.entity_query_language.factories.entity`
- {py:meth}`~krrood.entity_query_language.query.query.Query.where`
