# PR plan: rdr/explainable-choice — generic why-explainable choice (Why track, C1)

Not started. Base: `claude/rdr-why-answer-6fnw2o` (W1, PR #81). Extracted out of
the old M1 plan (2026-07-17): the choice machinery is general, so it lands in
krrood now, independent of the Montessori demo (deferred until Tom's branch is
ready — see `montessori/choice-policies.md`).

## Goal

Choosing one candidate from a set via an RDR-backed policy, with the choice
why-explainable for free: `choose() -> Choice` where `Choice` carries the
selected candidate and its `WhyAnswer`.

## Design (krrood only — no coraplex, no experiments)

- `rdr/choice.py`:
  - `ExplainableChoice` protocol/ABC: candidates as an EQL variable/domain +
    a policy; `choose()` returns a `Choice` value object (selected candidate,
    `WhyAnswer`, optionally the rejected candidates). DIP: consumers depend on
    the protocol, not on RDR concretely.
  - `RDRChoice(ExplainableChoice)`: implemented over `RDRBackend`'s existing
    `InferenceStrategy` seam (`ExplainingInference` from W1) — the choice IS an
    underspecified query whose `...` target the policy RDR fills; the retained
    `ClassificationTrace` yields the `WhyAnswer`. No new capture machinery.
  - Custom exceptions: `NoCandidatesToChooseFrom`, `NoChoiceConcluded`.
- Ranking/ordering choices (pick the FIRST of several) is the same mechanism
  with a conclusion that orders — keep v1 to single-choice; document the
  ordering extension.

## Test data (krrood self-containment rules)

Mimic the shape-sorting scenario inside `test/krrood_test/dataset` with classes
named after the pattern, not the demo: e.g. `CategorizedItem` /
`CategorizedSlot` (each carrying a category attribute), plus a
choice-by-category policy fitted in the test. No imports from
experiments/semantic_digital_twin/coraplex.

## TDD anchors

1. Policy chooses the matching-category slot; `Choice.why` names the fired
   rule and its condition (assert against `ClassificationTrace`).
2. Refinement-by-exception: add an exception rule (e.g. slot blocked), the
   choice changes, the why-answer names the refinement.
3. Empty candidate set raises `NoCandidatesToChooseFrom`.
4. With W2 merged upstack: `choice.why.verbalize()` golden text.

## Deferred to the demo track (NOT here)

Action-layer seam (`InsertMontessoriShapeAction` policy injection), pick/hole
policies over world entities, coraplex glue — all in
`montessori/choice-policies.md`, blocked on Tom's branch readiness.
