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

# Result Quantifiers

Result quantifiers are used to specify the expected number of results for a query. They wrap a query and enforce
constraints on its cardinality during execution.

## The `an()` Quantifier

The `an()` quantifier expresses that you expect **zero or more** results by default, or a custom cardinality by specifying
the qunatification constriants as keyword arguments.

```python
from krrood.entity_query_language.factories import an, entity

# We expect at least one robot satisfying the condition
query = an(entity(r).where(r.battery > 50))
```

💡 **Hint**: Use `an()` when you are searching for any number of matching entities and want a generator of results.

## The `the()` Quantifier

The `the()` quantifier expresses that you expect **exactly one** result. If the query returns zero results or more than
one result, EQL will raise an error.

```python
from krrood.entity_query_language.factories import the

# We expect exactly one robot named 'R2D2'
query = the(entity(r).where(r.name == "R2D2"))
```

⚠️ **Warning**: Using `the()` on a query that returns multiple results will raise a `MoreThanOneSolutionFound`. Use it
only when you are certain of the uniqueness of your match.

## Advanced Quantification

You can also pass specific constraints to `an()` to define more complex requirements.

```python
from krrood.entity_query_language.query.quantifiers import Exactly, AtLeast, AtMost

# Expect exactly 3 results
query = an(entity(r), quantification=Exactly(3))

# Expect at most 5 results
query = an(entity(r), quantification=AtMost(5))
```

📝 **Note**: Quantifiers are {py:class}`~krrood.entity_query_language.core.base_expressions.DerivedExpression`s.
They don't change the underlying data, but they wrap the result stream to enforce their constraints.

## Full Example: Finding a Unique Item

This example shows how `the()` ensures that you only get a single, unambiguous result.

```{code-cell} ipython3
from dataclasses import dataclass
from krrood.entity_query_language.factories import variable, entity, the, Symbol

@dataclass
class Item(Symbol):
    serial_number: str
    name: str

items = [
    Item("SN001", "Sensor"),
    Item("SN002", "Actuator"),
    Item("SN001", "Broken Sensor") # Duplicated serial number!
]

v = variable(Item, domain=items)

# This query will FAIL because SN001 is not unique
try:
    query = the(entity(v).where(v.serial_number == "SN001"))
    result = query.first()
except Exception as e:
    print(f"Error as expected: {e}")

# This query will SUCCEED
query = the(entity(v).where(v.serial_number == "SN002"))
result = query.first()
print(f"Found unique item: {result.name}")
```

## API Reference
- {py:func}`~krrood.entity_query_language.factories.an`
- {py:func}`~krrood.entity_query_language.factories.the`
- {py:class}`~krrood.entity_query_language.query.quantifiers.ResultQuantificationConstraint`
