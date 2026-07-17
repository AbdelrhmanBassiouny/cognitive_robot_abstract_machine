# PR plan: rdr/decision-queries — backend explanation semantics + the decision-query pattern (Why track, C1 — REFRAMED 2026-07-17)

Not started. Base: `eql/causal-verbalization` (W2, PR #82) so verbalized
explanations are available; coordinate with the W3 session
(`rdr/why-query-surface`, just cut) — why(...) composes over exactly what this
PR produces.

## Why the reframe (design discussion with the owner, 2026-07-17)

The old plan (`ExplainableChoice` protocol + `RDRChoice` class) duplicated
seams EQL already has and was dropped as YAGNI:

- A "choice" IS an underspecified query over a partially-specified decision
  object: `an(InsertionAction)(slot=...).evaluate(backend=rdr_backend)`.
  The action/decision dataclass is the natural case; filling its `...` IS
  choosing. No new protocol needed — `backend=` is already the DIP seam
  (RDR vs probabilistic vs future backends).
- No extra computation is needed for explanations: every classification
  already produces the full trace (`ConclusionObserver` → `FiredConclusion`
  with fired `Add`, anchor, bindings, `satisfied_condition_ids`). The gap is
  ONLY retention + addressing.
- A protocol for hypothetical non-EQL policies gets extracted later from
  working code if one ever exists.

## The storage decision (agreed with the owner)

**Canonical home: the model (Option B), never the concluded value, never the
case.**

- RDR conclusions bind EXISTING, shared values — in the zoo, `Species.mammal`
  is ONE enum member concluded for ~41 animals; attaching an explanation to
  it is one global slot overwritten per classification, and primitives can't
  hold attributes at all. (`inference()` may attach to instances only because
  it CREATES them.)
- Precedents: `CornerCaseStore` already keeps creation provenance model-side;
  the general-fixpoint plan chose an engine-side blackboard over case
  mutation; Wave-3 JTMS justifications need a model/engine-side store anyway.
  Firing provenance joins them.
- Current W1 state (PR #81): `ExplainingInference` retains traces in
  positional LISTS on the strategy object; `FastInference` is the default;
  no `explain(result)` routing. This PR upgrades that.

## Scope

1. **Model-side explanation store** on `EQLSingleClassRDR`: weak-keyed
   (case → last `ClassificationTrace`/`RDRConclusionExplanation`),
   last-classification-wins; `rdr.why(case)` reads it instead of (or before)
   re-tracing. Bounded/weak so long-running backends don't leak.
2. **Explanation-bearing yielded results**: `RDRBackend.infer` attaches the
   explanation to the yielded handle (`UnificationDict` / filled-result
   object — fresh per yield, so no aliasing), referencing the model store.
   `explain(result)` then routes RDR results through the same surface as
   `inference()` instances.
3. **Default-on for the RDR backend** (matching the `InferenceRecorder`
   precedent for `inference()`): the explaining strategy becomes the
   default; `FastInference` stays available as the opt-out. Measure the
   overhead on the zoo suite before committing; if unacceptable, keep
   fast-default and make `evaluate`'s explain opt-in explicit — decide from
   data, record the decision here.
4. **Typed failure semantics**: `first()`-style access on a decision query
   raises a meaningful exception (`NoChoiceConcluded`-style) instead of
   None-flow through `next(iterator, None)`.
5. **The decision-query pattern, documented**: extend
   `doc/eql/user/underspecified.md` (or a sibling page) with the canonical
   idiom — a decision is a partially-specified action object queried with
   `an(...)(attribute=...)`; choosing = evaluating with an RDR backend;
   asking why = `explain(result)` / W3's `why(...)`. The montessori
   pick/hole policies later instantiate this pattern with zero new
   machinery.

## Explicitly dropped

`ExplainableChoice` protocol, `RDRChoice`, `rdr/choice.py`,
`NoCandidatesToChooseFrom` (an empty domain is an ordinary empty query
result unless data shows otherwise).

## TDD anchors (zoo + a decision-object mimic in the krrood test datasets)

1. Aliasing regression: two cases concluding the SAME enum value get
   distinct explanations; the shared value carries nothing.
2. `explain(yielded_result)` returns the explanation naming the fired rule
   (assert against the model store / `ClassificationTrace`).
3. Weak-key lifetime: deleting the case drops its stored trace.
4. Re-classification overwrites: the store answers for the LATEST run.
5. Decision-object mimic (pattern-named, e.g. `SlotAssignment` with
   `chosen=...`): the three-liner
   `explain(next(an(SlotAssignment)(chosen=...).from_([assignment]).evaluate(backend=...)))`
   works end-to-end and verbalizes via W2.
6. First-access failure raises the typed exception.
