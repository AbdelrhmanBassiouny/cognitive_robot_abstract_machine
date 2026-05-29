---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.19.3
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Conclusion-Asking Internals

This guide explains the design of the *conclusion-asking* (no-ground-truth) fit path in
`krrood.entity_query_language.rdr`.  User documentation lives in
{doc}`../user/eql_rdr_conclusion_asking`.

## Design Goals

1. **Minimal expert burden** — on the no-target path the expert types two focused
   answers in two successive sessions rather than one combined session that mixes
   a label choice with a condition.  Separating the concerns reduces cognitive load and
   makes each session's validation rules simple.
2. **Zero duplication of the conditions flow** — once a conclusion is chosen, the
   conditions-only path (used by ground-truth fitting) is reused verbatim.
   `ask_for_conditions` is called exactly once regardless of how the conclusion was
   determined.
3. **Type-derived allowable values** — the set of valid conclusions is read from the
   declared type annotation (`enum.Enum` → enumerable; `bool` → enumerable; open type →
   isinstance-checked).  No schema file, no hand-maintained list.
4. **Injectable extension** — `ConclusionAid` is the single seam for task-specific
   presentation and suggestion.  Adding a new kind of aid never requires touching `Expert`
   or the interfaces.

---

## SOLID Split

The feature is spread across five focused classes; each has a single responsibility.

| Class | Responsibility | Module |
|---|---|---|
| `EQLSingleClassRDR` | Orchestration — calls expert, inserts rule | `single_class.py` |
| `Expert` | Policy — what to ask and in which order; owns validators | `expert.py` |
| `ExpertInterface` / `FunctionInterface` / `IPythonInterface` | Mechanism — how answers are collected | `interface.py` / `interactive.py` |
| `ConclusionDomain` | Value set — what values are valid for the conclusion | `conclusion_domain.py` |
| `ConclusionAid` | Extension seam — optional presentation and suggestion | `aid.py` |

---

## Architecture

```{mermaid}
sequenceDiagram
    participant RDR as EQLSingleClassRDR
    participant Exp as Expert
    participant Iface as ExpertInterface
    participant Aid as ConclusionAid
    participant Dom as ConclusionDomain

    RDR->>Exp: ask_for_rule(case, cv, domain, current, trace)
    Exp->>Aid: suggest(context)       [for each aid]
    Aid-->>Exp: suggestion | None
    Exp->>Dom: example_for("conclusion")
    Exp->>Iface: interact(context, [conclusion_request])
    Iface-->>Exp: {"conclusion": value}
    Note over Exp: if conclusion == current → return (current, None)
    Exp->>Iface: interact(context, [conditions_request])
    Iface-->>Exp: {"conditions": expr}
    Exp-->>RDR: (conclusion, conditions)
    RDR->>RDR: _insert_rule(trace, current, conditions, conclusion)
```

### `EQLSingleClassRDR.fit_case` — the entry point

`fit_case(case, target=UNSET, expert)` branches on whether a target was supplied:

- **Target given**: calls `expert.ask_for_conditions` directly; the one-step ground-truth flow.
- **Target is `UNSET`**: calls `expert.ask_for_rule`; the two-step conclusion-asking flow.

In both cases the returned `(conclusion, conditions)` pair is handed to `_insert_rule`,
which decides whether to seed the tree, add an `Alternative`, or add a `Refinement`
depending on what the current trace says fired.

### `Expert.ask_for_rule` — the two-step sequence

```python
# expert.py — simplified
def ask_for_rule(self, case, case_variable, conclusion_domain, current, trace):
    context = CaseContext(case_instance=case, case_variable=case_variable,
                          current_conclusion=current, conclusion_domain=conclusion_domain,
                          aids=self.aids, trace=trace)
    conclusion = self._ask_for_conclusion(context, conclusion_domain)
    if conclusion is UNSET or conclusion == current:
        return current, None          # keep current; conditions skipped
    conditions = self.ask_for_conditions(case, case_variable, conclusion, current, trace)
    return conclusion, conditions
```

