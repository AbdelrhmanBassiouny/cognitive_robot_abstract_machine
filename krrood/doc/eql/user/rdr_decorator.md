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

# Attaching an RDR to a Function with `@rdr`

The `@rdr` decorator wraps any fully-annotated Python function and attaches an
EQL-native Ripple Down Rules (RDR) classifier to it.  The case type is generated
automatically from the function's own signature — no handwritten dataclass needed.

This guide walks from the simplest possible usage to a complete end-to-end example.
Every step uses the same running domain: a robot grasping planner that predicts a
**grasp force** (in Newtons) for an object based on its weight (kg) and material.

## Setup — Define the Domain Types

```{code-cell} ipython3
import enum
from dataclasses import dataclass
from typing_extensions import ClassVar
```

## Step 1 — Apply the Decorator

`@rdr` takes a filename for the model file and wraps the function.  Use an absolute
path (or a relative name — see [Available Features](#available-features-overview)):

```{code-cell} ipython3
import tempfile, os
from krrood.entity_query_language.rdr.decorator import rdr

_tmp = tempfile.mkdtemp()
_model_file = os.path.join(_tmp, "force_model.py")

@rdr(_model_file)
def predict_force(weight_kg: float, material: str) -> float:
    """Default fallback: 5.0 Newtons for anything unfamiliar."""
    return 5.0

print(type(predict_force))
print("__name__  :", predict_force.__name__)
print("__doc__   :", predict_force.__doc__)
```

The decorator preserves `__name__` and `__doc__` via `functools.update_wrapper`.
Callers that introspect the function (logging, dispatch tables) see the original
metadata.

## Step 2 — Call It Like a Regular Function

With no rules fitted yet the wrapper calls through to the original function and
returns its output unchanged:

```{code-cell} ipython3
# No rules yet — returns the fallback.
result = predict_force(0.1, "plastic")
print("result:", result)
```

## Step 3 — Inspect the Auto-Generated Case Type

The decorator wrote a `FunctionCase` subclass to `_model_file` and loaded it.
Inspect `wrapper.case_type` to see what was generated:

```{code-cell} ipython3
CaseType = predict_force.case_type

print("case type name :", CaseType.__name__)
print("is FunctionCase:", issubclass(CaseType, __import__(
    "krrood.entity_query_language.rdr.function_case", fromlist=["FunctionCase"]
).FunctionCase))

# The fields mirror the function signature plus _output for the return value.
import dataclasses
for f in dataclasses.fields(CaseType):
    print(f"  field {f.name!r}: {f.type}")
```

The class has one field per annotated parameter plus `_output` for the return value.
The original function is bound as a `ClassVar` so the file stays self-contained.

## Step 4 — Access the Underlying RDR

`wrapper.rdr` is a live `EQLSingleClassRDR`.  You can inspect it, call `classify`
directly, or grow the tree with `fit_case`:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

print("rdr type       :", type(predict_force.rdr).__name__)
print("conclusion attr:", predict_force.rdr.conclusion_attribute_name)
print("classify (no rules):", predict_force.rdr.classify(
    CaseType(weight_kg=0.5, material="metal", _output=5.0)
))
```

## Step 5 — Fit a Rule Manually

Use `wrapper.fit_case` with a scripted `Expert` to teach one rule.  Here we teach
the RDR to predict 20.0 N for heavy objects (weight above 1 kg):

```{code-cell} ipython3
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.utils import UNSET

def _answer_fn(context, requests):
    """Simulate an expert: 20.0 N for heavy objects, 5.0 N otherwise."""
    answers = {}
    if any(r.name == "conclusion" for r in requests):
        answers["conclusion"] = 20.0
    if any(r.name == "conditions" for r in requests):
        answers["conditions"] = context.case_variable.weight_kg > 1.0
    return answers

expert = Expert(interface=FunctionInterface(answer_fn=_answer_fn))

# Build a case for a heavy metal object.
heavy_case = CaseType(weight_kg=2.5, material="metal", _output=5.0)
predict_force.fit_case(heavy_case, target=UNSET, expert=expert)

print("heavy object (2.5 kg):", predict_force(2.5, "metal"))
print("light object (0.1 kg):", predict_force(0.1, "plastic"))
```

The heavy object gets 20.0 N from the rule; the light object still falls through to
the original function's 5.0 N default.

## Step 6 — Verify Auto-Save

Every rule insertion automatically rewrites the model file as a self-contained
Python module.  After fitting, the file can be reloaded in any future process:

```{code-cell} ipython3
with open(_model_file) as f:
    text = f.read()

# Show the first part of the file — the auto-generated dataclass.
print(text[:700])
print("...")
```

## Step 7 — Reload from File

`load_rdr` reads the saved file and reconstructs the same tree:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.serialization import load_rdr

loaded_rdr = load_rdr(_model_file)
print("loaded — heavy (2.5 kg):", loaded_rdr.classify(
    CaseType(weight_kg=2.5, material="metal", _output=5.0)))
print("loaded — light (0.1 kg):", loaded_rdr.classify(
    CaseType(weight_kg=0.1, material="plastic", _output=5.0)))
```

## Step 8 — Fit Mode: Data Collection

Pass `fit=True` to the decorator to flip the wrapper into **fit mode**.  In this
mode every call invokes `rdr.fit_case` on the expert so you can build up a labelled
dataset while the function runs normally.  The original return value is always
returned to the caller — nothing is overridden:

```{code-cell} ipython3
_fit_file = os.path.join(_tmp, "force_fit.py")

@rdr(_fit_file, fit=True, expert=Expert(interface=FunctionInterface(answer_fn=_answer_fn)))
def predict_force_fit(weight_kg: float, material: str) -> float:
    """Fallback force used while collecting labels."""
    return 5.0

# In fit mode every call feeds the expert.
r1 = predict_force_fit(2.5, "metal")    # triggers fit_case
r2 = predict_force_fit(0.1, "plastic")  # triggers fit_case

# The caller always gets the original output, regardless of any rule.
print("call 1 returned (fit mode):", r1)
print("call 2 returned (fit mode):", r2)
```

## Available Features Overview

| Feature | How |
|---|---|
| Attach an RDR to a function | `@rdr("model.py")` — inference mode (default) |
| Build labels interactively | `@rdr("model.py", fit=True, expert=e)` — fit mode |
| Wire a permanent expert | `@rdr("model.py", expert=e)` |
| Call the function normally | `wrapper(...)` — original output if no rule fires (inference) or always (fit) |
| Manual single-case fit | `wrapper.fit_case(case, target=UNSET, expert=e)` |
| Batch fit | `wrapper.fit(cases, targets=None, expert=e)` |
| Inspect generated case type | `wrapper.case_type` |
| Access the underlying RDR | `wrapper.rdr` |
| Reload from file | `load_rdr(path)` — returns an `EQLSingleClassRDR` |
| Auto-save path | `wrapper.rdr.save_path` — set automatically to the store path |

## End-to-End Example

```{code-cell} ipython3
# One consolidated cell: decorate, fit all objects, verify, reload.
import tempfile, os
from krrood.entity_query_language.rdr.decorator import rdr
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.serialization import load_rdr
from krrood.entity_query_language.rdr.utils import UNSET

_e2e_tmp = tempfile.mkdtemp()
_e2e_file = os.path.join(_e2e_tmp, "force_e2e.py")

# Ground truth: three weight bands produce different forces.
_OBJECTS = [
    ("Milk",    1.05, "plastic", 20.0),
    ("Apple",   0.18, "organic",  5.0),
    ("Wrench",  0.45, "metal",   12.0),
    ("Battery", 2.30, "metal",   20.0),
    ("Sponge",  0.05, "foam",     5.0),
    ("Bowl",    0.35, "ceramic", 12.0),
]

def _e2e_answer(context, requests):
    answers = {}
    w = context.case_instance.weight_kg
    if any(r.name == "conclusion" for r in requests):
        answers["conclusion"] = 20.0 if w > 1.0 else (12.0 if w > 0.3 else 5.0)
    if any(r.name == "conditions" for r in requests):
        cv = context.case_variable
        if w > 1.0:
            answers["conditions"] = cv.weight_kg > 1.0
        elif w > 0.3:
            answers["conditions"] = cv.weight_kg > 0.3
        else:
            answers["conditions"] = cv.weight_kg <= 0.3
    return answers

@rdr(_e2e_file)
def plan_force_e2e(weight_kg: float, material: str) -> float:
    return 5.0

e2e_expert = Expert(interface=FunctionInterface(answer_fn=_e2e_answer))

# Fit each object.
for name, weight, material, label in _OBJECTS:
    plan_force_e2e.fit_case(
        plan_force_e2e.case_type(weight_kg=weight, material=material, _output=5.0),
        target=UNSET,
        expert=e2e_expert,
    )

# Verify via the wrapper.
for name, weight, material, label in _OBJECTS:
    got = plan_force_e2e(weight, material)
    status = "OK" if got == label else "FAIL"
    print(f"[{status}] {name:8s} weight={weight:5.2f}kg → {got:5.1f}N (expected {label:5.1f}N)")

# Round-trip through the file.
loaded = load_rdr(_e2e_file)
round_trip_ok = all(
    loaded.classify(plan_force_e2e.case_type(weight_kg=w, material=m, _output=5.0)) == l
    for _, w, m, l in _OBJECTS
)
print("Round-trip identical:", round_trip_ok)
```

## Learn More

- {py:class}`~krrood.entity_query_language.rdr.decorator.RDRWrapper` — the object
  returned by `@rdr`; exposes `rdr`, `case_type`, `fit_case`, and `fit`.
- {py:func}`~krrood.entity_query_language.rdr.decorator.rdr` — the decorator factory;
  see `filename`, `fit`, and `expert` parameters.
- {py:class}`~krrood.entity_query_language.rdr.function_case.FunctionCase` — base class
  for all auto-generated case types.
- {py:class}`~krrood.entity_query_language.rdr.file_store.RDRFileStore` — manages the
  model file lifecycle; `path`, `exists`, `load_case_type`, `save`.
- {py:class}`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR` — the
  underlying classifier; `fit_case`, `fit`, `classify`, `render_tree`.
- {py:func}`~krrood.entity_query_language.rdr.serialization.load_rdr` — reload a saved
  model file into a fresh `EQLSingleClassRDR`.
- {doc}`writing_rule_trees` — background on how EQL rule trees are authored and structured.
- {doc}`eql_rdr_conclusion_asking` — grow an RDR from unlabelled cases interactively.
- Developer guide: {doc}`../developer/rdr_decorator` — design rationale, generated-file
  anatomy, and extension points.
