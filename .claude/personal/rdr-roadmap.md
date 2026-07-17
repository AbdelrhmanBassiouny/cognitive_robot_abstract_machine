# RDR / EQL Master Roadmap (personal — never merged)

Single source of truth for the whole RDR-on-EQL programme: the recalled
original plan, where every piece currently stands, and the wave-by-wave
PR/session split. Each planned PR has (or gets) a plan note in
`.claude/personal/pr-progress/<branch>.md`, auto-loaded by session-start.sh
when a session checks that branch out. Update this file whenever a wave
lands or the split changes.

## 1. The original plan (recalled)

Three design documents, all currently living on branches (not yet on main):

1. **`krrood/doc/eql/developer/eql_rdr_refactor_plan.md`** (on `rdr-engine` /
   `rdr/oo-plan`) — the EQL-native RDR engine, Phases 0–8: rule tree as a live
   EQL DAG (no strings, no AST round-trip), RDR as an `EvaluationObserver`
   (AOP) on EQL evaluation, live-DAG growth via `Refinement`/`Alternative`
   insertion, expert answers as live EQL expressions, Python-file persistence
   via the unparser, underspecified (`...`) backend, Expert/ExpertInterface
   strategy split. **Status: implemented on the mega-branch; being landed via
   the split-PR stack (section 2).**