The key design point: the conditions step calls the **same** `ask_for_conditions` that
ground-truth fitting calls, with the chosen conclusion passed as `target_conclusion`.
There is no separate conditions-collection logic for the no-target path.

### `Expert._ask_for_conclusion` — the focused conclusion question

Before calling `interact`, the expert:

1. Builds a **layered validator** via `make_conclusion_validator(domain, allow_unset)`.
2. Consults each `ConclusionAid.suggest` and picks the first suggestion that passes the
   validator as the `AnswerRequest.default` (pre-seeds the namespace).
3. Uses `domain.example_for("conclusion")` as the copy-pasteable example.

The `allow_unset` flag is `True` when `context.has_current_conclusion` — meaning a rule
already fired.  This lets the expert press Ctrl-D without typing anything, which leaves
the `"conclusion"` name bound to `UNSET` (the initial default), signalling "keep the
current conclusion".

### `ConclusionDomain` — type-derived value set

`resolve_conclusion_domain(owner_type, attr_name)` reads the type annotation and
produces a `ConclusionDomain(frozen dataclass)`:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain
import enum
from dataclasses import dataclass
from typing_extensions import Optional

class Species(enum.Enum):
    mammal = "mammal"
    bird = "bird"
    fish = "fish"

@dataclass
class Animal:
    name: str
    backbone: bool
    species: Optional[Species] = None

domain = resolve_conclusion_domain(Animal, "species")
print("is_enumerable   :", domain.is_enumerable)
print("members         :", domain.members)
print("allows_none     :", domain.allows_none)
print("expected_types  :", domain.expected_types)
print("namespace_bind  :", domain.namespace_bindings())
print("example         :", domain.example_for("conclusion"))
```

`namespace_bindings()` returns `{"Species": Species}` — the interactive shell injects
this so the expert can type `Species.<tab>` for tab-completion.

`contains(value)` is type-aware: it checks `type(value) is type(member)` first, which
correctly rejects `1` when the domain is a `bool` domain (`1 == True` in Python but
`type(1) is not type(True)`).

### The `UNSET` sentinel vs. `None`

`UNSET` is a singleton of `_Unset` used to distinguish two conceptually different states:

| Value | Meaning |
|---|---|
| `UNSET` | Nothing was supplied — no rule fired, or the expert has not answered yet |
| `None` | A deliberate `null` label (valid only when the annotation is `Optional`) |

The validator distinguishes them: returning `None` for a non-optional domain is an
error; leaving the name `UNSET` when no current conclusion stands is also an error.
Conflating them would silently accept unanswered questions.

### The layered validator

`make_conclusion_validator(domain, allow_unset)` builds one closure that layers four
checks in order:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.expert import make_conclusion_validator
from krrood.entity_query_language.rdr.utils import UNSET

validator = make_conclusion_validator(domain, allow_unset=False)

# UNSET is rejected when no current conclusion stands.
print(validator(UNSET))

# None is rejected when the annotation is not Optional.
# (domain.allows_none is True here because of Optional[Species])
print(validator(None))  # None — allowed by Optional[Species]

# Out-of-domain value rejected.
print(validator("mammal"))

# Valid member accepted.
print(validator(Species.mammal))
```

---

## `ConclusionAid` — the Extension Seam

`ConclusionAid` is a plain ABC with two optional hooks that both default to `None`:

```python
# aid.py
class ConclusionAid:
    def present(self, context: CaseContext) -> Optional[str]: ...   # informational text
    def suggest(self, context: CaseContext) -> Optional[Any]: ...   # candidate conclusion
```

An aid implements whichever hook is useful:

- **Presenter-only** (e.g. show a screenshot, a plot, or a similar-case table).
- **Suggester-only** (e.g. a heuristic, a nearest-neighbour classifier, or an LLM).
- **Both** (e.g. an ML model that explains and proposes).

