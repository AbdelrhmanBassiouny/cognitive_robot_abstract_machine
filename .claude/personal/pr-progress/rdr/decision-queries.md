# PR plan: rdr/decision-queries — backend explanation semantics + the decision-query pattern (Why track, C1 — REFRAMED 2026-07-17)

Base: `eql/causal-verbalization` (W2, PR #82). **Draft PR #85 open**
(`rdr/decision-queries -> eql/causal-verbalization`).
Session: https://claude.ai/code/session_013NepUGgubeWHnLT5TUPLdu

## STATUS — implemented, pushed, CI watch (2026-07-17)

All five scope items + six TDD anchors done. Full `test_eql_rdr` = 291 passed
(273 baseline + 18 new). docformatter via `scripts/format_docstrings.py`; stray
downloads reverted, zoo pickles are gitignored.

Delivered:
- `rdr/explanation_store.py` `CaseExplanationStore`: model-side, weak *and*
  identity-keyed. Holds BOTH case and explanation weakly (the explanation's
  bindings reference the case, so a strong value would pin the case and defeat
  the weak key) — it is a cache; `answer_why` reads it then falls back to
  re-tracing. `record`/`get`/`require`/`__contains__`; `NoRecordedExplanation`.
- `rdr/decision.py`: `ExplainedUnificationDict(UnificationDict)` exposing
  `conclusion_explanation`; `explain(result)` routes RDR handles and
  `inference()` instances through one surface; `UnexplainedResult` on an
  unexplained handle (typed first-access failure).
- `single_class.py`: `explanation_store` field (repr/compare=False, ignored by
  serialization); `classify_and_explain` + shared `explanation_from_trace`
  helper; `answer_why` reads the store before re-tracing.
- `backend.py`: strategies return `ConcludedCase(value, explanation)`;
  `ExplainingInference` UPGRADED (not duplicated) to record into the store;
  `infer` attaches the explanation to the yielded handle (fresh per yield);
  new `RDRBackend.evaluate()` = decision-query entry, explains by default.
- Docs: decision-query pattern + canonical three-liner in
  `doc/eql/user/underspecified.md`.

## DEFAULT-ON decision — MEASURED (zoo, this env)

- small policy tree (7 cases): explain overhead ~13.5% (+1.7 ms/case).
- full zoo (101 cases, deep tree): explain -> RecursionError at default limit
  1000 (deep `OperationResult.all_bindings` chain); with limit 100k, +78.7%.
=> `infer()` KEEPS `FastInference` default (bulk, zoo-safe — changing it would
   also break the existing zoo integration tests with the RecursionError).
   `evaluate()` (the decision surface) defaults to `ExplainingInference` (small
   trees ~13%, and it is what the `explain(result)` three-liner needs).
   Follow-up worth flagging: the deep-chain RecursionError in `all_bindings` is
   latent for explanation over large trees (Track T / iterative-bindings fix).

## Coordination with W3 (#84) — CONFIRMED

W3 reshaped to `why(source)` composing over an `ExplanationCarrier` protocol
(a handle exposing `conclusion_explanation`). My `ExplainedUnificationDict`
exposes exactly that attribute (locked by
`test_handle_exposes_conclusion_explanation_attribute`) and satisfies a
`runtime_checkable` carrier — real handles drop into W3 unchanged, no public
signature change. `rdr.why(case)` stays the case-directed Python API.

## NEXT

- Watch CI on #85; keep draft; keep description current.
- If a reviewer wants the `all_bindings` recursion fixed here rather than in
  Track T, that is a scoped follow-up — flag, don't bundle.

---
(historical design rationale below)

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

## Coordination contract with W3 (decided 2026-07-17, second round)

The W3 session (`rdr/why-query-surface`) proceeds UNBLOCKED via a decoupled
seam: it defines a small explanation-source abstraction (an
`explain(result)`-style accessor + case store-read) and tests against a mimic
implementation. Decisions:

- `why(...)`'s primary input is the YIELDED RESULT HANDLE. The case-directed
  ask stays exclusively on W1's Python API (`rdr.why(case)`) — do not add a
  `(rdr, case)` form to the factory (one way of doing things).
- **C1 implements W3's abstraction** — the model-side store +
  explanation-bearing handles from this PR become its concrete
  implementation. Read W3's seam definition (their branch/note) BEFORE
  designing the store's public accessor, and match it exactly; do not invent
  a second lookup path. If the seam needs adjusting, negotiate via the notes,
  not by diverging.
