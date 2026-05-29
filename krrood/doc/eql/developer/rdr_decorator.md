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

# `@rdr` Decorator Internals

This guide explains the design of the `@rdr` decorator in
`krrood.entity_query_language.rdr`.  User documentation lives in
{doc}`../user/rdr_decorator`.

## Design Goals

1. **Zero boilerplate for the caller** — the user writes a normal annotated function
   and adds one decorator line.  No dataclass, no variable declaration, no file setup.
2. **EQL-native throughout** — the generated case type is a real `FunctionCase`
   subclass; the rule tree is the same EQL expression DAG used everywhere in the RDR
   subsystem.  No parallel "string rules" or bespoke serialization format is introduced.
3. **Transparent call-through** — callers see no behaviour change until a rule fires.
   In inference mode the original output is the default; in fit mode it is always the
   return value.  The wrapper is a drop-in replacement for the original function.
4. **Auto-persistence** — every rule insertion rewrites the model file automatically.
   The file is a self-contained importable Python module so it can be loaded across
   processes without any registry or pickle.
5. **Strict separation of concerns** — file lifecycle (`RDRFileStore`), case
   construction (`FunctionCase` + `function_to_dataclass_source`), and call interception
   (`RDRWrapper`) are three independent classes with no circular dependencies.

---

## SOLID Split

| Class | Single Responsibility | Module |
|---|---|---|
| `rdr()` | Factory — parse arguments, create store and wrapper | `rdr/decorator.py` |
| `RDRWrapper` | Interception — intercept calls, build cases, classify or fit | `rdr/decorator.py` |
| `RDRFileStore` | File lifecycle — resolve path, write, load case type | `rdr/file_store.py` |
| `FunctionCase` | Base type — shared `ClassVar[Callable]` contract | `rdr/function_case.py` |
| `function_to_dataclass_source` | Code generation — emit the `@dataclass` source | `class_diagrams/code_generation_utilities.py` |
| `EQLSingleClassRDR` | Classification + fitting — unchanged from the base RDR | `rdr/single_class.py` |

---

## Architecture

```{mermaid}
sequenceDiagram
    participant User as @rdr decorator
    participant Store as RDRFileStore
    participant Gen as function_to_dataclass_source
    participant Wrap as RDRWrapper.__post_init__
    participant RDR as EQLSingleClassRDR

    User->>Store: RDRFileStore(func, filename)
    User->>Wrap: RDRWrapper(func, store, expert, fit_mode)
    Wrap->>Store: store.exists()?
    alt file absent
        Store-->>Wrap: False
        Wrap->>Gen: function_to_dataclass_source(func)
        Gen-->>Wrap: class source string
        Wrap->>Wrap: prepend _empty_rdr_preamble
        Wrap->>Store: write combined source to store.path
        Wrap->>Store: store.load_case_type()
        Store-->>Wrap: FunctionCase subclass
        Wrap->>RDR: EQLSingleClassRDR(case_type, "_output")
    else file present
        Store-->>Wrap: True
        Wrap->>Store: store.load_case_type()
        Store-->>Wrap: FunctionCase subclass
        Wrap->>Wrap: load_rdr(store.path)
        Wrap-->>Wrap: EQLSingleClassRDR (with saved tree)
    end
    Wrap->>Wrap: case_type.function = func
    Wrap->>RDR: rdr.save_path = store.path
```

### `rdr()` — the factory

`rdr(filename, *, expert=None, fit=False)` is a two-level decorator factory:

1. Validates that `filename` is not `None` (raises `TypeError` immediately if omitted).
2. Returns `_decorate(func)` which creates a `RDRFileStore` and a `RDRWrapper`.

All argument validation happens here.  `RDRWrapper.__post_init__` receives fully
validated inputs and focuses only on loading or generating.

### `RDRWrapper.__post_init__` — load-or-generate

`_load_or_generate` is the branching point:

- **File absent**: `function_to_dataclass_source` generates the `@dataclass` class
  source; `_empty_rdr_preamble` writes the boilerplate rule-tree section (no rules yet,
  just the `variable(...)` declaration and the stable handle constants).  Both are joined
  and written to disk.  The case type is immediately loaded back via `store.load_case_type()`.
  A fresh `EQLSingleClassRDR(case_type, "_output")` is constructed.
- **File present**: `store.load_case_type()` recovers the `FunctionCase` subclass; the
  full rule tree is restored by `load_rdr(store.path)`.

After either branch, two invariants are enforced:
1. `case_type.function = self.func` — the live callable is always wired in, even when
   the file was loaded from a previous process (where `try/except NameError` in the
   generated code left `function` unset).
2. `rdr.save_path = store.path` — every subsequent rule insertion auto-saves.

### `RDRWrapper.__call__` — inference vs. fit

