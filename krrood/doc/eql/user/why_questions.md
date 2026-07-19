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

# Why-Questions

When a Ripple-Down-Rules reasoner concludes something, you can ask it **why**: which rule
fired, and on what grounds. The `why(...)` factory is the formal ask surface for that
question. It returns a **query** that composes over the explanation a result already carries
and reads back as a plain causal explanation:

> *the category of the Fruit is citrus, because the Fruit is sour, and the Fruit is not
> small, by the base rule R0*

`why(...)` never re-classifies and never inspects the concluded value — an RDR reuses one
shared value (e.g. one `citrus` enum member) across many cases, so an explanation cannot live
on it. Instead the explanation is produced once, model-side, and rides on the **result** the
reasoner hands you; `why(...)` composes over that.

---

## A small reasoner to question

We fit a two-rule `EQLSingleClassRDR` that predicts a `Fruit`'s `category` from its traits.
The rules are supplied programmatically here so the example is self-contained; in practice
they are grown interactively while fitting.

```{code-cell} ipython3
import enum
from dataclasses import dataclass
from typing import Optional

from krrood.entity_query_language.factories import why, and_
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface


class Category(enum.Enum):
    citrus = 1
    berry = 2

    def __repr__(self):
        return f"Category.{self.name}"


@dataclass
class Fruit:
    name: str
    sour: bool
    small: bool
    category: Optional[Category] = None


def rule_expert(conditions_for_target):
    """An expert that supplies each target's conditions over the shared case variable."""

    def answer(context, requests):
        build = conditions_for_target[context.target_conclusion]
        return {"conditions": build(context.case_variable)}

    return Expert(interface=FunctionInterface(answer_fn=answer))


rdr = EQLSingleClassRDR(Fruit, "category")
lemon = Fruit("lemon", sour=True, small=False)
blueberry = Fruit("blueberry", sour=False, small=True)

expert = rule_expert({
    Category.citrus: lambda v: and_(v.sour == True, v.small == False),
    Category.berry: lambda v: v.small == True,
})
rdr.fit_case(lemon, Category.citrus, expert)
rdr.fit_case(blueberry, Category.berry, expert)
```

---

## Asking why about a case

`rdr.explain(case)` reads the reasoner's explanation for a classified case; `why(...)` wraps
it in a {py:class}`~krrood.entity_query_language.rdr.why.WhyQuery`. The query is *lazy* —
building it reads nothing; the answer is resolved when you use it:

```{code-cell} ipython3
query = why(rdr.explain(lemon))
type(query).__name__
```

```{code-cell} ipython3
print(why(rdr.explain(lemon)).verbalize())
print(why(rdr.explain(blueberry)).verbalize())
```

The explanation has three spans, in this order:

1. **the conclusion** the rule reached — *the category of the Fruit is citrus*;
2. **because** the satisfied conditions that justify it — *the Fruit is sour, and the Fruit
   is not small*, read with the concrete case (*the Fruit*), not a bare variable;
3. **by the `<kind>` rule `<code>`** — the identity of the fired rule: its kind (a `base` rule,
   an `alternative` rule, or a `refinement` rule that overrides a more general one) and a stable
   code (`R0` for the base rule, `R`/`A`-prefixed codes for refinements and alternatives).

Above, `lemon` fires the `base` rule `R0` and `blueberry` the `alternative` rule `A1`.

---

## Asking why about a yielded result

The idiomatic surface is to ask over a **result** the reasoner yields. A decision is an
underspecified query over a partially-specified object, and choosing is evaluating it with an
RDR backend; each yielded result carries the explanation of how it was filled, so `why(...)`
composes over it directly:

```python
result = next(an(Fruit)(category=...).from_([lemon]).evaluate(backend=rdr_backend))
print(why(result).verbalize())
# the category of the Fruit is citrus, because the Fruit is sour, ... by the base rule R0
```

```{note}
Explanation-bearing yielded results (the model-side store and the handle attachment) arrive
with the RDR backend's decision-query support. `why(...)` already reads such a handle through
the {py:class}`~krrood.entity_query_language.rdr.why.ExplanationCarrier` seam — anything
exposing a `conclusion_explanation` — so it works the moment results carry their explanations,
with no change to this call.
```

---

## The answer object

`.answer` is a {py:class}`~krrood.entity_query_language.rdr.why.WhyAnswer` — the selected
content behind the sentence. Read its fields directly when you need the structured form
rather than the prose:

```{code-cell} ipython3
answer = why(rdr.explain(lemon)).answer
print("conclusion:", answer.conclusion)
print("rule code :", answer.rule_code.as_string)
print("rule depth:", answer.rule_depth)
print("corner case:", answer.corner_case)
for condition in answer.satisfied_conditions:
    print("  satisfied:", condition)
```

The same query reads its source at most once: repeated access returns the memoized answer.
Building the query itself verbalizes nothing — the answer is produced only when you use it.

---

## No conclusion, no explanation

A case that no rule classifies has nothing to explain, so asking for its explanation raises:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.exceptions import NoConclusionToExplainError

unfitted = EQLSingleClassRDR(Fruit, "category")

try:
    unfitted.explain(lemon)
except NoConclusionToExplainError as error:
    print("raised:", error)
```

---

## Contrastive questions are reserved

A *contrastive* why-question — *why citrus rather than berry?* — is reserved for a later
version. You may pass a `contrast`, and it is recorded on the query, but answering one is not
implemented yet:

```{code-cell} ipython3
contrastive = why(rdr.explain(lemon), contrast=Category.berry)
print("is contrastive:", contrastive.is_contrastive)

try:
    contrastive.answer
except NotImplementedError as error:
    print("reserved:", error)
```

```{note}
The `%why` line magic — asking *why* interactively about the last classified case — is
deferred until the interactive RDR interface lands. Until then, call `why(...)` directly.
```

---

## API Reference
- {py:func}`~krrood.entity_query_language.factories.why`
- {py:class}`~krrood.entity_query_language.rdr.why.WhyQuery`
- {py:class}`~krrood.entity_query_language.rdr.why.ExplanationCarrier`
- {py:class}`~krrood.entity_query_language.rdr.why.WhyAnswer`
- {py:class}`~krrood.entity_query_language.rdr.why.RDRConclusionExplanation`
- {py:meth}`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR.explain`
