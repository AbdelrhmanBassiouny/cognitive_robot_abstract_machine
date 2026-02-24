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

# Logical Operators

EQL provides intuitive ways to combine multiple constraints using logical operators. These allow you to build complex filters beyond simple attribute checks.

## The Conjunction (AND)

You can combine conditions using the `&` or `and_()` operator or by passing multiple arguments to `.where()`. Both methods are equivalent.

### 1. Multiple conditions in `.where()`
```python
# Select robots that are named 'R2D2' AND have battery > 50
query = entity(r).where(r.name == "R2D2", r.battery > 50)
```

### 2. Using the `&` operator
```python
# This produces the same result
query = entity(r).where((r.name == "R2D2") & (r.battery > 50))
```

💡 **Hint**: Using multiple arguments in `.where()` is generally cleaner for simple conjunctions.

## The Disjunction (OR)

Use the `|` or `or_()` operator to specify that at least one of the conditions must be met.

```python
# Select robots that are either 'R2D2' OR have battery < 10
query = entity(r).where((r.name == "R2D2") | (r.battery < 10))
```

⚠️ **Warning**: Always use parentheses around your conditions when using `&` or `|` to ensure correct operator precedence.

## The Negation (NOT)

The `~` or `not_()` operator inverts a condition. It returns results that do **not** satisfy the specified constraint.

```python
# Select all robots EXCEPT those named 'R2D2'
query = entity(r).where(~(r.name == "R2D2"))
```

📝 **Note**: Negation can be particularly useful for "anti-joins" or excluding specific subsets from your results.

## Full Example: Complex Logic

Let's build a query that combines all these operators.

```{code-cell} ipython3
from dataclasses import dataclass
from krrood.entity_query_language.factories import variable, entity, an, Symbol

@dataclass
class Robot(Symbol):
    name: str
    battery: int
    online: bool

robots = [
    Robot("R2D2", 100, True),
    Robot("C3PO", 20, False),
    Robot("BB8", 80, True),
    Robot("Gonk", 5, True)
]

r = variable(Robot, domain=robots)

# We want robots that are (ONLINE and (battery > 50)) OR (NOT ONLINE and battery < 30)
query = an(entity(r).where(
    (r.online & (r.battery > 50)) | (~r.online & (r.battery < 30))
))

for robot in query.evaluate():
    print(f"Robot: {robot.name} (Online: {robot.online}, Battery: {robot.battery})")
```

## API Reference
- {py:class}`~krrood.entity_query_language.operators.core_logical_operators.AND`
- {py:class}`~krrood.entity_query_language.operators.core_logical_operators.OR`
- {py:class}`~krrood.entity_query_language.operators.core_logical_operators.Not`
