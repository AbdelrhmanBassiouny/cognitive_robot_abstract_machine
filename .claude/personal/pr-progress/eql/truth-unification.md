# PR plan: eql/truth-unification — unified OperationResult truth (Wave 1, Track T)

Not started. BLOCKED until PR #28 (eql-core-prep) merges to main — this
touches `core/base_expressions.py` and the logical operators and would
conflict with the stack. Design doc:
`krrood/doc/eql/developer/operation_result_truth_unification.md` (on
`abdel/rdr/oo-plan`; land it with this PR).

## Goal

Truth is always read from `bindings[self._id_]`: drop the
`OperationResult.is_false` dataclass field, make `is_false`/`is_true`
computed properties, retire `is_condition_false`.

## Steps (from the design doc)

1. TDD: characterization tests for operator truth (NOT/AND/OR, comparator,
   quantifiers) pinning current semantics.
2. Make every truth-bearing expression store its boolean in
   `bindings[self._id_]` (as `Comparator` already does).
3. Convert `is_false` to a property; migrate the ~20
   `OperationResult(...)` constructor call sites (drop the positional flag).
4. Remove `is_condition_false`; repoint its readers (conclusion_selector,
   condition evaluation).
5. Full krrood suite + the RDR integration tests (they lean on condition
   truth); update the design doc status to "implemented".

## SOLID anchor

This removes a duplicate-state hazard (two truth sources) — single source
of truth, harder-to-misuse interface. Needed before
`rdr/justifications` (TMS) records per-conclusion justifications.
