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

Mira runs quality control at a coin mint. Every coin that comes off the press gets
measured by three sensors -- diameter, thickness, and weight -- and the mint has
already fitted a probabilistic model to a long history of these measurements: given
how the press was set up on a given run, what do the resulting coins tend to look
like? Mira doesn't build that model herself; she just has questions for it.

```python
from dataclasses import dataclass

@dataclass
class Coin:
    a: float  # diameter
    b: float  # thickness
    c: float  # weight
```

`set_of`/`entity` answer questions about *actual coins* -- "find me the coins whose
diameter is under spec". Mira's questions today are different: not about which coins
exist, but about the *model itself*. Three constructs answer that kind of question:

| Mira's question reads as... | Construct | Answer |
|---|---|---|
| "On average, how wide are the coins?" | {py:func}`~krrood.entity_query_language.factories.average` | a number |
| "What fraction of coins are dangerously thin?" | {py:func}`~krrood.entity_query_language.factories.probability_of` | a number |
| "Given today's press settings, what does the shape of the remaining measurements look like?" | {py:func}`~krrood.entity_query_language.factories.distribution_of` | a distribution |

All three need the fitted model to answer, so they only work when evaluated with
{py:class}`~krrood.entity_query_language.backends.ProbabilisticBackend`, the backend
that knows how to reach it:

```python
from probabilistic_model.distributions.uniform import UniformDistribution
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit, ProductUnit, leaf,
)
from random_events.interval import closed
from random_events.variable import Continuous

# Stand-in for the mint's already-fitted model: today's press run, in isolation,
# produces diameter/thickness/weight uniformly across a range each. (Named
# "Coin.<field>" so DictRegistry -- see below -- can look each field up by name.)
var_a = Continuous("Coin.a")
var_b = Continuous("Coin.b")
var_c = Continuous("Coin.c")

circuit = ProbabilisticCircuit()
root = ProductUnit(probabilistic_circuit=circuit)
root.add_subcircuit(leaf(UniformDistribution(variable=var_a, interval=closed(0, 1).simple_sets[0]), circuit))
root.add_subcircuit(leaf(UniformDistribution(variable=var_b, interval=closed(0, 2).simple_sets[0]), circuit))
root.add_subcircuit(leaf(UniformDistribution(variable=var_c, interval=closed(0, 3).simple_sets[0]), circuit))

from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.entity_query_language.factories import a, average, distribution_of, probability_of, variable
from krrood.parametrization.model_registries import DictRegistry

backend = ProbabilisticBackend(model_registry=DictRegistry({Coin: circuit}))
```

## "On average, how wide are the coins?"

The simplest question, and it uses a construct Mira already knows -- `average`, the
same one that averages a column of matched rows. Called *bare* (no `set_of`, no
`.grouped_by()`) against a model-backed backend, it answers straight from the model
instead of averaging a sample of rows:

```python
x = variable(Coin)
print(average(x.a).first(backend=backend))
# 0.5
```

That's it -- same function Mira would use in an ordinary query, just pointed at a
model instead of a table of coins.

## "What fraction of coins are dangerously thin?"

Suppose anything under 0.5 fails inspection.

```python
x = variable(Coin)
print(probability_of(x.a < 0.5).first(backend=backend))
# 0.5
```

There's a simpler way to think about this that Mira already knows from ordinary
querying: take a big batch of coins, count how many have diameter under 0.5, divide by
how many coins there are. That *is* what a probability means, and it's a perfectly
valid way to estimate one. `probability_of` doesn't do that, though -- there's no batch
of coins involved at all. It reads the answer directly off the fitted model, so
instead of an estimate that gets better with a bigger batch, Mira gets the exact
number the model implies, every time.

## "Given today's press settings, what does the rest look like?"

The press was calibrated to punch out 1.5g coins today, and Mira has already screened
out anything under the 0.2 diameter minimum. She's not asking for a number now -- she
wants to see the *shape* of what's left: how thickness and diameter vary once weight
is pinned down and the too-narrow coins are gone.

This is exactly the kind of thing `a(...)`/`an(...)`/`the(...)` already describe --
Mira would normally write this same shape of match to *generate* example coins that
fit these settings. `distribution_of` asks the identical question, just answered
differently: instead of generating coins, it hands back the distribution itself.

```python
match = a(Coin)(a=..., b=..., c=1.5)
match.where(match.variable.a > 0.2)

result = distribution_of(match).first(backend=backend)
print(sorted(v.name for v in result.variables))
# ['Coin.a', 'Coin.b', 'Coin.c']
```

`c=1.5` is the press setting; `.where(a > 0.2)` is the screening step; `a`/`b`
(diameter/thickness) are left open (`...`) -- what Mira wants to see the shape of.
The result is an ordinary distribution object, queryable like the mint's original
model:

```python
from random_events.product_algebra import SimpleEvent

a_range = SimpleEvent.from_data({var_a: closed(0.2, 1)}).as_composite_set()
print(result.probability(a_range))
# 1.0 -- everything left satisfies a > 0.2, by construction

b_range = SimpleEvent.from_data({var_b: closed(0, 1)}).as_composite_set()
print(result.probability(b_range))
# 0.5 -- unchanged: thickness never depended on diameter or weight to begin with
```

If Mira only cares about diameter specifically, she can ask for just that:

```python
narrowed = distribution_of(match, match.variable.a).first(backend=backend)
print({v.name for v in narrowed.variables})
# {'Coin.a'}
```

## Recap

- **`average(x.a)`** -- the same aggregator used for row-averaging, pointed at a model
  instead of a table; answers with the model's exact expectation.
- **`probability_of(condition)`** -- the exact answer a "count matching rows / count
  all rows" estimate is aiming for, computed directly from the model instead of
  estimated from a sample. Accepts any condition a `.where(...)` clause does.
- **`distribution_of(match, *variables)`** -- the same match Mira would write to
  *generate* coins, answered with the shape of the distribution instead of samples
  from it. Optional `*variables` narrow which measurements the answer covers.

All three only work with a probabilistic backend behind them -- there's no table of
rows to fall back to, only the model. And two of the names should look familiar
already: `distribution_of`/`average` are how `a(...)`/`an(...)`/`the(...)` and
`average(...)` already read, just answered from a different place.

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
- {py:class}`~krrood.parametrization.parameterizer.ModelQueryParameters`
- {py:class}`~krrood.entity_query_language.exceptions.BackendCannotEvaluateProbabilisticQuery`
- {py:class}`~krrood.parametrization.exceptions.JointQueryAcrossClassesNotSupported`
