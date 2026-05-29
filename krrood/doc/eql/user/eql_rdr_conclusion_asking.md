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

# Labelling Cases Without Ground Truth

In the basic RDR fitting workflow, you already know the correct conclusion for each
case — you pass it as `target` and the expert only has to write the conditions that
distinguish it.  Real annotation work often goes the other direction: you have a pile
of unlabelled cases and want the RDR to grow as you label them one by one.

This guide covers the **conclusion-asking** path: calling `fit_case` without a `target`
so the expert is asked *both* what the case should conclude *and* the conditions that
justify it.

## Running Example

All cells in this guide use the same small museum-collection scenario defined in
`rdr_conclusion_domain.py`.  Each `Exhibit` has observable features and a `kind`
attribute drawn from the `ExhibitKind` enum.  A human cataloguer (or a programmatic
stub in these cells) labels each exhibit and writes the EQL conditions that make the
label stick.

```{code-cell} ipython3
:tags: [remove-cell]

import sys
from pathlib import Path

# rdr_conclusion_domain.py lives in doc/eql/user/.
# When the notebook kernel runs from test_tmp/, Path("..") resolves there.
for _candidate in [Path("doc/eql/user"), Path("eql/user"), Path(".."), Path(".")]:
    if (_candidate / "rdr_conclusion_domain.py").exists():
        sys.path.insert(0, str(_candidate.resolve()))
        break
```

```{code-cell} ipython3
from rdr_conclusion_domain import Exhibit, ExhibitKind, EXHIBITS, LABELS

# A quick look at the data we will classify.
for exhibit, label in zip(EXHIBITS, LABELS):
    print(f"{exhibit.name:12s}  material={exhibit.material:6s}  "
          f"size={exhibit.size_cm:5.1f}cm  "
          f"inscription={exhibit.has_inscription}  → {label.value}")
```

## Step 1 — Create an RDR for the Unlabelled Attribute

`EQLSingleClassRDR` takes the case type and the name of the attribute it should
predict.  Nothing else is needed at construction time.

```{code-cell} ipython3
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

rdr = EQLSingleClassRDR(Exhibit, "kind")
print("case type            :", rdr.case_type.__name__)
print("conclusion attribute :", rdr.conclusion_attribute_name)
```

Before any fitting, `classify` returns `None` for every case — the tree is empty.

```{code-cell} ipython3
first_exhibit = EXHIBITS[0]
print("classification before fitting:", rdr.classify(first_exhibit))
```

## Step 2 — Inspect the Conclusion Domain

The RDR reads the type annotation on `Exhibit.kind` and derives the allowable values
automatically.  You can inspect this domain before the first fit.

```{code-cell} ipython3
domain = rdr.conclusion_domain
print("is_enumerable :", domain.is_enumerable)
print("members       :", domain.members)
print("allows_none   :", domain.allows_none)
print("display()     :", domain.display())
print("example       :", domain.example_for("conclusion"))
```

Because `kind` is typed as `ExhibitKind` (an `enum.Enum`), the domain is enumerable —
the three members are automatically discovered.  This information is used to validate
expert answers and, in the interactive shell, to show the allowed values and inject
the enum class for tab-completion.

## Step 3 — Write a Programmatic Expert

For headless execution (notebooks, CI, tests) you supply a `FunctionInterface` whose
`answer_fn` receives a `CaseContext` and the list of `AnswerRequest` objects and
returns the answers as a plain dict.

On the conclusion-asking path the function is called **twice** per case:

1. With a single `"conclusion"` request — the expert chooses the label.
2. With a single `"conditions"` request — the expert writes the EQL expression.

```{code-cell} ipython3
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.expert import Expert

label_map = dict(zip([e.name for e in EXHIBITS], LABELS))

def answer_fn(context, requests):
    """Simulates a human cataloguer: label from the map, conditions from features."""
    answers = {}
    # Conclusion step: which kind is this exhibit?
    if any(r.name == "conclusion" for r in requests):
        answers["conclusion"] = label_map[context.case_instance.name]
    # Conditions step: what distinguishes this exhibit?
    if any(r.name == "conditions" for r in requests):
        case = context.case_instance
        cv = context.case_variable  # the shared EQL variable — build expressions over it
        answers["conditions"] = cv.material == case.material
    return answers

expert = Expert(interface=FunctionInterface(answer_fn=answer_fn))
```

The `context.case_variable` attribute is the shared EQL variable that the whole rule
tree ranges over.  Conditions **must** be built over this variable, not over the
concrete `case_instance`.

## Step 4 — Fit One Case at a Time

