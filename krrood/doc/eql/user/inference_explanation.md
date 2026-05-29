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

# Inference Explanation

When EQL infers a new object via an `inference(...)` rule, it automatically attaches an
**`InferenceExplanation`** to that object. The explanation records:

- **Which query node** produced the instance.
- **The source statement** where the query was written.
- **Which conditions** in the query were satisfied (and their `ConditionAndBindings` representation).
- The **`OperationResult`** from the evaluation, carrying the complete variable bindings.

`explain_inference` returns `None` for instances that were not produced by an inference variable
(e.g. plain instances constructed directly).

---

## Data Model

All examples on this page share the same domain. We model bodies, handles, containers, and two
kinds of kinematic connections between them. The hierarchy mirrors the dataset used in the
`test_meta_queries` test suite so readers can cross-reference the tests directly.

```{code-cell} ipython3
from dataclasses import dataclass

from krrood.entity_query_language.factories import (
    entity, variable, match_variable, inference, exists, or_,
)
from krrood.entity_query_language.explanation.explanation import (
    explain_inference, ConditionAndBindings,
)
from krrood.symbol_graph.symbol_graph import Symbol


@dataclass
class ExampleBody(Symbol):
    name: str


@dataclass
class ExampleHandle(ExampleBody): ...


@dataclass
class ExampleContainer(ExampleBody): ...


@dataclass
class ExampleConnection(Symbol):
    parent: ExampleBody
    child: ExampleBody


@dataclass
class ExampleFixedConnection(ExampleConnection): ...


@dataclass
class ExamplePrismaticConnection(ExampleConnection): ...


@dataclass
class ExampleDrawer(Symbol):
    container: ExampleContainer
    handle: ExampleHandle


# Concrete domain objects
base = ExampleBody("base")
containers = [ExampleContainer("C1"), ExampleContainer("C2")]
handles = [ExampleHandle("H1"), ExampleHandle("H2")]
prismatic_conns = [
    ExamplePrismaticConnection(parent=base, child=containers[0]),
    ExamplePrismaticConnection(parent=base, child=containers[1]),
]
fixed_conns = [
    ExampleFixedConnection(parent=containers[0], child=handles[0]),
    ExampleFixedConnection(parent=containers[1], child=handles[1]),
]
```

---

## Drawer Rule

A `Drawer` is inferred wherever a `FixedConnection` shares a parent with a
`PrismaticConnection`'s child, and its other end connects to a `Handle`.
We use `match_variable` to express this structural constraint directly in the variable
definition rather than a separate `.where()` clause.

```{code-cell} ipython3
handle_var = variable(ExampleHandle, handles)
prismatic_conn = variable(ExamplePrismaticConnection, prismatic_conns)
fixed_conn = match_variable(ExampleFixedConnection, fixed_conns)(
    parent=prismatic_conn.child, child=handle_var
)
drawers = inference(ExampleDrawer)(
    container=fixed_conn.parent, handle=fixed_conn.child
).tolist()

print(f"Inferred {len(drawers)} drawer(s): {drawers}")
```

The `match_variable` call implicitly generates two equality conditions that must hold for
each candidate `FixedConnection`:

1. `fixed_conn.parent == prismatic_conn.child`
2. `fixed_conn.child == handle_var`

These are the conditions the explanation will report.

---

## Simple Usage

### Retrieving and printing the explanation

```{code-cell} ipython3
expl = explain_inference(drawers[0])
print(type(expl))
print(expl is None)  # False — the drawer was produced by inference
```

`as_string()` prints the inferred instance, the inference variable that produced it, the
source statement where the query was written, and the satisfied conditions rendered via
`ConditionAndBindings`:

```{code-cell} ipython3
print(expl.as_string())
```

Calling `explain_inference` on a directly constructed object returns `None`:

```{code-cell} ipython3
direct = ExampleDrawer(container=containers[0], handle=handles[0])
print(f"{explain_inference(direct)} -> Was not Inferred by an EQL rule")  # None
```

### Satisfied conditions via `ConditionAndBindings`

`get_satisfied_conditions_and_their_bindings()` returns a list of `ConditionAndBindings`
objects. Each one renders its condition expression using `ConditionAndBindings.__repr__`,
which formats comparators as `(left operator right)`:

```{code-cell} ipython3
for cond in expl.get_satisfied_conditions_and_their_bindings():
    print(cond)
```

### Condition graph

`condition_graph()` returns a `QueryGraph` with `is_satisfied` flags on every node. Satisfied
condition nodes keep their type-based colour; unsatisfied (or short-circuited) ones are faded.

```{code-cell} ipython3
import io
import matplotlib.pyplot as plt
from IPython.display import Image

graph = expl.condition_graph()
fig, ax = graph.visualize(filename="drawer_explanation.pdf")

buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
buf.seek(0)
plt.close(fig)
Image(buf.read())
```

---

## OR Branch Short-Circuit

To show the short-circuit behaviour of `or_()` with structurally different arms we use a
separate, simpler query. The left arm uses `exists()` to check whether there is any
`PrismaticConnection` whose child is the parent of the fixed connection (a relational check);
the right arm falls back to a string predicate on a completely different attribute.