```python
def __call__(self, *args, **kwargs):
    output = self.func(*args, **kwargs)
    case = self._build_case(args, kwargs, output)
    if self.fit_mode:
        if self.expert is not None:
            self.rdr.fit_case(case, target=UNSET, expert=self.expert)
        return output
    conclusion = self.rdr.classify(case)
    return output if (conclusion is UNSET or conclusion is None) else conclusion
```

Two important subtleties:

- The original function is **always** called first.  The case is built from actual
  call arguments and actual output, so `_output` is never speculative.
- In inference mode `UNSET` and `None` are both treated as "no rule fired" — the
  original output stands.  This means a rule that explicitly concludes `None` would be
  ignored; if a downstream use case requires `None` as a valid conclusion the `_output`
  field type must be `Optional[...]` and the rule tree must be grown accordingly.

### `_build_case` — argument binding

```python
def _build_case(self, args, kwargs, output):
    sig = inspect.signature(self.func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    params = {k: v for k, v in bound.arguments.items()
              if k not in ("self", "cls")}
    return self.case_type(**params, _output=output)
```

`inspect.signature` + `bind` + `apply_defaults` is the standard library's own argument
normalisation.  This handles positional, keyword, and default arguments uniformly.
`self` / `cls` are excluded so the decorator works on both free functions and methods.

---

## Generated File Anatomy

A freshly decorated function with no rules produces:

```python
# ── class-header section (function_to_dataclass_source) ──────────────────────
from __future__ import annotations
from dataclasses import dataclass
from typing_extensions import ClassVar, Callable
from krrood.entity_query_language.rdr.function_case import FunctionCase
try:
    from my.module import select_strategy
except ImportError:
    pass

@dataclass
class SelectStrategy(FunctionCase):
    """FunctionCase for the `select_strategy` function."""
    weight_kg: float
    material: str
    _output: GraspStrategy

try:
    SelectStrategy.function = select_strategy
except NameError:
    pass


# ── rule-tree section (_empty_rdr_preamble) ───────────────────────────────────
"""Auto-generated EQL-RDR rule tree. Do not edit by hand."""
from krrood.entity_query_language.factories import (
    variable, entity, add, refinement, alternative, next_rule, and_, or_, not_,)

selectStrategy = variable(SelectStrategy, domain=[])

# Stable handles for loading.
RDR_CASE_TYPE = SelectStrategy
RDR_CONCLUSION_ATTRIBUTE = '_output'
RDR_CASE_VARIABLE = selectStrategy
RDR_QUERY = None
```

After fitting one rule, `save_rdr_with_case` regenerates the class-header section
and replaces the rule-tree section with the live EQL expression.

The four `RDR_*` constants at the bottom are the stable load handles read by
`load_rdr` and `RDRFileStore.load_case_type`.

---

## The `save_path` Auto-Save Mechanism

`EQLSingleClassRDR.save_path` is an optional `str` field (default `None`).  When set,
`_insert_rule` (called after every successful fit) invokes `save_rdr_with_case(self, self.save_path)`.

`RDRWrapper.__post_init__` sets `rdr.save_path = store.path` unconditionally.  This
means the decorator fully delegates persistence bookkeeping to the RDR — the wrapper
itself never calls any save function.

---

## `save_rdr_with_case` vs. `save_rdr`

`save_rdr` serializes the rule tree only and imports the case type from its original
module.  `save_rdr_with_case` detects a `FunctionCase` subclass and **inlines the class
definition** at the top of the same file (passing `case_type_is_local=True` to suppress
the import).  This keeps the model file self-contained: it can be loaded in any
environment that has `krrood` installed, even if the original function's module is
not on `sys.path`.

```{code-cell} ipython3
# Demonstrate the self-contained nature of the generated file.
import tempfile, os
from krrood.entity_query_language.rdr.decorator import rdr
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.utils import UNSET

_tmp2 = tempfile.mkdtemp()
_path = os.path.join(_tmp2, "demo.py")

@rdr(_path)
def decide(speed: float) -> float:
    return 2.5

# Fit one rule.
def _ans(ctx, reqs):
    answers = {}
    if any(r.name == "conclusion" for r in reqs):
        answers["conclusion"] = 10.0
    if any(r.name == "conditions" for r in reqs):
        answers["conditions"] = ctx.case_variable.speed > 2.0
    return answers

decide.fit_case(
    decide.case_type(speed=3.0, _output=2.5),
    target=UNSET,
    expert=Expert(interface=FunctionInterface(answer_fn=_ans)),
)

with open(_path) as f:
    print(f.read())
```

---

## `RDRFileStore` — Path Resolution

`RDRFileStore._resolve_path` implements two modes:

- **Absolute path** (`Path(filename).is_absolute()` is `True`): used as-is.  This is the
  recommended mode for tests and for explicitly placing model files.