Call `fit_case(case, expert=expert)` — omit `target`.  The expert is consulted
automatically, the rule is inserted, and the method returns the chosen conclusion.

```{code-cell} ipython3
returned = rdr.fit_case(EXHIBITS[0], expert=expert)
print("returned conclusion :", returned)
print("classify EXHIBITS[0]:", rdr.classify(EXHIBITS[0]))
```

## Step 5 — Fit the Rest of the Collection

Call `fit` with no `targets` argument to label every case:

```{code-cell} ipython3
# Remaining exhibits (EXHIBITS[0] is already fitted).
for exhibit in EXHIBITS[1:]:
    rdr.fit_case(exhibit, expert=expert)

# Verify all cases classify correctly.
for exhibit, label in zip(EXHIBITS, LABELS):
    result = rdr.classify(exhibit)
    status = "OK" if result == label else "FAIL"
    print(f"[{status}] {exhibit.name}: classified as {result!r}, expected {label!r}")
```

Alternatively, pass all cases to `fit` in one call.  Omitting `targets` triggers the
same conclusion-asking path for each case (each paired with `UNSET` internally):

```{code-cell} ipython3
rdr2 = EQLSingleClassRDR(Exhibit, "kind")
rdr2.fit(EXHIBITS, expert=expert)
print("fit() result:", all(rdr2.classify(e) == l for e, l in zip(EXHIBITS, LABELS)))
```

## Step 6 — What Happens When a Rule Already Fires

If the expert is asked about a case the tree already classifies, they can re-confirm the
current conclusion by returning it again.  When the expert's conclusion matches the
current one, no rule is inserted and `fit_case` returns immediately.

```{code-cell} ipython3
from krrood.entity_query_language.rdr.utils import UNSET

call_count = {"n": 0}

def reaffirming_fn(context, requests):
    call_count["n"] += 1
    answers = {}
    if any(r.name == "conclusion" for r in requests):
        # Return the same value the RDR already concludes.
        answers["conclusion"] = rdr.classify(context.case_instance)
    return answers

reaffirm_expert = Expert(interface=FunctionInterface(answer_fn=reaffirming_fn))
result = rdr.fit_case(EXHIBITS[0], expert=reaffirm_expert)
print("returned conclusion:", result)
print("answer_fn called   :", call_count["n"], "time(s) — conditions step was skipped")
```

The conditions step is skipped entirely when the expert keeps the current conclusion.

## Step 7 — Plugging In a `ConclusionAid`

A `ConclusionAid` enriches the labelling session with optional *presentation* (extra
context for the expert) and optional *suggestion* (a candidate conclusion that
pre-seeds the answer).

Here is a simple suggester that looks up a lightweight heuristic:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.aid import ConclusionAid

class MaterialHeuristicAid(ConclusionAid):
    """Suggests a kind based purely on material — fast but imprecise."""

    _HINTS = {
        "clay": ExhibitKind.pottery,
        "gold": ExhibitKind.jewelry,
        "stone": ExhibitKind.tablet,
    }

    def suggest(self, context):
        exhibit = context.case_instance
        return self._HINTS.get(exhibit.material)  # None if material is unknown

    def present(self, context):
        exhibit = context.case_instance
        guess = self._HINTS.get(exhibit.material, "unknown")
        return f"Heuristic: material '{exhibit.material}' → likely {guess}"
```

Pass the aid to `Expert` and it is consulted before the conclusion question is shown:

```{code-cell} ipython3
aided_expert = Expert(
    interface=FunctionInterface(answer_fn=answer_fn),
    aids=[MaterialHeuristicAid()],
)

rdr3 = EQLSingleClassRDR(Exhibit, "kind")
rdr3.fit(EXHIBITS, expert=aided_expert)
print("With aid:", all(rdr3.classify(e) == l for e, l in zip(EXHIBITS, LABELS)))
```

When the heuristic suggestion is a valid domain member the expert can accept it by
simply not overriding the `"conclusion"` key — the pre-seeded default stands.

## Step 8 — Serializing and Reloading the Tree

A tree grown by conclusion-asking serializes and loads the same way as any other EQL RDR:

```{code-cell} ipython3
import os
import tempfile
from krrood.entity_query_language.rdr.serialization import save_rdr, load_rdr

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "exhibit_rdr.py")
    save_rdr(rdr, path)

    # Show the first few lines of the saved Python module.
    with open(path) as f:
        print(f.read()[:500], "...")

    loaded = load_rdr(path)

