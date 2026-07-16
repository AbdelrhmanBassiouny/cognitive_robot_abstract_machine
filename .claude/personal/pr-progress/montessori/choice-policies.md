# PR plan: montessori/choice-policies — explainable choices (Montessori track, M1)

Not started. Base: `tomsch420/cognitive_robot_abstract_machine` branch
`montessori_ijcai` (tip `b4b45382d`, the REAL demo: `hole_geometry.py` mesh-based
hole detection, `insert_shape_action.py`, Multiverse iCub scene under
`segmind/resources/multiverse_episodes/icub_montessori_no_hands/`, HSRB demo
main) with `rdr/why-answer` (W1) merged in. SHARED BRANCH LINEAGE with Tom
Schierenbeck — coordinate before any force-push; agree the PR target with him.

## Goal

Replace both procedural choice points with EQL/RDR-backed, why-explainable
policies. Nothing montessori-specific below the experiments layer.

## Design

- Generic layer (`krrood/.../rdr/choice.py`): `ExplainableChoice` protocol —
  candidates as an EQL variable + an RDR-backed policy →
  `choose() -> (choice, WhyAnswer)`. Implement once over
  `RDRBackend`/underspecified: the choice IS an underspecified query, so every
  such choice is why-explainable for free (DIP).
- Demo layer (`experiments/montessori/`):
  - `pick_policy` RDR: which loose shape next (case = shapes on table + board
    state).
  - `hole_policy` RDR: which hole for a shape; base rule = `hole.shape_category
    == shape.shape_category` (what `ShapeSortingBoard.hole_for`'s loop hard-codes
    today), refinable by exception (occluded, unreachable, drawer open).
  - `InsertMontessoriShapeAction`: injected policy seam; default preserves
    current `hole_for` behaviour (OCP, backward compatible).
  - Shape categories: existing `hole_geometry.py` detection (inferred) or the
    `shape_category` annotations (given).

## Conflict watch

Tom's branch changes krrood verbalization files that W2 also touches
(`vocabulary/english.py`, `fragments/base.py`, `parts_of_speech.py`) and
`factories.py`/`predicate.py` — reconcile with the split stack + W1/W2 early.

## TDD anchors

Hole-policy refinement-by-exception scenario; pick-order test; both branches'
existing montessori tests stay green (`test_montessori_semantics`,
`test_montessori_world`).
