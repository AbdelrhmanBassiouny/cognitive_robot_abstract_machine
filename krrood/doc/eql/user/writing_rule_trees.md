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

# Advanced Inference: Rule Trees

Beyond simple queries, EQL supports an inference engine for building **Rule Trees**. This allows you to symbolically construct new objects or add information to existing variables based on complex, conditional logic.

## Core Concepts

A Rule Tree is built using three main components:
1.  **`inference(Type)`**: A special variable constructor for objects that will be "materialized" by the rule.
2.  **`Add(target, value)`**: A conclusion clause that assigns a value to a symbolic variable.
3.  **ConclusionSelectors**: Logical branches that control rule evcaluation flow and choose which conclusions are applied.
Examples: `refinement()`,`alternative()`, and `next_rule()`.

## Conclusion Selectors

### 1. `refinement()`
Narrows the context with an additional condition. It behaves like a logical **AND** but is used specifically to 
specialize a rule.

```python
with refinement(body.size > 1):
    # This only happens if the body is big
    Add(views, inference(Door)(handle=handle, body=body))
```

### 2. `alternative()`
Provides a sibling branch that is only evaluated if the previous branches didn't match. It behaves like an **Else-If**.

```python
with alternative(body.is_fixed):
    Add(views, inference(Drawer)(...))
```

💡 **Hint**: Use `refinement` for specialization (exceptions) and `alternative` for mutually exclusive cases.

## The `with query:` Context

To build a rule tree, you use the query object as a context manager. Any `Add`, `refinement`, or `alternative` inside
this block becomes part of that query's rule structure.

```python
query = an(entity(views).where(...))

with query:
    Add(views, default_conclusion)
    with refinement(extra_condition):
        Add(views, specialized_conclusion)
```

⚠️ **Warning**: Rule trees are for **inference** (adding data). For simple filtering, stick to `.where()` and standard queries.

## Full Example: Categorizing Connections

This example demonstrates how to build a rule tree that categorizes connections into either `Fixed` or `Revolute` views.

```{code-cell} ipython3
from dataclasses import dataclass
from krrood.entity_query_language.factories import (
    variable, entity, an, Symbol, inference, refinement, alternative, Add
)

@dataclass
class Connection(Symbol):
    type_code: int

@dataclass
class View(Symbol): pass

@dataclass
class FixedView(View): pass

@dataclass
class RevoluteView(View): pass

# Data
conns = [Connection(1), Connection(2), Connection(3)]
c = variable(Connection, domain=conns)
views = inference(View)()

# 1. Base query
query = an(entity(views))

# 2. Rule Tree definition
with query:
    # If type_code is 1, it's a FixedView
    with refinement(c.type_code == 1):
        Add(views, inference(FixedView)())
    
    # Otherwise, if type_code is 2, it's a RevoluteView
    with alternative(c.type_code == 2):
        Add(views, inference(RevoluteView)())

# 3. Execution
results = query.tolist()
print(f"Inferred {len(results)} views from {len(conns)} connections.")
```

## API Reference
- {py:func}`~krrood.entity_query_language.factories.inference`
- {py:class}`~krrood.entity_query_language.rules.conclusion.Add`
- {py:func}`~krrood.entity_query_language.factories.refinement`
- {py:func}`~krrood.entity_query_language.factories.alternative`
