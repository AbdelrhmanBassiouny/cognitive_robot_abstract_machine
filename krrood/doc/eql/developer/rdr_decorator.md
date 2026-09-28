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

# How `@rdr` Works

The design of the decorator in `krrood.entity_query_language.rdr.decorator`. The guide for
using it is {doc}`../user/rdr_decorator`.

## What It Is For

A rule tree needs three things a user would otherwise write by hand: a case type, a
variable over it, and somewhere to keep the rules. All three are already implied by an
annotated function, so `@rdr` derives them from its signature and leaves the caller with
one decorator line.

Two properties follow from that and are worth stating, because they constrain everything
below:

- **The wrapper is a drop-in for the function.** Callers see no change until a rule fires,
  and in fit mode they see no change at all.
- **The model file is self-contained.** It is an importable Python module holding the case
  class and the rules, so a model crosses processes without a pickle, a registry or a
  schema.

## Who Does What

| Class | Responsibility | Module |
|---|---|---|
| `rdr()` | Build the store and the wrapper from the decorator's arguments | `rdr/decorator.py` |
| `RDRWrapper` | Intercept calls, build cases, classify or fit | `rdr/decorator.py` |
| `RDRFileStore` | Resolve the model file's path, write it, read the case type back | `rdr/file_store.py` |
| `FunctionCase` | The base every generated case class inherits | `rdr/function_case.py` |
| `FunctionCaseGenerator` | Emit the `@dataclass` source for a case class | `code_generation/function_case.py` |
| `EQLSingleClassRDR` | Classify and fit; unchanged by the decorator | `rdr/single_class.py` |

`RDRFileStore` is a `ModelSaver`, which is what lets the wrapper hand it straight to the
rule tree: the tree persists itself through the same object the decorator resolved the
path with, and the wrapper never calls a save function of its own.

## Building the Wrapper

```{mermaid}
sequenceDiagram
    participant Factory as rdr(filename, ...)
    participant Wrapper as RDRWrapper.__post_init__
    participant Store as RDRFileStore
    participant Generator as FunctionCaseGenerator
    participant Tree as EQLSingleClassRDR

    Factory->>Store: RDRFileStore(function, filename)
    Factory->>Wrapper: RDRWrapper(function, store, expert, fit_mode)
    Wrapper->>Wrapper: bind the function to its own name
    Wrapper->>Store: exists()?
    alt no model yet
        Store-->>Wrapper: False
        Wrapper->>Generator: generate(function)
        Generator-->>Wrapper: case class source
        Wrapper->>Wrapper: append empty_rule_tree_source
        Wrapper->>Store: write both to path
        Wrapper->>Store: load_case_type()
        Wrapper->>Tree: EQLSingleClassRDR(case_type, "_output")
    else model on disk
        Store-->>Wrapper: True
        Wrapper->>Wrapper: load_rdr(store.path)
        Tree-->>Wrapper: the saved rule tree
    end
    Wrapper->>Wrapper: case_type.function = function
    Wrapper->>Tree: model_saver = store
```

### Reading a model while the module is still importing

The model file imports the decorated function back by name, which is what makes it
importable on its own. That import runs whenever the file is read - and the decorator
reads it *during* decoration, while the module defining the function is still executing
its own body. The `@` that binds the name has not run yet, so the import would hit a
partially initialized module and fail.

`function_bound_to_its_own_name` closes that window: it binds the undecorated function
under its own name for the duration of the read and restores whatever the module held
afterwards. That is what the decorator syntax is about to do one line later anyway, with
the wrapper in place of the function. Both branches need it, because a model read back
from disk imports the function exactly as a freshly written one does.

### The two invariants

Whichever branch ran, the wrapper then guarantees:

1. `case_type.function` is the live callable. A case class read back from a file carries
   whatever its own import resolved to; rewiring it means a case always calls the function
   that is actually decorated.
2. `rdr.model_saver` is the store. A fit persists to the decorated function's own model
   file rather than to the temporary file the rule tree would otherwise default to.

## What a Call Does

```python
def __call__(self, *args, **kwargs):
    output = self.function(*args, **kwargs)
    case = self._build_case(args, kwargs, output)
    if self.fit_mode:
        if self.expert is not None:
            self.rdr.fit_case(case, expert=self.expert)
        return output
    conclusion = self.rdr.classify(case)
    return output if conclusion is ... else conclusion
```

The function always runs first, so the case is built from the arguments and the return
value a real call produced and `_output` is never speculative.

`...` is the one thing that means "no rule fired", so a rule concluding `None` is honoured
like any other conclusion. That requires the function's return annotation to admit `None`,
since the conclusion is validated against the domain the annotation implies.

### Binding the arguments

`_build_case` normalises a call through `inspect.signature(...).bind` and
`apply_defaults`, so positional, keyword and defaulted arguments all reach the case the
same way. `self` and `cls` are dropped via `PythonBuiltinParameterNames`, which is what
lets the decorator work on methods as well as free functions.