### How aids wire in

```{code-cell} ipython3
from krrood.entity_query_language.rdr.aid import ConclusionAid

# A suggester that proposes Species.mammal whenever the animal has backbone=True.
class BackboneAid(ConclusionAid):
    def suggest(self, context):
        if getattr(context.case_instance, "backbone", False):
            return Species.mammal
        return None

    def present(self, context):
        animal = context.case_instance
        return f"backbone={animal.backbone}  →  heuristic: mammal?"

aid = BackboneAid()
print("present:", aid.present(type("Ctx", (), {"case_instance": Animal("lion", True)})()))
print("suggest:", aid.suggest(type("Ctx", (), {"case_instance": Animal("lion", True)})()))
```

The validation guard in `Expert._suggested_conclusion` means an aid can return any
value — if it fails domain validation the suggestion is silently ignored and `UNSET`
stands as the default.  Aids never need to know the domain themselves.

### Worked example: a model-backed aid

```{code-cell} ipython3
from krrood.entity_query_language.rdr.aid import ConclusionAid
from krrood.entity_query_language.rdr.conclusion_domain import resolve_conclusion_domain

# Simulate a lightweight model that maps feature tuples to labels.
_MODEL = {
    (True, True):   Species.mammal,   # backbone + milk → mammal
    (True, False):  Species.fish,     # backbone, no milk → fish
    (False, False): Species.bird,     # no backbone, no milk → bird
}

class ModelAid(ConclusionAid):
    """Wraps a lookup table; real usage would call an ML model."""

    def _features(self, animal):
        milk = getattr(animal, "milk", False)
        return (animal.backbone, milk)

    def suggest(self, context):
        return _MODEL.get(self._features(context.case_instance))

    def present(self, context):
        features = self._features(context.case_instance)
        guess = _MODEL.get(features, "unknown")
        return f"Model input: {features}  →  predicted: {guess}"

# Quick smoke-test: suggestion is valid for a well-known animal.
@dataclass
class AnimalWithMilk:
    name: str
    backbone: bool
    milk: bool
    species: Optional[Species] = None

domain2 = resolve_conclusion_domain(AnimalWithMilk, "species")
validator2 = make_conclusion_validator(domain2, allow_unset=False)

class _Ctx:
    case_instance = AnimalWithMilk("lion", backbone=True, milk=True)

aid_model = ModelAid()
suggestion = aid_model.suggest(_Ctx())
print("suggestion       :", suggestion)
print("validation error :", validator2(suggestion))   # None = valid
print("present text     :", aid_model.present(_Ctx()))
```

### Informational-only aid

```{code-cell} ipython3
class SimilarCasesAid(ConclusionAid):
    """Shows the closest cases already in the dataset — no suggestion."""

    def __init__(self, known_cases, known_labels):
        self._cases = known_cases
        self._labels = known_labels

    def present(self, context):
        target = context.case_instance
        # Trivial proximity: same backbone value.
        similar = [
            (c, l) for c, l in zip(self._cases, self._labels)
            if c.backbone == target.backbone
        ][:3]
        if not similar:
            return "No similar cases found."
        lines = ["Similar cases:"]
        lines += [f"  {c.name} → {l.value}" for c, l in similar]
        return "\n".join(lines)

known = [Animal("dog", True), Animal("salmon", True), Animal("eagle", False)]
known_labels = [Species.mammal, Species.fish, Species.bird]
info_aid = SimilarCasesAid(known, known_labels)

class _Ctx2:
    case_instance = Animal("whale", True)

print(info_aid.present(_Ctx2()))
print("suggest:", info_aid.suggest(_Ctx2()))  # None — no suggestion
```

---

## `IPythonInterface` — the Interactive Mechanism

`IPythonInterface` overrides `_render_header` and `_build_namespace` from the base
`ExpertInterface`:

