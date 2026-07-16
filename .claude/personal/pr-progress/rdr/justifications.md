# PR plan: rdr/justifications — JTMS layer (Wave 3)

Not started. BLOCKED on `eql/truth-unification` (single truth source) and
`rdr/general-fixpoint` (dependency graph + blackboard). Design:
`rdr_architecture_plan.md` §2.3 last bullet + §6 (Doyle JTMS).

## Goal

Justification-based truth maintenance: record, per conclusion, which
facts/upstream conclusions it depended on → (a) incremental
retract/recompute when the world changes, (b) free explanations ("this is
a Drawer because …").

## Design (SOLID)

- `Justification` — frozen dataclass: conclusion id, supporting binding
  ids / upstream conclusion ids, producing rule node id.
- `JustificationRecorder(EvaluationObserver)` — mirrors
  `InferenceRecorder`'s shape (the reference observer in
  `explanation/explanation.py`); installed alongside the RDR observer;
  zero engine modification (OCP via the existing observer seam).
- `RetractionPropagator` — walks justifications on a retracted fact,
  invalidates dependents, re-fires only affected trees via the semi-naive
  strategy. Lives beside the fixpoint engine, depends only on the
  `Justification` store + `EvaluationStrategy` abstractions.
- Explanation rendering reuses the verbalization pipeline where possible
  (justification → NL is a natural extension of inference_explanation).

## TDD anchors

1. Classify; assert each conclusion carries a justification naming its
   supporting conditions.
2. Retract a supporting fact; only dependent conclusions recomputed
   (counter test — untouched trees not re-fired).
3. Explanation for the drawer case reproduces the
   `inference_explanation` behaviour through justifications.