## The Generated File

A freshly decorated function with no rules yet produces two sections. The first comes from
`FunctionCaseGenerator`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing_extensions import ClassVar, Callable, TYPE_CHECKING

from krrood.entity_query_language.rdr.function_case import FunctionCase
from my.module import select_strategy

if TYPE_CHECKING:
    from my.module import GraspStrategy


@dataclass
class SelectStrategy(FunctionCase):
    """
    FunctionCase for the `select_strategy` function.
    """
    weight: float
    material: str
    _output: GraspStrategy


SelectStrategy.function = select_strategy
```

The second comes from `empty_rule_tree_source`:

```python
"""Auto-generated EQL-RDR rule tree.
...
"""
from krrood.entity_query_language.factories import add, alternative, and_, entity, ...

selectStrategy = variable(SelectStrategy, domain=[])

# Stable handles for loading.
RDR_CASE_TYPE = SelectStrategy
RDR_CONCLUSION_ATTRIBUTE = "_output"
RDR_CASE_VARIABLE = selectStrategy
RDR_QUERY = None
```

The `RDR_*` names are the stable handles `load_rdr` and `RDRFileStore.load_case_type` read;
both sections take them from the constants in `rdr/serialization.py` rather than spelling
them out, so the writer and the reader cannot drift apart. `RDR_QUERY = None` is what an
empty tree looks like, and `load_rdr` reads it back as a tree with no rules.

Once a rule exists, `save_rdr_with_case` rewrites the whole file: it regenerates the class
section from `case_type.function` and replaces the rule-tree section with the live EQL
expression.

### `save_rdr_with_case` against `save_rdr`

`save_rdr` writes the rule tree alone and imports the case type from wherever it came
from. `save_rdr_with_case` recognises a `FunctionCase` subclass and inlines the class
definition at the top of the same file, passing `case_type_is_local=True` so the rule-tree
section does not import a class defined just above it. It generates that class against the
RDR layer's own `FunctionCase`, which is the base the layer checks against - a case class
generated against any other base is one the layer would not recognise on the way back in.

```{code-cell} ipython3
import os
import tempfile

from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.decorator import rdr
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface

model_file = os.path.join(tempfile.mkdtemp(), "decide.py")


@rdr(model_file)
def decide(speed: float) -> float:
    """Fall back to 2.5 for anything no rule recognises."""
    return 2.5


def answer_for_fast(context, requests):
    """Conclude 10.0, justified by the speed being above 2."""
    answers = {AnswerName.CONDITIONS: context.case_variable.speed > 2.0}
    if any(request.name is AnswerName.CONCLUSION for request in requests):
        answers[AnswerName.CONCLUSION] = 10.0
    return answers


decide.fit_case(
    decide.case_type(speed=3.0, _output=2.5),
    expert=Expert(interface=FunctionInterface(answer_function=answer_for_fast)),
)

print(open(model_file).read())
```

## Where the Model File Goes

`RDRFileStore.path` is a `cached_property` with two cases: an absolute filename is used as
given, and a relative one is resolved to `<module directory>/_rdr_models/<filename>`, with
`inspect.getfile(self.function)` locating the module. Caching it means the path is decided
once, at the moment the store is built.

```{code-cell} ipython3
import os
import tempfile

from krrood.entity_query_language.rdr.file_store import (
    MODELS_DIRECTORY_NAME,
    RDRFileStore,
)


def measure(distance: float) -> float:
    """Stand in for a decorated function."""
    return distance


relative_store = RDRFileStore(function=measure, filename="my_model.py")
print("relative name is placed beside the module:",
      relative_store.path.endswith(os.path.join(MODELS_DIRECTORY_NAME, "my_model.py")))

absolute_path = os.path.join(tempfile.gettempdir(), "absolute_model.py")
print("absolute name is used as given:",
      RDRFileStore(function=measure, filename=absolute_path).path == absolute_path)
```

Reading a model before anything wrote one raises `ModelFileMissing`, which names the
function and the path rather than leaving a bare `FileNotFoundError` to interpret.

## `FunctionCase`

The base carries exactly one member: a `ClassVar[Callable]` named `function`. It is
declared at class level and assigned *outside* the generated `@dataclass` body, so the
dataclass machinery never mistakes it for an instance field with a default.

A generated subclass adds one field per annotated parameter and an `_output` field typed
with the return annotation. There is no `__post_init__`, no `__init_subclass__` and no
metaclass - it stays thin so it composes with the rest of the RDR machinery unchanged.

```{code-cell} ipython3
import dataclasses

from krrood.entity_query_language.rdr.function_case import FunctionCase