- **`_build_namespace`**: injects `domain.namespace_bindings()` so enum types
  tab-complete, caches `_aid_text` once per question, and registers tree/help/aid
  lambdas for the line magics.
- **`_render_header`** (no-target branch): calls `_labelling_lines` which emits the
  "what should this case conclude?" prompt, the allowed-values list, and the call to
  action for setting both `conclusion` and `conditions`.

The two-session split means `_render_header` is called once per session with the
appropriate `context.has_target` value:

- Session 1 (`conclusion`): `context.has_target` is `False` → `_labelling_lines`.
- Session 2 (`conditions`): `context.has_target` is `True` → `_framing_lines` as
  usual for ground-truth fitting.

The `shell_runner` constructor argument lets tests inject a plain function in place of
the real `InteractiveShellEmbed` launch, as demonstrated in the user guide.

---

## Benefits and Trade-offs

### Benefits

- **No training data required** — labels emerge incrementally from expert interaction.
- **Transparent rules** — every label is backed by an inspectable EQL condition.
- **Reuses the conditions path** — the ground-truth conditions flow is reused
  unchanged; there is no risk of the two paths diverging.
- **Open-ended extension** — adding a new `ConclusionAid` subclass is the only change
  needed to enrich the labelling experience.

### Trade-offs / Known Limitations

- **Single-class only** — `EQLSingleClassRDR` classifies one attribute per case.
  Multi-class or generative inference is not supported and out of scope for this
  feature.
- **Sequential, not parallel** — the two steps happen in serial; there is no way to
  answer both in a single shell session.  This is a deliberate simplicity choice
  (each session's validation is independent), but it adds one round-trip for the expert.
- **No aid priority ordering** — when multiple aids are present, the first valid
  `suggest()` wins.  There is no ranking or ensemble mechanism.
- **`FunctionInterface` loops on invalid answers** — if `answer_fn` always returns an
  invalid value the `interact` loop will run forever.  The function is expected to be
  deterministic and correct; tests must supply valid answers.

---

## How to Add a New `ConclusionAid`

1. Subclass `ConclusionAid` in any module (no registration needed).
2. Override `present` and/or `suggest` as appropriate.
3. Pass an instance to `Expert(aids=[...])`.

The `Expert` iterates `aids` in order:
- All `present()` outputs are concatenated and shown once per question (header + `%aid` magic).
- The first `suggest()` that returns a non-`None` value **and** passes `make_conclusion_validator` is used as the pre-seeded default.

No other file needs to change.

---

## Extension Points Summary

| What you want | Where to change |
|---|---|
| Add a heuristic or ML-model suggestion | New `ConclusionAid` subclass; pass to `Expert(aids=[...])` |
| Add an information panel | New `ConclusionAid` subclass overriding `present` |
| Change how the conclusion question is rendered | Override `IPythonInterface._labelling_lines` |
| Add a new shell line magic | `IPythonInterface._build_namespace` → add a key + `_register_namespace_magic` |
| Support a new conclusion type | `conclusion_domain._enumerate_members` — add a branch for the new type |
| Use a custom I/O back-end | Subclass `ExpertInterface`; implement `_run` |

---

## API Reference

- {py:class}`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
- {py:meth}`~krrood.entity_query_language.rdr.expert.Expert.ask_for_rule`
- {py:func}`~krrood.entity_query_language.rdr.expert.make_conclusion_validator`
- {py:class}`~krrood.entity_query_language.rdr.conclusion_domain.ConclusionDomain`
- {py:func}`~krrood.entity_query_language.rdr.conclusion_domain.resolve_conclusion_domain`
- {py:class}`~krrood.entity_query_language.rdr.aid.ConclusionAid`
- {py:class}`~krrood.entity_query_language.rdr.interactive.IPythonInterface`
- {py:class}`~krrood.entity_query_language.rdr.interface.FunctionInterface`
- {py:data}`~krrood.entity_query_language.rdr.utils.UNSET`
