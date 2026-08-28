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

# Probabilistic Queries

Sometimes a query should not return rows at all, but something *about* the
distribution those rows would have come from -- the distribution itself, the
probability of a condition, or the expectation of an attribute. `set_of`/`entity`
always resolve to enumerated results; instead:

| Read as... | Construct | Resolves to |
|---|---|---|
| "the distribution of ..." | {py:func}`~krrood.entity_query_language.factories.distribution_of` | a `ProbabilisticModel` |
| "the probability of ..." | {py:func}`~krrood.entity_query_language.factories.probability_of` | a `float` |
| "the average of ..." | {py:func}`~krrood.entity_query_language.factories.average` (already existing) | a `float` |

Like `cause`/`confounder` (see {doc}`causality`), `distribution_of`/`probability_of`
only mean anything under
{py:class}`~krrood.entity_query_language.backends.ProbabilisticBackend`: querying a
probabilistic model directly is a probabilistic operation, not a data selection, so
neither has a native or SQL evaluation strategy at all -- evaluating either any other
way raises
{py:class}`~krrood.entity_query_language.exceptions.BackendCannotEvaluateProbabilisticQuery`.
`average(...)` is different: it already has an ordinary native meaning (the mean of
enumerated rows), and `ProbabilisticBackend` recognizes a *bare* `average(...)`
selection and answers it in closed form instead -- same call, correct answer under
either backend.

## `distribution_of`: the probabilistic interpretation of `a`/`an`/`the`

{py:func}`~krrood.entity_query_language.factories.a` already builds a
{py:class}`~krrood.entity_query_language.query.match.Match` that
{py:class}`~krrood.entity_query_language.backends.ProbabilisticBackend` conditions and
truncates before *sampling* instances from it -- literal-valued kwargs condition the
circuit, `.where(...)` conditions truncate it, and underspecified (`...`) fields are
the free variables it samples.
{py:func}`~krrood.entity_query_language.factories.distribution_of` asks for exactly
that same conditioned-and-truncated model, just returned directly instead of sampled
from:

```python
from dataclasses import dataclass

from probabilistic_model.distributions.uniform import UniformDistribution
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit, ProductUnit, leaf,
)
from random_events.interval import closed
from random_events.product_algebra import SimpleEvent
from random_events.variable import Continuous

from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.entity_query_language.factories import a, average, distribution_of, probability_of
from krrood.parametrization.model_registries import DictRegistry


@dataclass
class Coin:
    a: float
    b: float
    c: float


# Named "Coin.<field>" up front, the same convention used in the causality example, so
# DictRegistry can look each field up by its qualified name.
var_a = Continuous("Coin.a")
var_b = Continuous("Coin.b")
var_c = Continuous("Coin.c")

circuit = ProbabilisticCircuit()
root = ProductUnit(probabilistic_circuit=circuit)
root.add_subcircuit(leaf(UniformDistribution(variable=var_a, interval=closed(0, 1).simple_sets[0]), circuit))
root.add_subcircuit(leaf(UniformDistribution(variable=var_b, interval=closed(0, 2).simple_sets[0]), circuit))
root.add_subcircuit(leaf(UniformDistribution(variable=var_c, interval=closed(0, 3).simple_sets[0]), circuit))

backend = ProbabilisticBackend(model_registry=DictRegistry({Coin: circuit}))

match = a(Coin)(a=..., b=..., c=1.5)
match.where(match.variable.a > 0.2)

result = distribution_of(match).first(backend=backend)
print(sorted(v.name for v in result.variables))
# ['Coin.a', 'Coin.b', 'Coin.c']
```

