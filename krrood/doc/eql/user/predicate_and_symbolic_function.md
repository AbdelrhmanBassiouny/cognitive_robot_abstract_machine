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

A **Symbolic Function** is a {py:class}`~krrood.entity_query_language.predicate.SymbolicFunction` subclass whose
`__call__` computes a value. When constructed with symbolic arguments it defers execution until the query is
evaluated. Bind {py:func}`~krrood.entity_query_language.predicate.functional_form` to a plain name so the function
reads naturally at the call site: it constructs the symbolic expression when any argument is a variable, and returns
the directly computed value otherwise.

```python
from dataclasses import dataclass
from krrood.entity_query_language.predicate import SymbolicFunction, functional_form

@dataclass(eq=False)
class IsEven(SymbolicFunction):
    number: int

    def __call__(self) -> bool:
        return self.number % 2 == 0

is_even = functional_form(IsEven)

# Use it in a query
query = entity(r).where(is_even(r.battery))
```

```{note}
EQL provides a built-in {py:func}`~krrood.entity_query_language.predicate.length` symbolic function for
checking the size of collections.
```

:::{warning}
Symbolic attribute access covers **regular** attributes only. Dunder names (e.g. `variable.__name__`)
are *not* resolved symbolically — they are reserved for Python's own protocols, so intercepting them
would break `copy`, pickling, and debugging. To read a dunder-named member of a matched object inside
a query, wrap the access in a `SymbolicFunction`:

```python
@dataclass(eq=False)
class ClassName(SymbolicFunction):
    owner: type

    def __call__(self) -> str:
        return self.owner.__name__

class_name = functional_form(ClassName)

query = entity(v).where(class_name(v).startswith("C"))
```
:::

## Full Example: Custom Logic

Let's define a custom predicate and a symbolic function to find robots with specific capabilities.

```{code-cell} ipython3
from dataclasses import dataclass
from krrood.entity_query_language.factories import variable, entity, an, Symbol
from krrood.entity_query_language.predicate import SymbolicFunction, functional_form, Predicate

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