- **Relative filename**: resolved to `<module_dir>/_rdr_models/<filename>`.
  `inspect.getfile(func)` locates the module; the `_rdr_models/` subdirectory is
  created automatically on first write.

The `cached_property` on `path` ensures the path is computed once and never changes
for the lifetime of the store, even if the underlying module file moves (which should
not happen at runtime).

```{code-cell} ipython3
import inspect, tempfile, os
from krrood.entity_query_language.rdr.file_store import RDRFileStore

def _dummy(x: float) -> float:
    return x

store = RDRFileStore(func=_dummy, filename="my_model.py")
# Relative filename → placed beside _dummy's module file under _rdr_models/.
expected_suffix = os.path.join("_rdr_models", "my_model.py")
print("ends with expected suffix:", store.path.endswith(expected_suffix))

# Absolute filename → used as-is.
abs_path = os.path.join(tempfile.gettempdir(), "absolute.py")
store_abs = RDRFileStore(func=_dummy, filename=abs_path)
print("absolute path unchanged  :", store_abs.path == abs_path)
```

---

## `FunctionCase` — the Minimal Base

`FunctionCase` carries exactly one `ClassVar[Callable]` called `function`.  The
`ClassVar` is declared at class level but assigned *outside* the generated `@dataclass`
body so `@dataclass`'s annotation scanner never confuses it for an instance field with
a default value.

The generated subclass holds:

- One `dataclass` field per annotated parameter.
- One `_output` field typed with the return annotation.

No `__post_init__`, no `__init_subclass__`, no metaclass.  It is deliberately thin so
it integrates transparently with the rest of the EQL RDR machinery.

```{code-cell} ipython3
import dataclasses
from krrood.entity_query_language.rdr.function_case import FunctionCase

# FunctionCase itself has no instance fields — only the ClassVar.
print("FunctionCase fields:", dataclasses.fields(FunctionCase))
print("function ClassVar   :", "function" in FunctionCase.__annotations__)
```

---

## `function_to_dataclass_source` — Code Generation

`function_to_dataclass_source(func)` in `krrood.class_diagrams.code_generation_utilities`
produces the class-header section of the model file.  Key design points:

1. **`typing.get_type_hints` with graceful fallback** — string annotations (from
   `from __future__ import annotations`) are resolved via `get_type_hints`.  If
   resolution fails (e.g. locally-defined types in tests) the raw string annotation is
   used.  This avoids hard failures for forward references.
2. **`try/except ImportError` around the function import** — the generated file can be
   `exec`'d in isolated namespaces (tests, serialization round-trips) where the original
   module is not importable.  The `@rdr` decorator always sets `case_type.function`
   explicitly after loading, so the ClassVar assignment in the generated file is a
   convenience that does not need to succeed.
3. **`try/except NameError` around `Cls.function = func`** — mirrors the ImportError
   guard; if the import above failed `func` is not in scope and the assignment would
   raise `NameError`.

```{code-cell} ipython3
from krrood.class_diagrams.code_generation_utilities import function_to_dataclass_source
import enum

class Speed(enum.Enum):
    slow = "slow"
    fast = "fast"

def navigate(distance: float, mode: Speed) -> Speed:
    """Choose navigation speed."""
    return Speed.slow

print(function_to_dataclass_source(navigate))
```

---

## Benefits and Trade-offs

### Benefits

- **Single source of truth** — the function signature drives the case type, the RDR
  variable, and the conclusion attribute.  No duplication; no synchronisation burden.
- **Drop-in compatible** — existing callers need zero changes.  The decorator is
  transparent until a rule fires.
- **Self-contained model files** — the combined class + rule tree can be loaded in any
  krrood-installed environment.  No pickle, no registry, no JSON schema.
- **Composable with existing EQL RDR** — `wrapper.rdr` is a plain `EQLSingleClassRDR`;
  all `fit_case`, `fit`, `classify`, `render_tree`, `save_path` operations are directly
  accessible.

### Trade-offs / Known Limitations

- **Fully-annotated functions only** — every parameter and the return type must carry a
  type annotation.  `FunctionMissingAnnotationsError` is raised at decoration time.
- **`*args` / `**kwargs` functions not supported** — variadic parameters have no
  individual type annotations and cannot be mapped to named dataclass fields.
- **`None` conclusion treated as "no rule"** — in inference mode `classify` returning
  `None` falls through to the original output.  A function that legitimately returns
  `None` will never be overridden by a rule that concludes `None`.
- **First call incurs file I/O** — `_load_or_generate` writes the model file on the
  first decoration if it is absent.  For hot-reload or serverless scenarios this is a
  one-time cost at import time.
- **Module-relative path requires the function's source file to be discoverable** —
  `inspect.getfile(func)` fails for built-ins, C extensions, and functions defined in
  `exec`'d strings.  Use an absolute path in those cases.
