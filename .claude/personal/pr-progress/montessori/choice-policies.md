# PR plan: montessori/choice-policies — demo policy wiring (Montessori track, M1 — DEFERRED)

**DEFERRED (2026-07-17): blocked on Tom's `montessori_ijcai` branch being ready.**
The generic half was extracted to `rdr/explainable-choice.md` (C1) and proceeds
now in krrood. This note keeps only the demo-specific remainder.

## Remaining scope (when Tom's branch is ready)

Base: `tomsch420/montessori_ijcai` (fetch read-only via the git proxy;
re-check the tip — Tom pushes actively) + the landed C1/W1/W2 work. Push only
to the AbdelrhmanBassiouny fork; coordinate the PR target with Tom.

1. `pick_policy` RDR (which loose shape next; case = shapes on table + board
   state) built ON the generic `ExplainableChoice`/`RDRChoice` from C1.
2. `hole_policy` RDR (which hole for a shape; base rule = shape_category
   equality — what `ShapeSortingBoard.hole_for` hard-codes — refinable by
   exception: occluded, unreachable, drawer open).
3. Policy-injection seam on `InsertMontessoriShapeAction` (default preserves
   current `hole_for` behaviour); demo loop asks `pick_policy` instead of
   fixed iteration.
4. Shape categories from `hole_geometry.py` detection (inferred) or the
   `shape_category` annotations (given).

## Conflict watch

Tom's branch edits krrood verbalization/factories files (english.py,
fragments/base.py, parts_of_speech.py, factories.py, predicate.py) —
reconcile against the split stack + W2 (#82) + #83 at pickup time.

## TDD anchors

Hole-policy refinement-by-exception; pick-order test; both branches' existing
montessori tests stay green. M2 (`montessori/why-demo.md`) stacks after this.
