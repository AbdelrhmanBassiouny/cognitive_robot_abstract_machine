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

# Predicates and Symbolic Functions

EQL is highly extensible. You can define your own logic and integrate it into queries using **Predicates** for boolean
checks and **Symbolic Functions** for transforming data.

## Predicates

A {py:class}`~krrood.entity_query_language.predicate.Predicate` is a special class that represents a boolean condition.
When you call it with symbolic variables, it doesn't execute immediately; instead, it returns an `InstantiatedVariable`
that becomes part of the query's execution graph.

### The `HasType` Predicate
One of the most useful built-in predicates is `HasType`, which checks if a variable is an instance of a specific class.

```python
from krrood.entity_query_language.predicate import HasType

# Filter 'v' to only include objects that are instances of 'Handle'
query = entity(v).where(HasType(v, ExampleHandle))
```

```{hint}
`variable(Type, domain=...)` already includes an implicit `HasType` check. Use the predicate explicitly when
you need to check the type of a {py:class}`~krrood.entity_query_language.core.mapped_variable.Attribute` for example.
```

## Symbolic Functions

A **Symbolic Function** computes a value from its arguments. Define it as a
{py:class}`~krrood.entity_query_language.predicate.SymbolicFunction` subclass whose `__call__` holds the
logic, then bind a plain function name to it with
{py:func}`~krrood.entity_query_language.predicate.functional_form`. Called with symbolic arguments it
defers execution until the query is evaluated. (A boolean check is a
{py:class}`~krrood.entity_query_language.predicate.Predicate` instead — its `__call__` returns `bool`.)

```python
from dataclasses import dataclass
from krrood.entity_query_language.predicate import SymbolicFunction, functional_form

@dataclass(eq=False)
class RemainingCharge(SymbolicFunction):
    battery: float
    capacity: float

    def __call__(self) -> float:
        return self.capacity - self.battery

remaining_charge = functional_form(RemainingCharge)

# Use it in a query
query = entity(r).where(remaining_charge(r.battery, r.capacity) > 0)
```

By default a symbolic function verbalizes as *"the remaining charge of …"* — its class name read as a
noun. Override `_verbalization_fragment_` when that reading is wrong, and call
{py:meth}`~krrood.entity_query_language.predicate.SymbolicCallable.preview_verbalization` to see the
surface it produces before deciding.

```{note}
EQL provides a built-in {py:func}`~krrood.entity_query_language.predicate.length` symbolic function for
checking the size of collections.
```

## Full Example: Custom Logic

Let's define a custom predicate and a symbolic function to find robots with specific capabilities.

```{code-cell} ipython3
from dataclasses import dataclass
from krrood.entity_query_language.factories import variable, entity, an, Symbol
from krrood.entity_query_language.predicate import (
    SymbolicFunction, Predicate, functional_form)

@dataclass
class ExampleRobot(Symbol):
    name: str
    load: float

@dataclass(eq=False)
class CalculateStress(SymbolicFunction):
    load: float

    def __call__(self) -> float:
        return self.load * 1.5

calculate_stress = functional_form(CalculateStress)

@dataclass(eq=False)
class ExampleIsOverloaded(Predicate):
    robot: ExampleRobot
    limit: float = 10.0

    def __call__(self) -> bool:
        # This is where the actual logic happens during evaluation
        return calculate_stress(self.robot.load) > self.limit

# Data
robots = [ExampleRobot("Heavy", 8.0), ExampleRobot("Light", 2.0)]
r = variable(ExampleRobot, domain=robots)

# Query using custom logic
query = an(entity(r).where(ExampleIsOverloaded(r)))

for robot in query.evaluate():
    print(f"Overloaded Robot: {robot.name} (Load: {robot.load})")
```

## API Reference
- {py:class}`~krrood.entity_query_language.predicate.SymbolicFunction`
- {py:func}`~krrood.entity_query_language.predicate.functional_form`
- {py:class}`~krrood.entity_query_language.predicate.Predicate`
- {py:class}`~krrood.entity_query_language.predicate.HasType`
- {py:func}`~krrood.entity_query_language.predicate.length`