- **Non-builtin return types and annotations trigger a code-generation issue** —
  `function_to_dataclass_source` uses `inspect.formatannotation` which emits
  fully-qualified type names (e.g. ``mypackage.MyEnum``).  When the saved file is
  loaded and any attribute of the case variable is accessed (e.g.
  ``case_variable.weight_kg`` in an ``answer_fn``), the MappedVariable system tries
  to resolve all annotations on the case type.  It can resolve builtins (``float``,
  ``str``, ``int``, …) because their names are unqualified, but non-builtin types
  require the qualifying module to be importable in the loaded module's namespace.
  This is tracked as an upstream limitation of ``function_to_dataclass_source``;
  until the fix lands, prefer builtin return types or use
  :class:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
  directly (as demonstrated in the conclusion-asking guide) when working with custom
  enum types.

---

## Extension Points

### Add a new call-time behaviour mode

`RDRWrapper.__call__` currently branches on `self.fit_mode`.  To add a third mode
(e.g. a "shadow" mode that classifies but writes audit logs):

1. Add a new attribute to `RDRWrapper` in `rdr/decorator.py`.
2. Add the corresponding keyword argument to `rdr()`.
3. Add the branch in `__call__`.

No other file needs to change.

### Support a new conclusion type in the generated file

`_emit_value` in `rdr/serialization.py` serializes conclusion values to Python source.
Currently it handles `enum.Enum`, `bool`, `None`, `int`, `float`, and `str`.  To add a
new type (e.g. a dataclass):

1. Add a branch in `_emit_value` that returns a valid Python expression for the type.
2. Ensure the type is importable from the generated file (it may need to be added to
   `referenced_types` in `rdr_to_python`).

### Use a different base class for generated types

`function_to_dataclass_source` accepts a `base_class_fqn` keyword argument.  Pass a
fully-qualified name of any `@dataclass`-compatible base class to generate case types
that inherit from it instead of `FunctionCase`.  This allows adding shared methods or
validators to all generated types in a project.

```python
source = function_to_dataclass_source(
    my_func,
    base_class_fqn="mypackage.rdr_base.AuditedFunctionCase",
)
```

### Customise path resolution

Subclass `RDRFileStore` and override `_resolve_path` to place model files in a
project-wide registry, a cloud bucket (local cache + upload), or a database-backed
store.  Pass an instance of the subclass directly to `RDRWrapper` instead of using
the `rdr()` factory.

```{code-cell} ipython3
from krrood.entity_query_language.rdr.file_store import RDRFileStore
from krrood.entity_query_language.rdr.decorator import RDRWrapper
import tempfile, os
import enum

class Priority(enum.Enum):
    low = "low"
    high = "high"

class ProjectRDRFileStore(RDRFileStore):
    """Places all model files under a single project-wide directory."""

    _PROJECT_ROOT = tempfile.mkdtemp()

    @staticmethod
    def _resolve_path(func, filename):
        # Ignore the function location; use a project-wide registry dir.
        return os.path.join(ProjectRDRFileStore._PROJECT_ROOT, filename)

def triage(urgency: float) -> Priority:
    """Default: low priority."""
    return Priority.low

store = ProjectRDRFileStore(func=triage, filename="triage_model.py")
wrapper = RDRWrapper(func=triage, store=store, expert=None, fit_mode=False)

print("model path:", wrapper.store.path)
print("starts with project root:",
      wrapper.store.path.startswith(ProjectRDRFileStore._PROJECT_ROOT))
```

---

## Extension Points Summary

| What you want | Where to change |
|---|---|
| Add a new `@rdr` mode | `RDRWrapper.__call__` + new kwarg in `rdr()` — `rdr/decorator.py` |
| Serialise a new conclusion type | `_emit_value` in `rdr/serialization.py` |
| Change the generated base class | `base_class_fqn` kwarg in `function_to_dataclass_source` — `class_diagrams/code_generation_utilities.py` |
| Customise file placement | Subclass `RDRFileStore._resolve_path` — `rdr/file_store.py` |
| Add shared methods to all generated types | Subclass `FunctionCase`; pass as `base_class_fqn` |

---

## API Reference

- {py:class}`~krrood.entity_query_language.rdr.decorator.RDRWrapper`
- {py:func}`~krrood.entity_query_language.rdr.decorator.rdr`
- {py:class}`~krrood.entity_query_language.rdr.file_store.RDRFileStore`
- {py:class}`~krrood.entity_query_language.rdr.function_case.FunctionCase`
- {py:func}`~krrood.class_diagrams.code_generation_utilities.function_to_dataclass_source`
- {py:func}`~krrood.entity_query_language.rdr.serialization.save_rdr_with_case`
- {py:func}`~krrood.entity_query_language.rdr.serialization.load_rdr`
- {py:class}`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`
