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

# Giving a Function a Rule Tree with `@rdr`

`@rdr` attaches a Ripple Down Rules classifier to any fully annotated function. The case
type is generated from the function's own signature, so there is no dataclass to write by
hand, and the rules live in a Python file beside the function.

Every step below uses one running example: a grasping planner predicting the force, in
Newtons, needed to pick an object up given its weight in kilograms and its material.

## Applying the Decorator

`@rdr` takes the name of the model file. An absolute path is used as given; a relative
name lands in an `_rdr_models/` directory beside the decorated function's own module.

```{code-cell} ipython3
import os
import tempfile

from krrood.entity_query_language.rdr.decorator import rdr

model_file = os.path.join(tempfile.mkdtemp(), "force_model.py")


@rdr(model_file)
def predict_force(weight: float, material: str) -> float:
    """Fall back to 5 N for anything no rule recognises."""
    return 5.0


print("type     :", type(predict_force).__name__)
print("__name__ :", predict_force.__name__)
print("__doc__  :", predict_force.__doc__)
```

The wrapper keeps the function's own `__name__` and `__doc__`, so callers that introspect
it - logging, dispatch tables, documentation tools - still see the function they expect.

## Calling It

With no rules fitted yet, the call runs the function and hands back what it returned:

```{code-cell} ipython3
print("no rules yet:", predict_force(0.1, "plastic"))
```

## The Generated Case Type

The decorator wrote a case class to the model file and read it back. It carries one field
per annotated parameter, plus `_output` for the return value - the attribute the rule tree
predicts:

```{code-cell} ipython3
import dataclasses

case_type = predict_force.case_type
print("case type:", case_type.__name__)
for case_field in dataclasses.fields(case_type):
    print(f"  {case_field.name}: {case_field.type}")
```

## The Rule Tree Underneath

`predict_force.rdr` is a live `EQLSingleClassRDR`. It can be inspected, asked to classify
a case directly, or grown with `fit_case`:

```{code-cell} ipython3
print("predicts       :", predict_force.rdr.conclusion_attribute_name)
print("classify, empty:", predict_force.rdr.classify(
    case_type(weight=0.5, material="metal", _output=5.0)
))
```

`...` is what an empty tree answers with: no rule fired, so there is nothing to say.

## Teaching It a Rule

Fitting asks an expert two questions - what this case's conclusion is, and which
conditions justify it. `FunctionInterface` answers them from a plain function, which is
how a rule gets authored without a person at a terminal:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface

HEAVY_FORCE = 20.0


def answer_for_heavy_objects(context, requests):
    """Conclude 20 N, justified by the object weighing more than a kilogram."""
    answers = {AnswerName.CONDITIONS: context.case_variable.weight > 1.0}
    if any(request.name is AnswerName.CONCLUSION for request in requests):
        answers[AnswerName.CONCLUSION] = HEAVY_FORCE
    return answers


expert = Expert(interface=FunctionInterface(answer_function=answer_for_heavy_objects))

predict_force.fit_case(
    case_type(weight=2.5, material="metal", _output=5.0), expert=expert
)

print("heavy (2.5 kg):", predict_force(2.5, "metal"))
print("light (0.1 kg):", predict_force(0.1, "plastic"))
```

The heavy object gets the rule's 20 N. The light one matches no rule, so the answer is
what the function itself returned.

## Where the Rules Are Kept

The decorator hands its own file store to the rule tree as the tree's `model_saver`, so a
fit writes the whole model - the case class and the rules - back to the file as it
finishes:

```{code-cell} ipython3
print("saves through:", type(predict_force.rdr.model_saver).__name__)
print("file         :", predict_force.store.path)
print()
print(open(model_file).read()[:600], "...")
```

## Reading a Model Back

`load_rdr` rebuilds the same tree from the file, so a later process - or a later run of
the same decorated function - picks up where fitting left off:

```{code-cell} ipython3
from krrood.entity_query_language.rdr.serialization import load_rdr

reloaded = load_rdr(model_file)
print("heavy:", reloaded.classify(case_type(weight=2.5, material="metal", _output=5.0)))
print("light:", reloaded.classify(case_type(weight=0.1, material="plastic", _output=5.0)))
```

The light object answers `...` here rather than 5 N: a bare rule tree reports that no rule
fired, and falling back to the function's own return value is the wrapper's doing.

## Fit Mode

`fit=True` turns every call into an opportunity to grow the tree. The caller always gets
the function's own return value, so a function in fit mode behaves exactly as it did
before while the rules are being written:

```{code-cell} ipython3
fit_model_file = os.path.join(tempfile.mkdtemp(), "force_fit_model.py")