# The loaded tree classifies identically.
all_match = all(rdr.classify(e) == loaded.classify(e) for e in EXHIBITS)
print("Round-trip identical:", all_match)
```

## Available Features Overview

| Feature | How |
|---|---|
| Label a single case | `fit_case(case, expert=expert)` — omit `target` |
| Label many cases | `fit(cases, expert=expert)` — omit `targets` |
| Inspect allowed values | `rdr.conclusion_domain` |
| Re-confirm current label | Return the current conclusion; no rule is inserted |
| Pre-seed with a heuristic | `Expert(aids=[MyAid()])` |
| Save to disk | `save_rdr(rdr, path)` |
| Reload from disk | `load_rdr(path)` |
| Interactive shell | `Expert(interface=IPythonInterface())` — see prose below |

## The Interactive Shell Experience

When you use `IPythonInterface` (the default for notebooks and terminal sessions), the
conclusion-asking path presents two successive embedded IPython sessions per unlabelled
case.

**First session — choose the conclusion.**  The header shows the case table, the
allowable values, and (if an aid is configured) any presentation text.  The expert
assigns the chosen value to `conclusion`:

```
┌─────────────────────────────────────────────────────────┐
│  name     │ material │ size_cm │ has_inscription │ kind │
│  Bowl-1   │ clay     │  12.0   │ False           │ None │
└─────────────────────────────────────────────────────────┘
No rule fired — what should this case conclude?
Choose one of: <ExhibitKind.pottery: 'pottery'>, ...
Set the conclusion, then justify it with a condition.
Type %help / %aid for help with this case.
In [1]: conclusion = ExhibitKind.pottery
In [2]: ^D
```

**Second session — write the conditions.**  The chosen conclusion becomes the known
target, and the standard conditions-only session opens.  The expert writes an EQL
expression over `case_variable`:

```
Ground-truth conclusion: <ExhibitKind.pottery: 'pottery'>
Current conclusion:      UNSET
No rule fired for this case.
Write a condition that fires for it.
In [1]: conditions = case_variable.material == "clay"
In [2]: ^D
```

The magics `%help`, `%show_tree`, and `%aid` are available throughout.

## End-to-End Example

```{code-cell} ipython3
# Full flow in one cell: create, fit without targets, verify, persist.
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.serialization import save_rdr, load_rdr
from rdr_conclusion_domain import Exhibit, ExhibitKind, EXHIBITS, LABELS
import os, tempfile

_label_map = dict(zip([e.name for e in EXHIBITS], LABELS))

def _answer(context, requests):
    case = context.case_instance
    cv = context.case_variable
    result = {}
    if any(r.name == "conclusion" for r in requests):
        result["conclusion"] = _label_map[case.name]
    if any(r.name == "conditions" for r in requests):
        result["conditions"] = cv.material == case.material
    return result

rdr_e2e = EQLSingleClassRDR(Exhibit, "kind")
rdr_e2e.fit(EXHIBITS, expert=Expert(interface=FunctionInterface(answer_fn=_answer)))

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "exhibit_e2e.py")
    save_rdr(rdr_e2e, path)
    loaded_e2e = load_rdr(path)

print("All correct:", all(loaded_e2e.classify(e) == l for e, l in zip(EXHIBITS, LABELS)))
```

## Learn More

- {py:class}`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR` —
  the main entry point: `fit_case`, `fit`, `classify`, `conclusion_domain`, `render_tree`.
- {py:class}`~krrood.entity_query_language.rdr.expert.Expert` — holds the interface and
  the list of aids; `ask_for_rule` is the no-target path.
- {py:class}`~krrood.entity_query_language.rdr.interface.FunctionInterface` — programmatic
  expert for tests and headless notebooks.
- {py:class}`~krrood.entity_query_language.rdr.interactive.IPythonInterface` — embedded
  IPython expert for interactive sessions.
- {py:class}`~krrood.entity_query_language.rdr.conclusion_domain.ConclusionDomain` and
  {py:func}`~krrood.entity_query_language.rdr.conclusion_domain.resolve_conclusion_domain` —
  how allowable values are derived from the type annotation.
- {py:class}`~krrood.entity_query_language.rdr.aid.ConclusionAid` — base class for pluggable
  presentation and suggestion aids.
- {py:func}`~krrood.entity_query_language.rdr.serialization.save_rdr` /
  {py:func}`~krrood.entity_query_language.rdr.serialization.load_rdr` — persistence.
- {doc}`writing_rule_trees` — background on how EQL rule trees are structured.
- Developer guide: {doc}`../developer/eql_rdr_conclusion_asking` — design rationale and
  extension points.