`c=1.5` conditions the circuit (`c` stays in the model, but as a point mass at 1.5 --
conditioning doesn't drop the variable, it collapses its distribution); `a > 0.2`
truncates it; `b` is free and untouched, since it's independent of `a`/`c`:

```python
a_range = SimpleEvent.from_data({var_a: closed(0.2, 1)}).as_composite_set()
print(result.probability(a_range))
# 1.0 -- everything left satisfies a > 0.2

b_range = SimpleEvent.from_data({var_b: closed(0, 1)}).as_composite_set()
print(result.probability(b_range))
# 0.5 -- unchanged, b is independent of a and c
```

Pass extra `*variables` to narrow the result to a subset of the match's free variables
(further marginalization) -- e.g. just `a`, dropping `b` and the now-degenerate `c`:

```python
narrowed = distribution_of(match, match.variable.a).first(backend=backend)
print({v.name for v in narrowed.variables})
# {'Coin.a'}
```

## `probability_of`

Unlike `distribution_of`, this doesn't wrap a `Match` -- it takes a bare condition
directly, any expression a `.where(...)` condition already accepts (comparators
combined with `and_`/`or_`/`not_`, ranges, ...):

```python
p = probability_of(match.variable.a < 0.5).first(backend=backend)
print(p)
# 0.5
```

## `average`: the expectation, via the construct EQL already has

There's no separate "expectation" construct. The existing
{py:func}`~krrood.entity_query_language.factories.average` aggregator -- the same one
used inside `set_of(...)`/`entity(...)` to average enumerated rows -- already reads
declaratively as "the average of ...", so `ProbabilisticBackend` reuses it directly:
evaluated bare (no `set_of`, `.grouped_by()`, `.where()`, ...), it resolves in closed
form via `ProbabilisticModel.moment` instead of sampling and averaging rows:

```python
expectation_a = average(match.variable.a).first(backend=backend)
print(expectation_a)
# 0.5 -- midpoint of Uniform([0, 1])
```

The same call against an ordinary (non-probabilistic) backend still does the ordinary
thing -- averages enumerated values:

```python
from krrood.entity_query_language.factories import variable

heights = [1, 2, 3, 4, 5]
heights_var = variable(int, domain=heights)
print(average(heights_var).first())
# 3.0
```

Grouped, filtered, or otherwise-modified `average(...)` calls are *not* reinterpreted
probabilistically -- there's no enumerated data to group over from a bare
`variable(...)`, so `ProbabilisticBackend` falls through to its ordinary
generative-backend error rather than silently ignoring the grouping.

## Scope

- **`distribution_of`/`probability_of`: evaluate with `ProbabilisticBackend` only.**
  Evaluating either natively, or with any other backend, always raises
  {py:class}`~krrood.entity_query_language.exceptions.BackendCannotEvaluateProbabilisticQuery`.
- **`probability_of`: one class per query.** Every attribute a condition constrains
  must be reached from the same `variable(...)` root -- e.g. `probability_of(and_(x.a
  < 5, y.b < 5))` for two different classes' variables raises
  {py:class}`~krrood.parametrization.exceptions.JointQueryAcrossClassesNotSupported`,
  since every {py:class}`~krrood.parametrization.model_registries.ModelRegistry`
  resolves a single model per class. `distribution_of(...)` never raises this: it
  wraps a single `Match`, which is always for one class by construction.
- **`average`: only a bare selection is reinterpreted.** `average(x.a)` evaluated
  directly; anything with `.grouped_by()`/`.where()`/etc. attached falls through to
  the ordinary (non-probabilistic) evaluation path.

## Verbalization

`distribution_of`/`probability_of` are also verbalizable, via
{py:func}`~krrood.entity_query_language.verbalization.pipeline.verbalize_expression`
(see {doc}`verbalization`). `distribution_of(match)` reuses the match's own `given
that`/`where` grammar, with two changes from the match's own rendering: its imperative
*"Find"*/*"Generate"* header becomes a definite *"The distribution over …"* (a
distribution is asked for, not rows, so it takes neither verb), and its underspecified
(`...`) fields -- the distribution's free variables -- aren't named at all, unlike the
match's own generative *"and predict its battery value"* clause: *"the distribution
over a Coin"* already means "over every attribute not given", so a query that just
selects everything (`a(Coin)(a=..., b=..., c=...)`) verbalizes as plainly as *"The
distribution over a Coin"*. When `*variables` marginalizes that default to a subset,
they're named directly in the subject instead (*"the a of a Coin"*) rather than a
trailing qualifier like *"restricted to …"*, which reads like a truncation (a `where`)
rather than a choice of which variables the joint is even over.
`probability_of(condition)` recurses the condition through the ordinary comparator
grammar, prefixed with *"the probability that …"*. `average(...)` needs no
verbalization changes: it's an ordinary aggregator node already verbalized (*"the
average of …"*) regardless of which backend will evaluate it.

```python
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

match = a(Coin)(a=..., b=..., c=1.5)
match.where(match.variable.a > 0.2)

print(verbalize_expression(distribution_of(match)))
# "The distribution over a Coin given that its c is 1.5, where its a is greater
#  than 0.2"

print(verbalize_expression(distribution_of(match, match.variable.a)))
# "The distribution over the a of a Coin given that its c is 1.5, where its a is
#  greater than 0.2"

x = variable(Coin)
print(verbalize_expression(probability_of(x.a < 0.5)))
# "the probability that the a of a Coin is less than 0.5"
```

---

## API Reference

- {py:func}`~krrood.entity_query_language.factories.distribution_of`
- {py:func}`~krrood.entity_query_language.factories.probability_of`
- {py:func}`~krrood.entity_query_language.factories.average`
- {py:class}`~krrood.entity_query_language.operators.probabilistic_queries.ProbabilisticQuery`
- {py:class}`~krrood.entity_query_language.operators.probabilistic_queries.Distribution`
- {py:class}`~krrood.entity_query_language.operators.probabilistic_queries.Probability`
- {py:class}`~krrood.entity_query_language.operators.aggregators.Average`
- {py:meth}`~krrood.entity_query_language.backends.ProbabilisticBackend._resolve_average`
- {py:meth}`~krrood.parametrization.parameterizer.UnderspecifiedParameters.resolve_conditioned_and_truncated_model`
- {py:class}`~krrood.parametrization.parameterizer.SelectedAttributesParameters`
- {py:class}`~krrood.parametrization.parameterizer.ConditionParameters`
- {py:class}`~krrood.entity_query_language.exceptions.BackendCannotEvaluateProbabilisticQuery`
- {py:class}`~krrood.parametrization.exceptions.JointQueryAcrossClassesNotSupported`