print("instance fields on the base:", dataclasses.fields(FunctionCase))
print("carries the function ClassVar:", "function" in FunctionCase.__annotations__)
```

## Generating the Case Class

`FunctionCaseGenerator.generate` produces the class section, and three of its decisions
matter here:

1. **Annotations are resolved with `get_type_hints`**, falling back to the raw annotation
   when resolution fails, so a forward reference does not stop generation outright.
2. **The decorated function is imported by name**, which is what makes the file loadable on
   its own - and what the wrapper's name binding above exists to accommodate.
3. **Every non-builtin annotation is imported** under `if TYPE_CHECKING:`, so the file
   stays importable wherever those types are importable.

```{code-cell} ipython3
import enum

from krrood.code_generation.function_case import FunctionCaseGenerator
from krrood.entity_query_language.rdr.function_case import FunctionCase


class Speed(enum.Enum):
    """How fast to travel."""

    SLOW = "slow"
    FAST = "fast"


def navigate(distance: float, mode: Speed) -> Speed:
    """Choose a navigation speed."""
    return Speed.SLOW


print(FunctionCaseGenerator(base_class=FunctionCase).generate(navigate))
```

## What It Cannot Do

- **Only fully annotated functions.** Every parameter and the return value needs an
  annotation; anything less raises `FunctionMissingAnnotationsError` at decoration time.
- **No `*args` / `**kwargs`.** Variadic parameters carry no individual annotations, so
  they map to no named field.
- **The function must be importable by name.** A model file imports it back, so a function
  defined inside another function, or in an `exec`'d string, cannot round-trip.
- **A relative filename needs a locatable module.** `inspect.getfile` fails for built-ins
  and C extensions; name an absolute path in those cases.
- **The first decoration writes a file.** Where import time is costly - serverless, hot
  reload - that write happens once per model, at import.

## Extending It

### Another call-time mode

`__call__` branches on `fit_mode`. A third mode - a shadow mode that classifies and
audits, say - is a new field on `RDRWrapper`, a new keyword on `rdr()`, and a branch. No
other module changes.

### Another conclusion type in the saved file

`_emit_value` in `rdr/serialization.py` turns a conclusion into Python source, and handles
enums, `bool`, `None`, `int`, `float` and `str`. A new type needs a branch there, plus an
entry in `rdr_to_python`'s `referenced_types` if it has to be imported.

### Another base for generated case classes

`FunctionCaseGenerator` takes a `base_class`. Any `FunctionCase` subclass works, which is
how shared methods or validators reach every generated type in a project:

```python
source = FunctionCaseGenerator(base_class=AuditedFunctionCase).generate(some_function)
```

### Another place for model files

`RDRFileStore.path` is a `cached_property`, so a subclass overriding it decides placement -
a project-wide directory, a cache in front of a bucket, a database-backed store. Build the
wrapper with that store directly instead of going through `rdr()`.

```{code-cell} ipython3
import os
import tempfile

from functools import cached_property

from krrood.entity_query_language.rdr.decorator import RDRWrapper
from krrood.entity_query_language.rdr.file_store import RDRFileStore

PROJECT_MODELS_DIRECTORY = tempfile.mkdtemp()


class ProjectRDRFileStore(RDRFileStore):
    """Keeps every model in one project-wide directory, wherever its function lives."""

    @cached_property
    def path(self) -> str:
        """
        :return: The model's path inside the project-wide directory.
        """
        return os.path.join(PROJECT_MODELS_DIRECTORY, self.filename)


def triage(urgency: float) -> float:
    """Score how urgent something is."""
    return 0.0


wrapper = RDRWrapper(
    function=triage,
    store=ProjectRDRFileStore(function=triage, filename="triage_model.py"),
    expert=None,
    fit_mode=False,
)
print("kept in the project directory:",
      wrapper.store.path.startswith(PROJECT_MODELS_DIRECTORY))
```

| To change | Change this |
|---|---|
| Add an `@rdr` mode | `RDRWrapper.__call__`, plus a keyword on `rdr()` |
| Serialize a new conclusion type | `_emit_value` in `rdr/serialization.py` |
| Generate against another base | `base_class` on `FunctionCaseGenerator` |
| Place model files elsewhere | Override `path` on an `RDRFileStore` subclass |

## API Reference

- {py:class}`~krrood.entity_query_language.rdr.decorator.RDRWrapper`
- {py:func}`~krrood.entity_query_language.rdr.decorator.rdr`
- {py:func}`~krrood.entity_query_language.rdr.decorator.empty_rule_tree_source`
- {py:class}`~krrood.entity_query_language.rdr.file_store.RDRFileStore`
- {py:class}`~krrood.entity_query_language.rdr.function_case.FunctionCase`
- {py:class}`~krrood.code_generation.function_case.FunctionCaseGenerator`
- {py:class}`~krrood.entity_query_language.rdr.serialization.ModelSaver`
- {py:func}`~krrood.entity_query_language.rdr.serialization.save_rdr_with_case`
- {py:func}`~krrood.entity_query_language.rdr.serialization.load_rdr`
- {py:class}`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