2. **`krrood/doc/eql/developer/rdr_architecture_plan.md`** (on `rdr/oo-plan`;
   PR #20 that carried it was closed unmerged — the doc must be re-landed) —
   the forward architecture:
   - **Feature layer** — named, memoized, registry-backed derived features;
     rules reference features by name; one `CaseView` per case per run =
     each feature computed once regardless of rule count (**the "poor man's
     Rete"**).
   - **MCRDR + GRDR port** — the new `entity_query_language/rdr` has
     SCRDR only; multi-class and the general fixpoint loop must be ported
     from legacy `ripple_down_rules` with the dependency graph and the
     monotonic-conclusions contract designed in.
   - **Concept trees (NRDR / nested RDR)** — trees declared as *vocabulary*
     (named boolean/typed conclusions other trees may reference), a
     **declared dependency graph** between trees, stratified evaluation
     order, semi-naive re-firing (Datalog semantics), cornerstone-regression
     checks on shared-concept edits, upstream-fix routing in the KA UX.
   - **OO integration** — per-class `definition` RDRs (Specification
     pattern, colocated with the class), candidate generators
     (hypothesize-and-test), the case as `(candidate, scoped view)` (Law of
     Demeter), taxonomy-level discriminators for exclusive siblings; the
     engine supplies upstream conclusions bottom-up over the **dependency
     graph between class definitions** (inversion of control — definitions
     never call definitions).
   - **TMS (JTMS)** — justification recording per conclusion → incremental
     retract/recompute on world change + free explanations.
3. **`krrood/doc/eql/developer/operation_result_truth_unification.md`** (on
   `rdr/oo-plan`; trimmed out of PR #28) — planned EQL-core cleanup: remove
   the `is_false` field, make truth always read from `bindings[self._id_]`,
   retire `is_condition_false`. Prerequisite-quality groundwork for TMS
   justification recording.

## 2. Current state (2026-07-16)

### The split-PR stack (refactor-plan delivery), bottom-up

| PR | branch | base | state |
|---|---|---|---|
| #5 | query-class-refactor | main | ready, under review |
| #28 | eql-core-prep | query-class-refactor | ready, green, watched |
| #58 | code-extraction | eql-core-prep | open |
| #39 | code-generation-extract | code-extraction | open |
| #53 | ripple-down-rules-refactor | code-generation-extract | open (Qt/GUI + JSON serialization removed here) |
| #41 | rdr-backward-inference | ripple-down-rules-refactor | open |
| #63 | D-core-aid | rdr-backward-inference | open |
| #64 | D-core-underspecified | D-core-aid | open |
| #65 | D-core-corner-case | D-core-underspecified | open |
| #66 | D-core-serialization | D-core-corner-case | open |
| #67 | D-core-support | D-core-serialization | draft |
| #68 | D-core-engine | D-core-support | draft |
| #38 | rdr-engine (umbrella) | eql-core-prep | draft; close once remainder is split |

Split tip `D-core-engine` already contains the full core `rdr/` package
(aid, backend, backward_inference, conclusion_domain, condition_resolver,
corner_case, expert, function_case, interface, observer, progress,
rule_tree, rule_tree_view, serialization, single_class, underspecified) and
its tests.

### Still unsplit (in umbrella #38 only)

- **D-ui** — `rdr/interactive.py`, `rdr/magics.py`, `rdr/case_table.py`,
  `rdr/prompt_examples.py`, `rdr/prompt_sections.py` + the interactive/
  rendering/magic tests and `fitted_models/`. Plan:
  `pr-progress/D-ui.md`.
- **D-deco — SPLIT INTO 2 STACKED PRs** (2026-07-16, review-size): #80
  `D-store` (`rdr/file_store.py` + `test_rdr_file_store.py`; RDRFileStore
  lifecycle, self-tested with no decorator dep) then #77 `D-deco`
  (`rdr/decorator.py`, `rdr/templates/rdr_empty.py.jinja`,
  `test_rdr_decorator.py`, `rdr_decorator.md` dev+user). Merge order
  #80 → #77. Plans: `pr-progress/D-store.md`, `pr-progress/D-deco.md`.
  **Steward: propagation chain now …→ D-ui → D-store → D-deco — register
  D-store in the restack loop.**
- Old task "D-ser" is subsumed: `serialization.py` landed as #66; the
  serializer-adjacent tests ride D-ui (they exercise interactive save).
- Legacy `ripple_down_rules` leftovers on the umbrella (gui.py,
  tracked_object.py, predicates.py, types.py, JSON tests) are
  **deliberately dropped** (removed by #53) — do not port them.
- RDR docs (`rdr_decorator.md` ride with D-deco #77). The umbrella-closure
  "sweep" that briefly rode D-deco is dissolved (2026-07-16): #38 was
  already closed, so its zero-diff justification was spent. Only genuinely
  additive, non-duplicate files are rehomed — `rdr_conclusion_domain.py`
  (D-ui's `eql_rdr_conclusion_asking.md` imports it) and
  `test_rule_tree_view.py` (only real coverage of the rule-tree renderer)
  → **rehome to #76 (D-ui), handed to the steward**. `eql_rdr_refactor_plan.md`
  is a dangling (un-indexed) design doc → offered to steward for #68 or drop.
  `backward_inference_{design,user_guide}.md` sit in a stray `krrood/docs/`
  path (not the built `krrood/doc/` tree, referenced by nothing) → **dropped**.

### OO-track prototypes (stale bases — do not merge as-is)

- #20 (closed unmerged): architecture brief + bibliography. Re-land as the
  small docs PR `rdr/architecture-brief` off main.
- #21 `rdr/oo-recognition` (draft): `rdr/recognition/` package — definition,
  engine, registry, candidate generators, `has_candidates`, predicates +
  `test_recognition.py`. Prototype input for Wave 3.
- #22 `rdr/backend-unification` (draft): unifies recognition with the
  query/underspecified backend frontend. Prototype input for Wave 3.

## 3. Waves and parallel sessions

Rule of thumb: sessions may run in parallel iff their PRs touch disjoint
files AND neither needs the other's branch as base. Everything below main
is stacked, so "parallel" means parallel *tracks*, each track internally
sequential.

### Wave 0 — finish landing the engine (start now, 3 parallel sessions)

- **S0 (steward):** babysit the open stack bottom-up; merge #5 → #28 → …;
  propagate restacks forward after each merge (this is the standing
  session's job today).
- **S1 (D-ui) — SPLIT INTO 3 STACKED PRs** (see `pr-progress/D-ui.md`, owned
  by the D-ui session): #78 `D-ui-splice-fix` (insert_at splice engine fix,
  may fold into #68 — steward decision pending), #79 `D-ui-rendering`
  (case_table + shell-free tests), #76 `D-ui` (interactive layer + conftest
  fixture + docs). Merge order #78 → #79 → #76.
  **Steward: the propagation chain is now D-core-engine → D-ui-splice-fix →
  D-ui-rendering → D-ui → D-deco — register the two intermediate branches in
  any restack loop.**
- **S2 (D-deco) — SPLIT INTO 2 STACKED PRs** (see `pr-progress/D-store.md`
  + `pr-progress/D-deco.md`): #80 `D-store` (RDRFileStore) then #77 `D-deco`
  (decorator + docs), on the new `D-ui` tip. The sweep that made #38's diff
  reach zero is dissolved now that #38 is closed; its two keeper files are
  rehomed to #76 (steward hand-off).
- **S3 (docs, off main):** `rdr/architecture-brief` — re-land the closed
  #20 content (`rdr_architecture_plan.md` + bibliography). Trivial,
  independent, unblocks every Wave-1+ session's shared context.

### Why & Montessori track — PRIORITY after Wave 0 (decided 2026-07-16)

Why-questions on RDR conclusions + the Montessori shape-sorting demo take
priority over Tracks F/G/T below (those start only when sessions are free).
Full design: plan session 2026-07-16; per-PR notes exist for every branch.

- **W1 `rdr/why-answer`** (base: D-core-engine): WhyQuestion/WhyAnswer value
  objects built from ClassificationTrace/FiredConclusion,
  `EQLSingleClassRDR.why(case)`, backend explain-path, Explanation
  unification with `explain_inference`. Plain why in v1; contrast field
  reserved (contrastive = follow-up via SufficientConditionSet).
- **W2 `eql/causal-verbalization`** (base: W1): "because" vocabulary +
  `grammar/causal/` assembler (InferenceAssembler pattern), routing beside
  the Match special case, binding-threading; `WhyAnswer.verbalize()`.
- **W3 `rdr/why-query-surface`** (base: W2): `why(...)` EQL factory + docs +
  bibliography (provenance witnesses, JTMS, RDR traces, Miller contrastive).
  `%why` magic deferred until D-ui #76 lands.
- **M1 `montessori/choice-policies`** (base: `tomsch420/montessori_ijcai`
  tip b4b45382d + W1; SHARED with Tom Schierenbeck — coordinate):
  `ExplainableChoice` protocol over RDRBackend/underspecified (generic,
  krrood), pick_policy + hole_policy RDRs replacing the procedural
  `hole_for` loop and fixed insertion order, policy seam on
  `InsertMontessoriShapeAction`.
- **M2 `montessori/why-demo`** (base: M1 + W2): narrated demo loop, headless
  CI mode emitting the why-transcript, README.
- Ordering: W1 → W2 → W3 sequential (one session track); M1 starts once W1's
  API shape is pushed; M2 after W2 + M1.
- Conflict watch: Tom's branch modifies krrood verbalization files W2 also
  touches (`vocabulary/english.py`, `fragments/base.py`,
  `parts_of_speech.py`) plus `factories.py`/`predicate.py`.

### Wave 1 — independent foundations (after the stack lands on main; 3 parallel tracks; AFTER the Why & Montessori track per priority decision)

- **Track F — feature layer ("poor man's Rete"):**
  `rdr/feature-registry` (registry + CaseView memoization + EQL name
  resolution) then `rdr/feature-capture` (%feature magic, AST-hash dedup,
  registry autocomplete). Plans: `pr-progress/rdr/feature-registry.md`.
- **Track G — multi-tree engines:** `rdr/multi-class` (MCRDR: iterable /
  multi-valued attributes; lifts the single-valued guard in
  `underspecified.py`) then `rdr/general-fixpoint` (GRDR naive fixpoint +
  monotonic-conclusions contract + recorded dependency edges). Plans:
  `pr-progress/rdr/multi-class.md`, `pr-progress/rdr/general-fixpoint.md`.
- **Track T — truth unification:** `eql/truth-unification` (EQL core only;
  touches `core/base_expressions.py` + operators, so it must WAIT until
  #28 has merged to avoid stack conflicts — it is Wave 1, not Wave 0).
  Plan: `pr-progress/eql/truth-unification.md`.

### Wave 2 — concept trees (needs F + G)

- `rdr/concept-trees`: concept declaration, explicit `DependencyGraph`,
  stratified order, semi-naive firing strategy, cornerstone-regression gate
  on shared-feature/concept edits, upstream-fix routing hooks. Plan:
  `pr-progress/rdr/concept-trees.md`.

### Wave 3 — OO integration + TMS (needs Wave 2; two parallel tracks)

- `rdr/oo-definitions`: definition-classmethod protocol, candidate-generator
  protocol, `(candidate, scoped view)` case type, taxonomy discriminators;
  harvest #21/#22 prototypes, then close them. Plan:
  `pr-progress/rdr/oo-definitions.md`.
- `rdr/justifications` (TMS): `Justification` value object +
  `JustificationRecorder(EvaluationObserver)` + retraction propagation over
  the dependency graph (needs Track T's unified truth). Plan:
  `pr-progress/rdr/justifications.md`.

### Dependency graph

```
main ── stack #5…#68 ── D-ui ── D-store ── D-deco   (Wave 0, sequential chain)
main ── rdr/architecture-brief                   (Wave 0, parallel)
land ─┬─ rdr/feature-registry ── rdr/feature-capture   (Track F)
      ├─ rdr/multi-class ── rdr/general-fixpoint       (Track G)
      └─ eql/truth-unification                          (Track T)
F + G ── rdr/concept-trees                       (Wave 2)
Wave2 ─┬─ rdr/oo-definitions                     (Wave 3)
       └─ rdr/justifications  (also needs T)     (Wave 3)
```

## 4. Standing conventions for every session in this programme

- Follow `.claude/personal/cram-notes.md` (drafts, session link, subscribe,
  keep description current, pr-progress upkeep via save-pr-progress.sh).
- SOLID is a review gate, not an afterthought: every new capability enters
  as an abstraction (ABC/protocol) plus small dataclass implementations;
  strategies (evaluation order, interfaces, backends) must be substitutable
  without touching the engine (see the per-PR notes for the concrete
  class-level splits).
- TDD: failing test first, no test modification to make things pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in
  `test/krrood_test/dataset`.
