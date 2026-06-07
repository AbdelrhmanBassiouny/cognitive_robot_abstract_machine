# Full Unification of OperationResult Truth Semantics

## Status

**Planned** — not yet implemented. This document describes the next step beyond the targeted fix
introduced in the `rdr_refactor` branch (commit that added `OperationResult.is_condition_false`).

## Motivation

After the targeted fix, two truth-related attributes exist on `OperationResult`:

- `is_false: bool` — a raw dataclass field, set explicitly by logical operators (NOT, AND, OR, …).
- `is_condition_false: property` — the canonical rule used in condition evaluation: value-based
  for expressions with bindings, flag-based for operators without.

The duplication is harmless now but creates a maintenance hazard: a future author may use
`is_false` where `is_condition_false` is required and reintroduce the bug that was just fixed.
The full unification removes this ambiguity by making `is_false` *itself* the correct, unified
property.

## Goal

Remove the `is_false: bool = False` dataclass field from `OperationResult`. Make every
truth-bearing expression — including logical operators — store its boolean result in
`bindings[self._id_]` (exactly as `Comparator` already does). `is_false` and `is_true` become
pure computed properties, and `is_condition_false` can be retired.

The invariant becomes: **truth is always read from `bindings[self._id_]`**.

## Detailed Design

### 1. `OperationResult` changes

```python
@dataclass
class OperationResult:
    bindings: Bindings
    # is_false field removed
    operand: Optional[SymbolicExpression] = None
    previous_operation_result: Optional[OperationResult] = None
    ...

    @property
    def is_false(self) -> bool:
        if self.has_value:
            v = self.value
            return not (len(v) > 0 if is_iterable(v) else bool(v))
        return False  # no binding → no truth claim → treat as true

    @property
    def is_true(self) -> bool:
        return not self.is_false
```

`is_condition_false` can then be removed (it is now identical to `is_false`).

### 2. Constructor call sites (~20 locations)

Every `OperationResult(bindings, is_false_value, operand, ...)` call must drop the
`is_false_value` positional argument. The simplest migration: rename the field to
`_is_false_flag: bool = False` (kept only during the transition for call sites that still need
it) and add the `is_false` property first; then clean up all call sites in a follow-up.

### 3. Logical operators must store their truth result

Each `_evaluate__` in NOT, AND, OR, Refinement, Alternative, Next, and the logical quantifiers
must write `bindings[self._id_] = truth_bool` before yielding the `OperationResult`.

Example for `NOT`:
```python
def _evaluate__(self, sources):
    for v in self._evaluate_child_as_condition_(self._child_, sources):
        truth = not v.is_true
        bindings = copy(v.bindings)
        bindings[self._id_] = truth
        yield OperationResult(bindings, self, v)
```

### 4. `_evaluate_child_as_condition_` simplification

Once every expression stores a value, `_evaluate_child_as_condition_` can be simplified:

```python
def _evaluate_child_as_condition_(self, child, sources):
    for result in child._evaluate_(sources):
        yield result  # is_false is already correct via the property
```

Or it may be removed entirely if all callers can rely on `is_false` directly.

### 5. `SatisfiedConditionTracker` simplification

The `isinstance(expr, LogicalOperator)` branch in `on_conclusions_processed` can be removed:
both logical operators and attributes now store a value in bindings, so the uniform
`result.bindings[expr_id]` check handles all expressions:

```python
for expr_id in evaluated:
    expr = expression._get_expression_by_id_(expr_id)
    if not is_condition_participant(expr):
        continue
    if expr_id in result.bindings and result.bindings[expr_id]:
        satisfied.add(expr_id)
```

## Scope and Risk

| Area | Files | Notes |
|---|---|---|
| `OperationResult` | `base_expressions.py` | Field removal + property; constructor sig change |
| Constructor call sites | ~20 places across `base_expressions.py`, `conclusion_selector.py`, `operations.py`, `comparator.py`, `core_logical_operators.py`, `logical_quantifiers.py`, etc. | Mechanical; break one at a time |
| Logical operator `_evaluate__` | NOT, AND, OR, Refinement, Alternative, Next, Every, Some | Each needs to write `bindings[self._id_] = bool` |
| `SatisfiedConditionTracker` | `evaluation.py` | Simplify `on_conclusions_processed` |
| All existing tests | `test/krrood_test/` | Must remain green throughout |

The migration can be done incrementally:
1. Rename `is_false` field → `_is_false_flag`; add `is_false` property that falls back to the flag.
2. Port each operator one at a time, removing its reliance on the flag.
3. Once all operators write a value, remove `_is_false_flag` entirely.
4. Remove `is_condition_false` (now identical to `is_false`).