```{code-cell} ipython3
fixed_var = variable(ExampleFixedConnection, fixed_conns)
prismatic_var = variable(ExamplePrismaticConnection, prismatic_conns)
or_drawers = (
    entity(inference(ExampleDrawer)(
        container=fixed_var.parent, handle=fixed_var.child))
    .where(or_(
        exists(prismatic_var, prismatic_var.child == fixed_var.parent),  # True → short-circuits
        fixed_var.parent.name.startswith("X"),                           # never entered
    ))
    .tolist()
)

print(f"Inferred {len(or_drawers)} drawer(s) via OR rule")
```

In the condition graph for this explanation the `OR` and `Exists` nodes are satisfied and
rendered at full opacity. The right arm (`startswith("X")`) was short-circuited by the
successful `exists(...)` check and is faded.

```{code-cell} ipython3
or_expl = explain_inference(or_drawers[0])
or_graph = or_expl.condition_graph()
fig2, ax2 = or_graph.visualize(filename="or_drawer_explanation.pdf")

buf2 = io.BytesIO()
fig2.savefig(buf2, format="png", dpi=100, bbox_inches="tight", facecolor="white")
buf2.seek(0)
plt.close(fig2)
Image(buf2.read())
```

---

## Meta-queries

`InferenceExplanation` inherits from `Symbol`, making it a first-class entity in the
`SymbolGraph`. Its methods return EQL **Entity** descriptors that can be chained, filtered, and
composed just like ordinary queries. All examples below operate on `expl` — the explanation
for the first drawer from the drawer rule above.

### Which conditions were satisfied?

Returns all satisfied condition expressions, including `LogicalOperator` wrappers produced by
`match_variable` and the inference root.

```{code-cell} ipython3
conditions = expl.get_satisfied_condition_expressions_for_the_instance().tolist()
print(f"{len(conditions)} condition expression(s) (comparators + logical wrappers):")
for c in conditions:
    print(" ", ConditionAndBindings(c, expl.operation_result.all_bindings))
```

### Which variable nodes participated (by type)?

Returns the symbolic variable nodes whose `_type_` is a subclass of the given type.
Because `ExampleFixedConnection` and `ExamplePrismaticConnection` both inherit from
`ExampleConnection`, the base-type query returns both:

```{code-cell} ipython3
conn_nodes = expl.get_variable_nodes_of_given_type(ExampleConnection).tolist()
print("Connection variable nodes:", [n._type_.__name__ for n in conn_nodes])

handle_nodes = expl.get_variable_nodes_of_given_type(ExampleHandle).tolist()
print("Handle variable nodes:", [n._type_.__name__ for n in handle_nodes])
```

### What were the actual bound values?

Returns the concrete domain objects that were bound to variable nodes of the given type:

```{code-cell} ipython3
bound_handles = expl.get_values_of_variable_nodes_of_given_type(ExampleHandle).tolist()
print("Bound handle value(s):", bound_handles)
```

### Which conditions relate two variables of the same type?

Returns satisfied conditions that have at least two **distinct** variable nodes of the given
type in their descendant tree.

Because `ExampleFixedConnection` and `ExamplePrismaticConnection` are both subclasses of
`ExampleConnection`, the condition `fixed_conn.parent == prismatic_conn.child` has two
`ExampleConnection`-typed descendants. It is therefore returned here:

```{code-cell} ipython3
same_conn = expl.get_conditions_that_relate_the_variables_of_type(ExampleConnection).tolist()
print("Conditions relating two Connection variables:")
for c in same_conn:
    print(" ", ConditionAndBindings(c, expl.operation_result.all_bindings))
```

### Which conditions relate variables of two different types?

Returns satisfied conditions that have at least one descendant of each specified type.
Here `fixed_conn.parent == prismatic_conn.child` joins an `ExampleFixedConnection` to an
`ExamplePrismaticConnection`:

```{code-cell} ipython3
cross = expl.get_conditions_that_relate_variables_of_types(
    ExampleFixedConnection, ExamplePrismaticConnection
).tolist()
print("Conditions relating FixedConnection ↔ PrismaticConnection:")
for c in cross:
    print(" ", ConditionAndBindings(c, expl.operation_result.all_bindings))
```

The method is symmetric — swapping the two types returns the same set:

```{code-cell} ipython3
cross_rev = expl.get_conditions_that_relate_variables_of_types(
    ExamplePrismaticConnection, ExampleFixedConnection
).tolist()
print("Symmetric result:", {c._id_ for c in cross} == {c._id_ for c in cross_rev})
```

And the condition that links `ExampleFixedConnection` to `ExampleHandle`:

```{code-cell} ipython3
fixed_to_handle = expl.get_conditions_that_relate_variables_of_types(
    ExampleFixedConnection, ExampleHandle
).tolist()
print("Conditions relating FixedConnection ↔ Handle:")
for c in fixed_to_handle:
    print(" ", ConditionAndBindings(c, expl.operation_result.all_bindings))
```

---

## API Reference
- {py:func}`~krrood.entity_query_language.explanation.explanation.explain_inference`
- {py:class}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation`
- {py:class}`~krrood.entity_query_language.explanation.explanation.ConditionAndBindings`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.as_string`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.get_satisfied_conditions_and_their_bindings`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.get_satisfied_conditions_as_string`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.condition_graph`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.get_satisfied_condition_expressions_for_the_instance`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.get_variable_nodes_of_given_type`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.get_values_of_variable_nodes_of_given_type`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.get_conditions_that_relate_the_variables_of_type`
- {py:meth}`~krrood.entity_query_language.explanation.explanation.InferenceExplanation.get_conditions_that_relate_variables_of_types`