@rdr(fit_model_file, fit=True, expert=expert)
def collect_force(weight: float, material: str) -> float:
    """Fall back to 5 N while labels are being collected."""
    return 5.0


print("heavy call returned:", collect_force(2.5, "metal"))
print("rules after the call:", collect_force.rdr.query is not None)
```

## What `@rdr` Gives You

| To do this | Write this |
|---|---|
| Classify every call | `@rdr("model.py")` |
| Grow the tree from every call | `@rdr("model.py", fit=True, expert=expert)` |
| Name the expert once | `@rdr("model.py", expert=expert)` |
| Fit one case | `wrapper.fit_case(case, expert=expert)` |
| Fit a batch | `wrapper.fit(cases, targets, expert)` |
| Reach the generated case class | `wrapper.case_type` |
| Reach the rule tree | `wrapper.rdr` |
| Reach the model file | `wrapper.store.path` |
| Read a model back | `load_rdr(path)` |

## End to End

Three weight bands, fitted from labelled objects and then checked through the wrapper and
through the file:

```{code-cell} ipython3
LIGHT_FORCE, MEDIUM_FORCE = 5.0, 12.0
OBJECTS = [
    ("Milk", 1.05, "plastic", HEAVY_FORCE),
    ("Apple", 0.18, "organic", LIGHT_FORCE),
    ("Wrench", 0.45, "metal", MEDIUM_FORCE),
    ("Battery", 2.30, "metal", HEAVY_FORCE),
    ("Sponge", 0.05, "foam", LIGHT_FORCE),
    ("Bowl", 0.35, "ceramic", MEDIUM_FORCE),
]


def answer_by_weight_band(context, requests):
    """Put each object in its weight band, and justify it with that band's bound."""
    weight = context.case_instance.weight
    case_variable = context.case_variable
    if weight > 1.0:
        conclusion, conditions = HEAVY_FORCE, case_variable.weight > 1.0
    elif weight > 0.3:
        conclusion, conditions = MEDIUM_FORCE, case_variable.weight > 0.3
    else:
        conclusion, conditions = LIGHT_FORCE, case_variable.weight <= 0.3
    answers = {AnswerName.CONDITIONS: conditions}
    if any(request.name is AnswerName.CONCLUSION for request in requests):
        answers[AnswerName.CONCLUSION] = conclusion
    return answers


end_to_end_file = os.path.join(tempfile.mkdtemp(), "force_end_to_end.py")


@rdr(end_to_end_file)
def plan_force(weight: float, material: str) -> float:
    """Fall back to 5 N for anything no rule recognises."""
    return LIGHT_FORCE


band_expert = Expert(interface=FunctionInterface(answer_function=answer_by_weight_band))

for name, weight, material, expected in OBJECTS:
    plan_force.fit_case(
        plan_force.case_type(weight=weight, material=material, _output=LIGHT_FORCE),
        expert=band_expert,
    )

for name, weight, material, expected in OBJECTS:
    predicted = plan_force(weight, material)
    outcome = "ok" if predicted == expected else "MISMATCH"
    print(f"[{outcome}] {name:8s} {weight:5.2f} kg -> {predicted:5.1f} N")

reloaded_plan = load_rdr(end_to_end_file)
print("same after reloading:", all(
    reloaded_plan.classify(
        plan_force.case_type(weight=weight, material=material, _output=LIGHT_FORCE)
    ) == expected
    for _, weight, material, expected in OBJECTS
))
```

## Learn More

- {py:class}`~krrood.entity_query_language.rdr.decorator.RDRWrapper` — what `@rdr`
  returns; carries `rdr`, `case_type`, `store`, `fit_case` and `fit`.
- {py:func}`~krrood.entity_query_language.rdr.decorator.rdr` — the decorator itself, and
  its `filename`, `expert` and `fit` arguments.
- {py:class}`~krrood.entity_query_language.rdr.function_case.FunctionCase` — the base
  every generated case class inherits.
- {py:class}`~krrood.entity_query_language.rdr.file_store.RDRFileStore` — where the model
  file lives and how it is read and written.
- {py:class}`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR` — the rule
  tree itself; `classify`, `fit_case`, `fit`, `render_tree`.
- {py:func}`~krrood.entity_query_language.rdr.serialization.load_rdr` — read a model file
  back into a rule tree.
- {doc}`writing_rule_trees` — how EQL rule trees are authored and structured.
- {doc}`eql_rdr_conclusion_asking` — growing a tree from unlabelled cases, interactively.
- Developer guide: {doc}`../developer/rdr_decorator` — the design, the generated file's
  anatomy, and the extension points.
