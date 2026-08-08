# RDR / EQL Master Roadmap (personal — never merged)

The narrative companion to `plan.yaml` (waves/tracks/items, live-checked
against GitHub by the `/plan-dashboard` skill). This file holds everything
that isn't structured data: the recalled original design, why decisions were
made, and history. When a wave lands or the split changes, update `plan.yaml`
first (it drives the dashboard) and add the "why" here — then run
`save-plan.sh` to push both.

This file is the direct migration of the old, freestanding
`rdr-roadmap.md` (single source of truth before the plan-dashboard system
existed) — content preserved as originally written, plus one addendum
section at the end capturing what a 2026-07-20 side-quest (PR #89) found.

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

## 2. Current state as of the last freestanding update (2026-07-16)

Kept verbatim for history; `plan.yaml`'s `items[]` is now the live-checked
version of this table — read that (via `/plan-dashboard rdr-refactor`) for
current status, not this snapshot.

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

- #20 (closed unmerged): architecture brief + bibliography. Re-landed once
  as `rdr/architecture-brief` (PR #75, also closed 2026-07-24 without
  merging — see the Wave Final addendum below); the branch is kept for a
  third landing once the engine is stable.
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
  by the D-ui session): ~~#78 `D-ui-splice-fix`~~ (closed 2026-07-31,
  superseded by #118 — see §10), #79 `D-ui-rendering` (case_table +
  shell-free tests), #76 `D-ui` (interactive layer + conftest fixture +
  docs). Merge order #79 → #76.
  **Steward: the propagation chain is now D-core-engine → D-ui-rendering →
  D-ui → D-deco. #79 is still *based* on the closed `D-ui-splice-fix` branch
  and must be re-targeted onto `D-core-engine` before it can land — the
  branch still exists, so nothing is broken today, but it can no longer
  merge through #78.**
- **S2 (D-deco) — SPLIT INTO 2 STACKED PRs** (see `pr-progress/D-store.md`
  + `pr-progress/D-deco.md`): #80 `D-store` (RDRFileStore) then #77 `D-deco`
  (decorator + docs), on the new `D-ui` tip. The sweep that made #38's diff
  reach zero is dissolved now that #38 is closed; its two keeper files are
  rehomed to #76 (steward hand-off).

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
- **C1 `rdr/decision-queries`** (base: W2; REFRAMED 2026-07-17 after design
  discussion — the ExplainableChoice protocol was dropped as YAGNI): a
  choice IS an underspecified query over a partially-specified decision
  object (`an(InsertionAction)(slot=...).evaluate(backend=rdr)`); C1
  delivers the missing explanation semantics instead: model-side weak-keyed
  explanation store (never attach to shared concluded values — enum
  aliasing), explanation-bearing yielded results so `explain(result)`
  routes RDR conclusions, default-on explaining strategy (measure first),
  typed first-access failure, and the documented decision-query pattern.
  See `pr-progress/rdr/decision-queries.md` for the full rationale.
- **M1 `montessori/choice-policies` — DEFERRED** until Tom's
  `montessori_ijcai` branch is ready: only the demo-specific remainder —
  pick/hole policy RDRs as decision queries per the C1 pattern (the
  action's slot/next-shape become underspecified attributes resolved by
  query + RDR backend; no policy-injection seam needed anymore).
- **M2 `montessori/why-demo` — DEFERRED** (base: M1 + W2): narrated demo
  loop, headless CI mode emitting the why-transcript, README.
- Ordering: W1 → W2 → W3 sequential; C1 parallel to W3 (both need only W1);
  M1/M2 resume when Tom's branch is ready.
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

### Wave Final — land once the RDR engine is stable

- **`rdr/architecture-brief`** (docs-final track): re-land the closed #20 /
  #75 content (`rdr_architecture_plan.md` + bibliography). Deliberately
  deferred past Wave 3 (see the 2026-07-24 addendum below) rather than
  landed early off `main` — the brief documents the architecture as a
  finished whole, which reads oddly while the engine underneath it is
  still being restacked wave by wave.

### Dependency graph

```
main ── stack #5…#68 ── D-ui ── D-store ── D-deco   (Wave 0, sequential chain)
land ─┬─ rdr/feature-registry ── rdr/feature-capture   (Track F)
      ├─ rdr/multi-class ── rdr/general-fixpoint       (Track G)
      └─ eql/truth-unification                          (Track T)
F + G ── rdr/concept-trees                       (Wave 2)
Wave2 ─┬─ rdr/oo-definitions ──┐                 (Wave 3)
       └─ rdr/justifications ──┴─ rdr/architecture-brief   (Wave Final)
          (also needs T)
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

## 5. Addendum (2026-07-20) — PR #89 and what it found

A side-quest session (asked to "check the ripple-down-rules-refactor
status and all related PRs") opened **PR #89**
(`conditions-root-drop-dead-parent-recovery`, off `main`, not on the
session's own designated branch — that branch never got commits).

What it found, verified against live GitHub state (not just the notes
below, which is exactly the discipline `plan.yaml`'s live cross-check now
automates):

- The split stack's real PR numbers are `#5`/`#28` (query-class-refactor /
  eql-core-prep, both merged) — matching this doc's original table exactly.
  (A later note briefly misremembered these as `#452`/`#453`; that was a
  slip, not a renumbering — corrected when migrating to `plan.yaml`.)
- **#41 (rdr-backward-inference) has a real merge conflict**: an automated
  restacking bot flagged `needs-resolution` in `base_expressions.py` over
  whether `_last_parent_of_type_` should exist. #89 root-caused it:
  `_conditions_root_`'s own use of that method is genuinely dead (verified
  by instrumenting it across the full `test_eql/test_ormatic/
  test_class_diagrams/test_ripple_down_rules` suite, 1275 tests, zero
  calls), distinct from **#78's** independent, live use of the same method
  name for `insert_at`'s anchor-parent recovery (a real, proven bug: a
  shared-identity `MappedVariable` anchor keeps whichever parent attached
  first, dropping 12/21 rules on zoo-model reload). The two were diffed and
  merge-tested directly against each other: fully compatible, no
  coordination needed.
- **W1 (`rdr/why-answer`) shipped as PR #81**, on branch
  `claude/rdr-why-answer-6fnw2o` — but its own `pr-progress` note still said
  "Not started". W2/W3 already build on real `WhyAnswer`/`rule_code`
  functionality, so the note was simply never updated after the work
  landed. This is precisely the staleness class `plan.yaml` + the
  `/plan-dashboard` skill's live GitHub cross-check exists to catch
  automatically instead of requiring a session to notice it by accident.
- PR #83 (`eql/attribute-predicate-verbalization`) is open as **not
  draft**. Checking the live state of the whole programme while migrating
  it to `plan.yaml` (2026-07-21) found this isn't unique to #83: #58, #39,
  #53, #41, and #63–#67 (the lower two-thirds of the S0 stack) are also
  open as non-draft — likely marked ready deliberately once each stabilized,
  consistent with the always-drafts-until-ready personal convention, not a
  slip. Not flagged as an issue; noted here since the original draft of
  this addendum incorrectly called #83 unique.

Once #89 merges, the restacking bot should cascade the fix down through
#58 → #39 → #53 → #41, clearing #41's conflict for free. Verify that
actually happens; nudge manually if the bot doesn't pick it up.

## 6. Addendum (2026-07-23) — PR #68 review: the D-core-engine split + the expert-framework tracks

The PR #68 (`D-core-engine`) review — 71 inline threads plus a request to split
the mostly-test mega-slice into topic-oriented PRs — resolved as follows.

**The split.** `D-core-engine` is superseded by three stacked, topic-oriented
PRs, each carrying its own tests: `d-core-expert` (`expert.py`) →
`d-core-single-class` (`single_class.py`, the engine) → `d-core-backend`
(`backend.py`, the underspecified-query backend). The three form a linear stack
in that dependency order; the backend is the new tip. Everything that was stacked
on `D-core-engine` (`D-ui-splice-fix`, `rdr-why-answer`, `rdr-feature-registry`,
`rdr-multi-class`) re-points onto `d-core-backend`. PR #68 is closed once the
three open. Steward notified via #94.

**Engine design decisions locked in the review** (carried by the split PRs):
classify() returns `UNSET` (not `None`) when no rule fires; non-convergence raises
`RDRDidNotConvergeError` (a `DataclassException`) and `max_passes` is removed
(oscillation detection plus a termination test bound it); a new `rdr/exceptions.py`
holds the `DataclassException` hierarchy; conclusion validation moves onto
`ConclusionDomain`; an `AnswerName` enum replaces the duplicated `"conditions"`/
`"conclusion"` strings; `CaseContext` is built by the engine and threaded down as a
parameter object (engine owns the facts, the expert augments with its aids/
suggestion); progress and save use Null-Object defaults to retire the
`if ... is not None` guards; `backend.infer` splits into a pure `infer` (yields
`UnificationDict`) and an eager `fill`; docs stop restating field docs and stop
mentioning plans/phases/history. The auto condition-resolver plus `resolution_mode`
are kept, minimally tidied, in the interim — the resolver's `_try_auto_resolve`
eligibility clauses are marked as the seed for the capability-guarded Expert below.

**Three new tracks capture the larger ideas surfaced in the review**, all blocked
until the Wave-0 engine stack lands on main; literature pointers recorded per item
for a design-time review when each PR is picked up:

- **Expert framework** (new wave; track `expert-capabilities`). Promote each
  expert's applicability to a first-class, evaluable EQL *capability guard* so the
  engine gates delegation on the guard, not the type (ISP + LSP) — the current auto
  condition-resolver becomes one such expert whose guard is exactly its
  `_try_auto_resolve` clauses, retiring `resolution_mode`. Then cooperating experts
  (Hint mode as composition) and capability verbalization ("why can / can't this
  expert handle this situation?", reusing the rule-tree explanation machinery). Lit:
  blackboard knowledge-source activation conditions (Hearsay-II/BB1), Contract-Net
  eligibility, Chain-of-Responsibility `canHandle`; mixed-initiative/critiquing
  systems for the ensembles.
- **Audience-dependent explanation rendering** (track `comms-track`, in the
  why-montessori wave). Separate an explanation's content from its rendering, chosen
  from the recipient's model: natural language for humans, the raw EQL expression
  for programs. Lit: user-tailored NLG (Paris), Reiter & Dale, Grice's maxims,
  Sperber & Wilson relevance theory; the EQL-as-formal-derivation vs NL-gloss
  distinction ties to Wave-3 TMS justifications.
- **Engine runtime behaviour** (track `engine-runtime`, Wave 1). Beyond the interim
  classify()→`UNSET`: no-rule-fired modes (warn-and-skip, ask an available expert, a
  user-provided default conclusion) and conclusion provenance (rule vs default vs
  expert vs unset), coordinating with Wave-3 JTMS justifications; unresolved cases
  stored for later expert review.

## 7. Addendum (2026-07-24) — `rdr-architecture-brief` repositioned to Wave Final

A session dispatched to investigate whether PR #75 (`rdr/architecture-brief`) was
still needed — since `plan.yaml` already tracks it as the `S3-docs` item — checked
with the plan owner instead of assuming. The owner's call: the architecture brief
reads as a description of a *finished* system, so landing it mid-refactor (as a
Wave-0 "trivial, independent" doc PR, the original S3 framing) was the wrong
sequencing — it should be the *last* PR, once the engine it describes is actually
stable.

Applied directly (authorized by the plan owner in-session, same convention as the
2026-07-23 D-core-engine split above):

- New wave `wave-final` + track `docs-final`, replacing `S3-docs` (removed —
  nothing else used it).
- `rdr-architecture-brief` item: `track` → `docs-final`, `status` → `deferred`,
  `depends_on` → `[rdr-oo-definitions, rdr-justifications]` (Wave 3's two tips, a
  best-guess proxy for "the engine is stable" — revisit the exact edge when this
  item is next picked up), `pr` → `null`.
- **PR #75 closed, not merged.** Its branch `rdr/architecture-brief` is kept
  as-is (not deleted) so the already-refreshed content (the post-split
  `krrood/src/krrood/entity_query_language/rdr/` repo-mapping table, the
  `rdr/serialization.py` auto-serialization claim, the de-`eql_rdr`'d
  mentions) doesn't need re-doing when this item is eventually picked back up
  — only a re-verify against whatever the engine looks like by then.
- Flagged on the tracking issue (#94) per the structural-change convention,
  since this session isn't the plan's designated steward session even though
  the owner authorized the edit directly.

## 8. Addendum (2026-07-31) — `rdr-backward-inference` (#41) unblock verified

A `/plan-item-resolve` session picked up `rdr-backward-inference`, recorded as
`blocked` on the §5 conflict. Closed the verification loop §5 explicitly asked
for ("Verify that actually happens"):

- PR #89 merged to `main` on 2026-07-30. Confirmed live that the cascade worked:
  GitHub reports #41's `mergeable_state` as `clean` (previously conflicting), and
  an independent local `git merge-tree $(git merge-base origin/main
  origin/rdr-backward-inference) origin/main origin/rdr-backward-inference` — a
  real content-level dry run, not just trusting the cached GitHub field —
  produced zero `<<<<<<<` conflict markers across 1338 lines of diff.
- CI on #41 is green (18/18 checks).
- #41 had 4 unresolved review threads, all marked `is_outdated` by GitHub. Read
  the current head of the affected files directly (not just the PR's own claim)
  and confirmed all four were already fixed by commit `7faa806`:
  `what_do_we_know_about()` resolves the conditions root internally now (proven
  by a dedicated test), `ResolutionMode.SILENT` is `ResolutionMode.AUTOMATIC`,
  and `test_materialize_wraps_a_negated_guard_in_not` asserts `isinstance(...,
  Not)` plus evaluates both true/false cases. Replied to each thread citing the
  specific evidence and resolved all four.
- `plan.yaml`: `status` → `in_progress`, stale `blockers` entry removed. No code
  changes were needed on #41 itself — it's ready for the steward to merge
  bottom-up whenever picked up next.

## 9. Addendum (2026-07-31) — `D-core-serialization` (#66) restack conflict resolved

The same `/plan-item-resolve` session that unblocked §8 then picked up
`D-core-serialization`, recorded as `blocked` on a real restack conflict against
its base, `D-core-corner-case` (#65). Root-caused and resolved it:

- Confirmed live via `pull_request_read` and independently reproduced with
  `git merge-tree --write-tree origin/D-core-serialization origin/D-core-corner-case`
  (git's rename-aware three-way merge) that there were exactly two content
  conflicts — `krrood/code_generation/function_case.py` and
  `krrood/code_generation/object_to_source.py` — matching the restacking bot's
  own report exactly.
- Root cause: #66 itself renamed `krrood/code_generation/type_hints.py` →
  `object_to_source.py` (a review-driven change, confirmed in #66's resolved
  review-thread history) and repointed its importers. Independently, after #66's
  last restack (2026-07-19), further work landed on `main` via the
  `code-generation-extract` cascade that kept evolving `type_hints.py` **under
  its old name**: dropped the `_ORIGIN_TYPE_TO_HINT` special-case, dropped the
  `stringify_hint` backward-compat alias, and changed
  `get_types_to_import_from_type_hints`/`get_types_to_import_from_function_type_hints`
  to return an order-preserving `List[Type]` instead of `Set[Type]` (also
  de-abbreviating `tp` → `type_`, per AGENTS.md). Git's rename detection matched
  the two files as one across branches and auto-merged everything except two
  small overlapping hunks.
- Resolution: `function_case.py` — took `D-core-corner-case`'s full file (#66
  never touched anything else in it) and redirected its one `type_hints` import
  to `object_to_source` (same two names, unchanged). `object_to_source.py` —
  kept #66's own `render_dict_literal` addition alongside
  `D-core-corner-case`'s `List[Type]`-returning `get_types_to_import_from_type_hints`.
  Everything else (`ripple_down_rules/utils.py`'s import-block trim, `AGENTS.md`'s
  dual additions) auto-merged cleanly on its own.
- Verified before pushing: `test_code_generation` (98/98) and `test_eql_rdr`
  (57/59) pass; the 2 `test_eql_rdr` failures are `test_underspecified_match.py`
  hitting a missing `probabilistic_model.probabilistic_circuit.relational.rspn`
  submodule (the public PyPI release of `probabilistic_model` lacks it) — a
  pre-existing environment/dependency-version gap in files #66 never touches, not
  a regression from this merge.
- Pushed as commit `5f897c27` on `D-core-serialization`. `plan.yaml`: `status`
  `blocked` → `in_progress`.
- CI on `5f897c27` failed across every job (`test_each_lib (krrood)` and
  everything downstream of it) with
  `ModuleNotFoundError: No module named 'krrood.code_generation.type_hints'`
  from `krrood/ripple_down_rules/user_interface/template_file_creator.py:24`.
  Root cause: that file imports `stringify_type_hint` straight from
  `krrood.code_generation.type_hints` and was never touched by either side's
  diff during the merge (not part of #66's rename commit, and
  `D-core-corner-case` never edited that particular import line either) — so
  git's rename-aware merge had nothing to match it against and silently kept
  it pointing at the now-deleted module. This is exactly the "atomically
  updates every importer" claim from #66's own review-thread history proving
  narrower than stated: it listed `function_case.py`,
  `entity_query_language/rdr/{serialization,corner_case}.py`, and
  `ripple_down_rules/{rdr,rules,utils}.py` — never `template_file_creator.py`.
  `git grep` for `code_generation\.type_hints` on the merged tree confirmed
  this was the only remaining stale reference (and `stringify_hint`, the
  retired alias, had zero references left, confirming that part of the
  auto-merge was correct). Fixed by redirecting that one import to
  `object_to_source` and pushed as commit `2577a2e3`. Verified locally:
  `test_code_generation` (98/98), `test_eql_rdr` (57/59), and
  `test_ripple_down_rules` (229/233) all pass through the previously-broken
  import chain; the remaining 4 failures split into the same pre-existing
  `probabilistic_model` gap (2) and a missing `dot` (graphviz) binary in the
  local sandbox (2, `test_object_diagram.py`) — neither in files this PR
  touches, neither present in the PR's own documented CI environment.

## 10. Addendum (2026-07-31) — `D-core-support` (#67) investigated; the splice fix moves to `dag-facade-hardening`

A `/plan-item-resolve` session picked up `D-core-support`, which carried no recorded
blocker at all. What it found, and one cross-plan consequence.

### #67's actual state

Not a conflict, and not a bad dependency: `check_dependency_readiness.py` reports
`D-core-serialization` as `open_ready`, GitHub reports #67 `mergeable_state: clean`, and
a local `git merge-tree --write-tree` of the two branches is conflict-free with zero
stale `code_generation.type_hints` references in the merged tree (#67 touches no
`code_generation` file, and its `function_case.py` is the RDR one, not the file that
conflicted in §9). What is wrong:

1. **Stale relative to its own base.** `D-core-support` is at `8eb7518` (2026-07-19) and
   `D-core-serialization` is at `2577a2e3` — the branch is two commits behind, and those
   two commits are precisely §9's restack merge and stale-import fix. #67's green 18/18
   CI ran against the old base; nothing has ever built it on the current one.
2. **Two unresolved review threads, both waiting on the developer.** 84 of 86 are
   resolved; these two are why the PR has not moved since 2026-07-19. Both were put to
   the owner and answered in-session: `test_conclusion_domain.py`'s AGENTS.md ask is
   covered by the rule `main` has since gained (docstrings must not "narrate the review
   or implementation history"), so reply and resolve with no AGENTS.md edit; and
   `rule_tree_view.py:255` is handled below.
3. **An unrecorded collision with Track T.** #67 changes `base_expressions.py:410` from
   `current_result.is_false` to `current_result.is_condition_false`. That accessor exists
   on `main` (`base_expressions.py:971`) and is **deleted** on #99's branch (`f8a8fe56`).
   #99's #94 comment coordinates with #89/#90/#92 but not #67, whose call site postdates
   that analysis. Whichever lands second reconciles it.

Also noted: #67's description is stale (claims a `conftest.py` and an `__init__.py`
export block, neither in the current 16-file diff — `rdr/__init__.py` on the branch is a
bare docstring); #66 carries a stale `needs-resolution` label and one unrelated
giskardpy CI failure (`test_attached_self_collision_avoid_stick`, `test_each_lib
(krrood)` green); and current `main` is no longer an ancestor of the serialization tip,
so the whole stack is due another cascade.

### The `enforce_parent_consistency` thread, and where its answer lives

The review asked why the rule tree isn't consistent in the first place. It is the right
question, and the answer is not in this plan: `SymbolicExpression` is a DAG behind a
tree-shaped `_parent_` that returns whichever parent attached *first*. That is
`dag-facade-hardening`'s entire subject (tracking issue #96).

Chasing it turned up the concrete instance — `ConclusionSelector.insert_at`
(`rules/conclusion_selector.py:67`) splicing above `anchor._parent_` — **on `main`**, and
a new item `insert-at-ownership-parentage` was added to that plan to fix it at the façade
level, from the owning rule-tree context. Full rationale in that plan's own 2026-07-31
addendum.

Two consequences here:

- **#78 (`D-ui-splice-fix`) is superseded.** It fixes the same bug by reintroducing
  `_last_parent_of_type_` — a symbol #89 deleted from `main`, and a structural-accessor
  read that `dag-facade-hardening`'s Wave-1 guard test forbids and its rename would
  break. Its scope note ("`insert_at` does not exist on `main` yet") was true on
  2026-07-16 and is now stale: `rules/` has landed. It reduces to its regression test
  re-pointed at the fixed API, or closes.
  **Resolved 2026-07-31: closed as superseded** by #118, which landed the façade-level
  fix. The "re-point its regression test" half of that choice turned out not to be
  available — `TestAttributeReusedInEarlierSiblingBranch` lives in
  `test/krrood_test/test_eql_rdr/`, a directory that does not exist on `main`, and
  asserts through `walk_rules`/`classify_case` from the RDR layer. #118 covers the same
  defect DSL-only at the accessor's own contract level instead. The RDR-level test can
  be re-added against the fixed API once `test_eql_rdr/` lands; it needs no production
  change to pass.
- **#67 changes nothing.** `enforce_parent_consistency` makes no `_parent_`/`_root_`
  reads at all — it is a display-order heuristic over the flattened rule list — so it is
  neither the defect nor caught by the guard test. Keep it, reply pointing at #96 and the
  new item, resolve. Whether it becomes redundant once the façade is hardened is a
  question for then, not a promise now.

### Sequencing across the two plans

`rdr-refactor`'s Wave 0 still goes first. `dag-facade-hardening`'s
`facade-rename-and-guard` is a repo-wide rename of `_parent_`/`_root_` in
`base_expressions.py` — the file this 12-PR stack contests most — and every merge to
`main` while the stack is open costs a full cascade restack, as #89 already demonstrated.
Landing the stack first means doing that rename once against a stable `main`; it also
lets Phase D's audit see `rdr/rule_tree*.py`, which is not on `main` yet.

`insert-at-ownership-parentage` is the deliberate exception: small, off `main`, gated on
nothing, and it *removes* a future cascade rather than adding one.

## 11. Addendum (2026-08-03) — `d-core-single-class` planned; four items handed back to #98

`/plan-item-kickoff rdr-refactor d-core-single-class` produced an approved implementation
plan, saved to `.claude/personal/pr-progress/D-core-single-class.md`. No branch cut and no
code written — the implementation runs in a fresh session, since the planning session had
consumed most of its context reading #68's 71 review threads and the mega-branch.

### The scope handoff

Planning surfaced that several changes the split had filed under `d-core-single-class`
target files that already exist on `D-core-expert`: `condition_resolver.py`,
`interface.py` and `progress.py`. They were reassigned to #98 and reported there
(comment `5156702002`):

1. `ConditionResolver.resolve` takes `CaseContext` — four definitions (abstract at
   `condition_resolver.py:72`, `TargetKnowledgeResolver:115`,
   `CornerCaseKnowledgeResolver:172`, `ChainConditionResolver:208`), eight flattened
   parameters to three, plus `test_condition_resolver.py`'s 10 call sites. This is
   comment 2 of 3 in the `single_class.py:239` thread — #98 answered comment 1 (the
   expert) and left the resolver half.
2. Null-Object defaults for progress and save (`NullProgressReporter` in `progress.py`,
   nothing `Optional` left for a caller to guard on).
3. A `ProgressDescription` `StrEnum` replacing the `_FITTING_DESCRIPTION` module global.
4. Segregate `ExpertInterface` — see below.

### Item 4: from "promote onto `Expert`?" to "segregate the interface"

Item 4 was first posted as a yes/no question — should `save()` and
`make_progress_reporter()` move from `ExpertInterface` onto `Expert`, so the engine stops
reaching through `expert.interface.…`? The developer pushed back with the better question:
should the interface object be owned by the RDR rather than hidden inside `Expert`? Tracing
the consumers showed the original framing was wrong, and the answer was revised the same
day (comment `5163364467`).

The framing error: it treated the problem as *which class exposes two methods*, when the
actual defect is that `ExpertInterface` carries three unrelated responsibilities — expert
Q&A (`_run`, `interact`, `_build_namespace`, `_validate`, `_missing_required`,
`_render_header`), model persistence (`on_save`, `save()`), and fitting progress
(`make_progress_reporter()`). Only the first is genuinely the `Expert`'s.

The evidence, from the mega-branch's `single_class.py:439-440`:

```python
if expert is not None and self.save_path is not None and expert.interface.on_save is None:
    expert.interface.on_save = lambda: save_rdr_with_case(self, self.save_path)
```

The engine reaches two levels deep and *writes* to the expert's interface, installing a
callback built from the RDR's own `save_path`. The save behaviour was always the RDR's,
smuggled into the interface because that is where the plumbing lived. Corroborating: nothing
else in `krrood/src` references either method, and the only `make_progress_reporter`
overrides anywhere are two test doubles subclassing `FunctionInterface` just to inject a
progress spy (`test_single_class_rdr.py:110`, `test_fit_convergence.py:70`).

Resolution: the RDR takes a `ProgressReporter` and a save strategy as its own collaborators
with Null-Object defaults; `ExpertInterface` keeps only the Q&A surface. Giving the RDR the
*whole* interface — the developer's literal suggestion — overshoots, since that would hand
the engine the Q&A mechanism and force the RDR to pass it back on every `ask_for_*` call.
This subsumes item 2: the defaults attach to the RDR's collaborators, not to
`ExpertInterface`.

The cost, which is real: progress and Q&A share a session — in the IPython case the bar and
the prompt render into the same shell, and `make_progress_reporter()` on the interface is
what wires the bar to that shell. After the split the interactive layer constructs both and
hands them in. **D-ui (#76) is the PR that absorbs this**, and it has not merged, so this is
the cheap moment; afterwards it is a change across two merged layers.

The rule applied: split on what the work *is*, not on which PR happened to notice it. One
parameter-object refactor read twice by a reviewer is worse than one PR carrying it whole,
and #98 had already set the precedent by touching `interface.py` when its own review
required it.

### Two facts verified live, both worth carrying forward

**#98 has never had CI run on it.** `get_status` on head `ed805dc7` returns
`state: pending, total_count: 0`; the check-runs list is empty. It is `mergeable_state:
clean`, which is what the `open_ready` dependency rule keys on — so the rule passes while
nothing has actually verified the branch. Get a baseline before stacking ~3,500 lines of
ported tests on it, or the next PR's first CI result cannot be separated from what it
inherited. Worth noting the general shape: `open_ready` is a proxy for "safe to build on"
and does not imply the branch was ever tested.

**The stack is still stale, and that is fine to build on.** Unchanged since §10:
`D-core-support` `8eb7518a` (2026-07-19) still does not contain `D-core-serialization`
`2577a2e3`, `D-core-expert` `ed805dc7` sits on that stale support, and `main` `82501888`
is not an ancestor of the serialization tip either. But
`git merge-tree --write-tree origin/D-core-expert origin/D-core-serialization` exits 0
with no conflicts, and the merged tree carries zero stale `code_generation.type_hints`
references. The missing commits are entirely in `code_generation/` while
`d-core-single-class` touches only `rdr/` and `test_eql_rdr/`. So the cascade is *not* a
prerequisite for starting the item — it is the steward's own job, and it has to be redone
before anything merges anyway since `main` keeps moving.

## 12. Addendum (2026-08-03) — `rdr-backward-inference` (#41): the `negated`-vs-`Not()` design question

§8 closed this item as "ready for the steward to merge, no code changes needed." That is no
longer true, and the reason is worth recording because it is a *recurring* question rather
than a new one.

### What changed

- **2026-08-02: #41 was reparented onto `main`** (PR comment `5157212715`), since
  `ripple-down-rules-refactor`'s content landed via #53. The Files-changed view had been
  showing 268 files / +27,825 purely from measuring against a stale merge-base; the real
  diff is 7 files / +1,318. `mergeable_state: clean`, CI green 20/20 on head `cbbf7bf3`.
- **2026-08-03: a new review thread** (`r3702021144`, `backward_inference.py:64`) asks
  whether `GuardCondition.negated` should be dropped in favour of wrapping the guard
  expression in `Not()` so that "guard expression must always be true" — explicitly asking
  for the answer to consider every use of the guard across this plan, not just #41.

### The question already had an answer, on a branch that was marked for deletion

`krrood/docs/eql/backward_inference_design.md` on the `rdr-engine` mega-branch, "Key Design
Decisions" #1, records the alternative as designed and rejected:

> `GuardCondition` with negated flag — no live tree mutation. Calling `not_()` on a live EQL
> expression node sets `expression._parent_` to the new `Not` wrapper, corrupting the
> original tree's parent references.

Re-verified live rather than taken on faith: `factories.not_` → `SymbolicExpression._invert_`
→ `Not(self)` → `base_expressions.py:299` `child._parent_ = self`. The hazard is real, and it
is the same defect class `dag-facade-hardening` (#96) exists to fix (see §10).

**That doc is on the stray `krrood/docs/` path §2 records as dropped** — not the built
`krrood/doc/` tree, referenced by nothing. So the rationale for a field that is now being
questioned survives only on a stale branch. This is the same staleness class §5 caught for
`rdr/why-answer`'s progress note, except the casualty here is a design decision rather than
a status. Whatever is decided, the reason belongs in the field's own docstring.

### The eight use sites

`Not()`-wrapping is genuinely cleaner at four of six concrete sites — `holds_for` loses its
inversion, `condition_resolver._materialize` disappears entirely, `_active_path`'s
`and not guard.negated` reduces to an identity check, and `%knows`'s display branch
(`magics.py:142`) goes away. Against that: `_leaf_guards`' De Morgan recursion still needs an
internal polarity parameter either way (eager wrapping builds `Not(Not(x))`), and the
structural cost is reparenting live nodes. Small distributed wins, one structural hazard.

**Verbalization does not decide it, contrary to expectation.** Both shapes work today:
`ConditionAssembler.predicate(comparator, *, negated: bool = False)` is already exactly the
`(expression, polarity)` pair, and `NotComparatorRule` / `NotBooleanAttributeRule`
(`grammar/conditions/rules.py:495-560`) render `Not(Comparator)` by unwrapping it back into
that same call with `negated=True`. So the Why track (W1/W2, where `SufficientConditionSet`
is the reserved contrastive mechanism) is served either way.

### Two findings for whoever picks this up

- **`_materialize` violates the decision it is built on.** `condition_resolver.py:104` calls
  `not_(guard.expression)` on a live tree node — the exact mutation the flag exists to avoid,
  merely deferred from traversal time to rule-insertion time. Not fixed here: a non-mutating
  negation needs #96's façade work, and #41 is the bottom of a seven-PR stack where every
  extra commit costs a cascade.
- **`holds_for`'s evaluation comment is misleading.** `backward_inference.py:82-90` implies a
  `Not()` guard would not evaluate to a usable truth value. It would: `evaluate()`
  (`base_expressions.py:210`) maps `_process_result_` over `_true_results_()`, which already
  filters `if result.is_true`, so `any(...)` tests whether a true binding survived. The same
  reading suggests the `isinstance(result, OperationResult)` branch is unreachable, since
  `evaluate()` yields processed values — worth pinning with a test before deleting it.

### Disposition

Answered at `r3702169709`: keep the field, with the expiry condition stated plainly —
`Not()`-wrapping wins outright once #96 lands a non-mutating negation. The thread is
deliberately **left unresolved**; the call is the developer's, and no code was changed on #41
pending it.

### Resolution (same day)

The developer resolved thread `r3702021144` without a counter-argument and marked #41 **ready
for review**. The decision is therefore: **keep `GuardCondition.negated`**, on the
no-live-tree-mutation ground, with the recorded expiry — revisit if `dag-facade-hardening` (#96)
lands a non-mutating negation.

All 23 review threads on #41 are now resolved, `draft: false`, `mergeable_state: clean`, CI green
20/20. #41 is genuinely ready to merge as the stack bottom — the §8 claim that was stale this
morning is now true for a different reason.

The three follow-ups offered in the reply are **not applied**, and deliberately so: pushing to #41
would force it back to draft under the standing always-drafts-until-ready convention, undoing the
developer's own ready-for-review signal minutes after they gave it. They need an explicit
go-ahead, and are cheap to carry on whichever PR next touches these files if #41 merges first:

1. Record the no-live-tree-mutation rationale in the `negated` field's docstring — its design doc
   is on the dropped `krrood/docs/` path and will not land, so the reason is otherwise lost.
2. Correct the misleading evaluation comment at `backward_inference.py:82-90`.
3. TDD-pin whether the `isinstance(result, OperationResult)` branch in `holds_for` is reachable,
   and delete it if not.

The `_materialize` live-node mutation (`condition_resolver.py:104`) remains open and unplaced —
it is a real defect, and not this PR's to carry.

### Applied (2026-08-03, same day)

The developer chose to take the three follow-ups onto #41 rather than defer them. Pushed as
`29c27cca`; PR converted back to draft per the always-drafts-until-ready convention.

- `GuardCondition.negated`'s docstring now states why polarity is a flag (negation reparents,
  and the expression belongs to the live rule tree), so the reason survives the dropped
  `krrood/docs/` design doc.
- `holds_for`'s comment now describes the real mechanism.
- The dead `isinstance(result, OperationResult)` branch and its import are gone.

**A correction worth keeping**, because it nearly caused a real bug. §12 above recorded that
`evaluate()` "already filters `if result.is_true`", inferred from reading `_true_results_`.
Probing it directly disproved the generalisation:

| expression | case | `evaluate()` yields |
|---|---|---|
| `animal.has_fur` | `fur=True` | `[True]` |
| `animal.has_fur` | `fur=False` | `[False]` |
| `Not(animal.has_fur)` | `fur=True` | `[]` |
| `Not(animal.has_fur)` | `fur=False` | `[UnificationDict]` (truthy) |

A leaf predicate yields a bool either way, including a literal `False`. So `bool(result)` is
load-bearing; "simplifying" to `any(expression.evaluate())` on the strength of the earlier
claim would have made every false leaf guard read as true. Only the `isinstance` branch was
genuinely dead. Both rows are now pinned by
`test_guard_expressions_evaluate_to_plain_values_never_operation_results`, added before the
removal, alongside new coverage for a `Not()`-wrapped guard.

Verification followed §8's method — compare against a clean run of the same tree, not raw
counts. `test_eql` + `test_eql_rdr`: **206 failed / 935 passed** on the previous head,
**206 failed / 937 passed** after, identical failures, +2 exactly the new tests. (The 206 are
this container's missing system dependencies, plus three files excluded for the pre-existing
`probabilistic_model.probabilistic_circuit.relational.rspn` gap §9 already documented.)

**`scripts/format_docstrings.py` was deliberately not run on the result.** AGENTS.md mandates
it for modified files, but on `backward_inference.py` it rewrites the whole module — 125 lines
of unrelated rewrapping — and regresses `:return: ``True``` to `:return:``True``` (dropping the
space) in every docstring it touches. Bundling that into a stack-bottom PR conflicts with
keeping PRs focused, and it would ship a formatting regression. Flagged on the thread as
deserving its own pass across the package; the tool/file mismatch is pre-existing, not
introduced here.

The `_materialize` defect is now `dag-facade-hardening`'s `non-mutating-negation` item. When it
lands, **revisit `GuardCondition.negated`** — the recommendation here was explicitly conditional.

### Closed (2026-08-03)

The developer marked #41 **ready for review** again after the push. CI green 20/20 on head
`29c27cca`, including `test_each_lib (krrood)`; `draft: false`, `mergeable_state: clean`, all 23
threads resolved. #41 is ready to merge as the stack bottom.

Worth recording for future sessions: **CI is the load-bearing verification here, not the local
run.** This resolve session's container shipped no interpreter with the project's dependencies at
all — the 206 failures in its sweep were entirely environmental, which is exactly why the
before/after comparison (206/935 vs 206/937) rather than the absolute number was the signal. CI
runs the real environment and passed. A local sweep in a bare container can only show *no new
failures*; it cannot show *no failures*.

## 13. Addendum (2026-08-03) — `eql-truth-unification` (#99): reconciled with PR #89, landed first

A `/plan-item-resolve` session picked up `eql-truth-unification`, whose `mergeable_state` had gone
`dirty`. The maintenance bot had reported the same restack conflict three times since 2026-07-30
(20:12, then 08-03 01:19, then 08-03 09:38) without anyone resolving it.

### Root cause

**PR #89** (`conditions-root-drop-dead-parent-recovery`) merged to `main` on 2026-07-30 and
independently added a `_true_results_()` method plus reworked
`SatisfiedConditionTracker.on_conclusions_processed` — the same two things #99 changes — without
knowledge of #99's `TruthValuedExpression` fix. #99's own coordination comment on #94 named
#89/#90/#92 as touching the same functions, but that comment was written 2026-07-26, before #89's
actual content existed. #89 landed first, so #99 had to reconcile onto it.

### Resolution

Reproduced the conflict locally (a real `git merge origin/main`, not just `merge-tree`, to see the
actual conflicting content) and resolved three files:

- **`base_expressions.py`**: `main`'s `_true_results_()` (from #89) was an unconditional
  `result.is_true` filter — exactly the bug #99 exists to fix (a query selecting `0`/`[]` would be
  dropped). Kept `_true_results_()` as the named method (`main` already calls it elsewhere), but
  moved #99's `TruthValuedExpression` guard into its body; `evaluate()` goes back to the simple
  `main`-style call through it. One duplication turned out already resolved on `main`'s own side:
  #89 also added a name-lookup helper that would have overlapped with #99's
  `_subtree_expressions_with_ids_`, but `main`'s own review deleted it outright on 2026-07-30
  (commit `a4e0e39f`) once its callers switched to asserting on ids directly.
- **`evaluation.py`**: kept #99's simplified `on_conclusions_processed` body (one uniform
  `is_condition_participant`/bindings lookup, dropping `main`'s `chain_truth_map` +
  `LogicalOperator` special case — exactly #99's own stated simplification), but wired it onto
  `main`'s `active_conditions_root.has_condition` guard rather than this branch's own
  `expression._conditions_root_ is expression._root_` check. `main`'s guard is the newer,
  dedicated mechanism (`test_evaluation_context.py`, 10 tests) that other code in the merged file
  already depends on; this branch had never seen it.
- **`test_explanation.py`**: both sides had independently added a `_get_true_results(query)` test
  helper with different bodies — consolidated to delegate to the now-fixed `_true_results_()`.

### Verification

`test/krrood_test/test_eql` before vs. after the merge: **61 failed / 78 errors on both sides,
byte-for-byte identical failed+error test names** (a pre-existing `random_events` packaging gap in
this sandbox — unrelated to anything #99 or #89 touches — blocks every test that reaches the real
backend), with `+8` passed purely from tests `main` itself added since this branch last synced.
Targeted re-runs of everything the resolution actually touches all pass cleanly:
`test_evaluation_context.py` (10/10), the `test_satisfied_conditions_*`/`test_condition_graph_*`
family in `test_explanation.py` (11/11), `test_operation_result_truth.py` (26/26, excluding the one
test blocked by the same environmental gap).

Pushed as `857fb74f`. PR converted back to draft per the always-drafts-until-ready convention,
pending CI on `coraplex`/`semantic_digital_twin` — the packages this PR's cost fix has broken
before, and which a local sandbox missing `random_events` cannot exercise at all.

### The 4 open review threads from 2026-07-30

All four (`base_expressions.py:376,394,907,1183`) already carried a full Claude analysis ending in
"your call" with no code change proposed. The developer approved this session's plan, which covered
signing off on all four — replied to each with a one-line pointer and resolved them.

### Not touched

The `#67`/`#99` `is_condition_false`-removal collision recorded in §10 / tracking-issue comment
`5146833251` — #67 hasn't merged, so it isn't part of `main` yet. Still "whichever lands second
reconciles it."

## 14. Addendum (2026-08-06) — `d-core-expert` (#98): the four handed-back items landed; the CI trigger is a real, separate problem

A `/plan-item-resolve` session picked up `d-core-expert`. What it found, what it changed, and one
thing it could not fix.

### What was actually stalling it

Not a conflict and not a bad base: #98 was `mergeable_state: clean` against `D-core-support`, and
**all 27 review threads were resolved** — including `PRRT_kwDOQhJw3c6VZoGj` (`interface.py:127`,
"why keep the `__call__` methods?"), which `pr-progress/D-core-expert.md` still recorded as open
and waiting on the developer. The developer had resolved it without a counter-argument, so the
decision was already made: **keep `AnswerValidator.__call__`**. That note was stale, in the same
class §5 caught for `rdr/why-answer`'s progress note.

What actually stalled it was §11's four handed-back items, none of which had been implemented —
confirmed by diff, not by the notes: `condition_resolver.py` and `progress.py` did not appear in
#98's 9-file diff at all. Items 1–3 were decided; **item 4 had no answer anywhere** — not on the
PR, not on #94, not here. Put to the developer, who chose to segregate `ExpertInterface`.

### What landed (commit `28a89ff4`)

- **`ConditionResolver.resolve` takes `CaseContext`** across all four definitions, eight flattened
  parameters down to three. The firing anchor comes off `context.trace.firing_anchor`, so
  `_active_path` now guards on both an absent trace and an absent anchor — the second case is new
  (an empty rule tree produces no trace at all) and is pinned by its own test.
- **`ExpertInterface` segregated to the Q&A surface.** `ModelSaver`/`NullModelSaver`/`FileModelSaver`
  landed in `serialization.py` rather than a new `persistence.py` — `save_rdr_with_case` already
  lives there, and a new module would have needed to import it anyway. `NullProgressReporter`
  landed in `progress.py`. The RDR holds both; `expert.interface.on_save = lambda: …` has nothing
  left to reach through.
- **`ProgressDescription(StrEnum)`** replaces `_FITTING_DESCRIPTION`. Worth recording the tension
  honestly: that global does not exist on this branch — its only consumer is the mega-branch's
  `single_class.py` — so this lands a type whose consumer arrives in the next slice. Same shape as
  `CaseContext` in #98's first round, and the same YAGNI question could be asked of both.

`FileModelSaver` is tested here against `test_serialization.py`'s existing `_SerializableRuleTree`
stand-in; the engine-level round trip stays `d-core-single-class`'s, as that module's docstring
already says.

### Verification followed §12's method, and it mattered again

This container also shipped without the project's dependencies — and, separately, with the wrong
Python: `pyproject.toml` requires `>=3.12,<3.13` and the default interpreter was 3.11, which fails
inside `class_diagram.py` on `make_dataclass(module=…)` (a 3.12 addition). A 3.12 venv plus the
dependency set got the suite running, minus `probabilistic_model`'s `relational.rspn` submodule,
which the public PyPI release still lacks (§9's gap, unchanged).

- `test_eql_rdr`: **6 failed / 113 passed** before, **6 failed / 125 passed** after — identical
  failure set, all six the `rspn` gap, and the +12 exactly the new tests.
- `test_eql`: failure sets diffed **byte-for-byte identical** (211 entries) on both sides.

### The CI trigger is a genuine, unsolved problem — and the plan's assumed fix does not work

§11 recorded that #98 had never had CI run on it. That is still true, and it is worse than a
missing run: **it is not self-healing.** Verified this session:

- Workflow runs exist for `a235d4bd` (green) and `b772e959` (failed, `coraplex` flake only). The
  three commits since — `ad75cf4e`, `ed805dc7`, and now `28a89ff4` — queued **nothing**.
- It is not repo-wide: `ci.yml` ran on a dozen other branches through 2026-08-05, including other
  Claude-session branches.
- `ci.yml` has no `workflow_dispatch`, so it cannot be dispatched manually.

The resolve plan assumed "the implementation push supplies the baseline". **That assumption was
wrong** — the push landed and no run was queued. Immediately after it, GitHub reported #98's
`mergeable_state` as `unknown`, which is the most likely lead: a `pull_request` workflow runs
against `refs/pull/98/merge`, and that ref cannot be computed while mergeability is unresolved.
Whether it settles on its own is not something this session could establish without waiting.

Worth carrying forward, because it invalidates a readiness assumption the dashboard makes:
`open_ready` keys on open + non-draft only. It is a proxy for "safe to build on" and, as §11
already warned, does not imply the branch was ever tested. #98 is the concrete case — clean,
non-draft-eligible, and never once verified by CI.

### A dependency regression nothing flagged

`D-core-support` (#67), this item's only `depends_on`, is now `mergeable_state: dirty` with a
`needs-resolution` label. §10 and §11 both recorded it clean. Cause: `D-core-serialization`
advanced to `08f2fbdd` (a 2026-08-03 merge of `D-core-corner-case`) while #67 stayed at
`8eb7518a` (2026-07-19), so it is now three commits behind rather than two.

This does **not** block #98 — #98's own base is unchanged at `8eb7518a` and #98 is clean against
it — but it blocks the stack landing, and the readiness rule reports #67 as `OPEN_READY`
regardless, so neither the manifest nor the dashboard shows it. Steward's job, per §11's standing
call that the cascade is not a prerequisite for working an item.

### One formatter deviation, same as §12's

`scripts/format_docstrings.py` rewrote `serialization.py` wholesale — ~180 lines of docstring
rewrapping unrelated to the change — and similar churn in `test_serialization.py`, where the real
change is a small addition. That churn was reverted in those two files and the formatter's output
kept in the files this commit substantially rewrites. No `:return:`-space regression appeared this
time. The tool still deserves its own pass across the package, as §12 already concluded for
`backward_inference.py`.

## 15. Addendum (2026-08-08) — `rdr-backward-inference` (#41): where the selector branching logic belongs

§12 closed this item twice as "ready to merge". The developer reopened it as a *design*
question rather than a defect, and the answer is worth recording because the reasoning
generalises past this PR.

### The question

Should `GuardCondition` move into `rules/conclusion_selector.py`; should the conclusion
selectors move into `rdr/` beside it; or are `_leaf_guards` / `_collect_rule_paths` fine
as they are, since the selectors are a closed set of branching logic?

### Neither move — the layering decides it both ways

- **Selectors into `rdr/`**: `rules/conclusion_selector.py` is on `main` with EQL-core
  consumers that have nothing to do with RDR — `factories.py:562,575,588` (the public
  `refinement()` / `alternative()` / `next_rule()` DSL), `scope.py:121-123`,
  `query_graph.py:312`. They are EQL operators by inheritance too
  (`Refinement(LogicalBinaryOperator)`, `Alternative(OR)`, `Next(EQLUnion)`). The move
  points the DSL front door at the RDR subpackage.
- **`GuardCondition` into `rules/`**: the same error smaller. It is a backward-chaining
  concept — a leaf predicate plus the polarity under which a path was taken — and every
  consumer is in `rdr/` (`backward_inference.py`, `condition_resolver.py`, `%knows`).
  Nothing in forward evaluation needs it. YAGNI until a non-RDR consumer exists.

### "Closed set, leave it" was half right, and extensibility was the weaker argument

Refinement / alternative / next is RDR's fixed branch vocabulary, and neither Track G nor
Wave 2 obviously adds a selector — so the open/closed case does not rest on a fourth
selector arriving. Two other things were wrong:

1. **The code disagreed with itself.** `ConclusionSelector` already makes the *insertion*
   side polymorphic (`_get_current_context_condition`, `_create_between_two_expressions`
   are abstract per-selector classmethods, deliberately not an `isinstance` ladder in
   `factories.py`). The *traversal* side was an `isinstance` ladder over the same classes.
2. **One rule set lived in two functions.** `_leaf_guards` and `_collect_rule_paths` are
   not duplicated code, but they are two facets of one per-selector semantics, with
   nothing forcing them to change together.

### What landed (`19e387a9`)

`rdr/branch_semantics.py`: `SelectorBranchSemantics`, one concrete class per selector
holding **both** halves — `sibling_guards` (decompose as a competing sibling branch) and
`branches` (children to descend into, with their entry guards). Dispatch reuses
`krrood/patterns/specificity_ranking.py` (`concrete_subclasses`, `mro_depth`,
`sole_maximum`), the same primitives behind the grammar's `PhraseRule` registry and its
`SpecificityRule` families — so this is the repo's existing answer to per-node-type
behaviour owned by a *consuming* layer, not a new mechanism. Equally specific candidates
raise `AmbiguousBranchSemanticsError` (new `rdr/exceptions.py`) rather than resolving by
declaration order.

The `Not(ConclusionSelector)` De Morgan pushdown deliberately stayed in `_leaf_guards` —
it is a core-operator case, not selector dispatch. One incidental find: `_leaf_guards`'
`Alternative` branch had an `if negated:` whose two arms were byte-identical.

### A hypothesis that did not survive the probe

The plan flagged a suspected soundness bug: `_leaf_guards(Alternative(A, B),
negated=False)` returns `[A, B]`, and `SufficientConditionSet` **conjoins**, so a positive
`Alternative` guard would read `A AND B` where the semantics is `A OR B`.

Instrumenting `_leaf_guards` across four DSL-built shapes recorded positive-Alternative
calls of **0, 0, 0, 1** — only a hand-built `Refinement(Alternative(A,B), C)` triggers it.
The reason is structural: `refinement()` anchors on a `with`-entered condition while
`alternative()` / `next_rule()` anchor on the conditions root, so an `Alternative` is
always spliced *above* a refinement, never as its left child.

So: unreachable, no semantics changed, and the constraint is now stated on
`AlternativeBranchSemantics` instead of being implicit. This is §12's measure-don't-reason
lesson applying in the other direction — there the probe *disproved* a claimed
simplification, here it disproved a claimed bug. Both times the instrumented run, not the
reading, was the evidence.

### Verification

`test_eql_rdr` 33 → 45, the 33 existing ones untouched. The 3 open/closed and specificity
tests were mutation-checked (pointing the test semantics at a different selector makes
exactly those 3 fail, falling back to `AlternativeBranchSemantics`), so they are not
vacuous. Sweep over `test_eql` + `test_eql_rdr` against this branch's previous head in the
same container: **109 failed / 921 passed → 109 failed / 933 passed**, 264 failed+errored
ids byte-for-byte identical, +12 exactly the new tests. Per §12's standing note, CI is
still the load-bearing check.

### Two things carried forward

- **`rdr/exceptions.py` now exists here.** §6 plans a module at that path for the `D-core`
  split; that is an additive merge, not a conflict, but whoever lands it should know.
- **This session could not subscribe to #41.** Both `subscribe_pr_activity` tools returned
  "Could not subscribe to this PR", so the post-push CI result is unwatched — unlike every
  earlier round on this item. Check it by hand.

### Scoping, applied rather than assumed

`git ls-tree main -- .../rdr/backward_inference.py` is empty; `conclusion_selector.py`
exists. The change as landed touches only files #41 introduces, and nothing in it stands
alone without #41 — so it folded into #41 rather than becoming a separate PR from the
session's own branch (`claude/rdr-guard-conclusion-arch-8htmfu`, which stays unused). #41
went back to draft per the always-drafts-until-ready convention, for the third time on
this PR, which the developer chose knowingly.

## 16. Addendum (2026-08-08) — `rdr-backward-inference` (#41): the review round on the family

§15's `19e387a9` drew 11 review threads the same evening. Ten were applied; one was a
design question the developer settled against this session's own recommendation, and one
was a genuine defect in the tests §15 had just praised.

### The developer kept the family, over my advice

The reviewer asked directly whether the strategy family was overkill "for something we
know will not be extended further and has well-known semantics", and whether methods on
the selector classes would be better. Asked to answer in-session rather than on the PR.

**My answer was that they were right and I had over-built it**, on three grounds:

1. **Ratio.** +659/−91: `branch_semantics.py` (267) and `exceptions.py` (39) replacing 81
   lines of `isinstance` ladders, plus 318 lines of tests. The specificity-ranking dispatch
   solves a problem verbalization genuinely has — 30 `PhraseRule` subclasses across 7
   packages, with `when` guards and real subsumption — and this one does not: 3 classes, no
   guards, no subsumption.
2. **§15's own argument cut the other way.** It justified the family partly on
   "`ConclusionSelector` already makes insertion polymorphic via
   `_get_current_context_condition` / `_create_between_two_expressions`". Those are *methods
   on the selector classes*. Read properly that argues for putting branch semantics there
   too — the reviewer's suggestion — so §15 used a consistency argument and then broke the
   consistency.
3. **Extensibility.** §15's own probe already said refinement / alternative / next is RDR's
   fixed vocabulary, and neither Track G nor Wave 2 adds a branch operator. §15 said so and
   built for extensibility anyway.

A coupling worth carrying forward: if the semantics ever *do* move onto the selectors, the
natural return type is an `(expression, polarity)` pair — an EQL-level concept, not an RDR
one (`ConditionAssembler.predicate(comparator, *, negated=False)` is already that shape).
That would make the developer's *original* question — should `GuardCondition` live in
`rules/`? — coherent in a way §15 argued it was not. §15 answered the first question partly
on grounds the second undermines.

**Developer's call: keep the family, apply everything else.** Landed as `b0107c76`. The
thread is deliberately left unresolved, per the standing rule that a thread answered
differently from its ask is the developer's to close.

### The defect: `==` on symbolic expressions asserts nothing

The reviewer flagged that comparing expressions with `==` triggers `__eq__`, which builds a
`Comparator`. Probing it showed the consequence is total, not marginal:

| assertion | result |
|---|---|
| `nodes == [correct expressions]` | `True` |
| `nodes == [wrong expressions]` | `True` |
| `[n._id_ …] == [correct ids]` | `True` |
| `[n._id_ …] == [wrong ids]` | `False` |

The `Comparator` is truthy, so list/tuple comparison reports equality for *any* two
expressions. **Nine assertions in `test_branch_semantics.py` asserted nothing about which
expression came back.** Only the `negated` booleans and the list lengths did any work —
which is why §15's mutation check still passed: the mutant it used changed a list *length*.

Fixed by comparing `_id_` through a helper whose docstring records the trap, then
re-mutation-checked with three mutants the old form could not catch — swapped `Refinement`
branch order, `Next` repeating one child, `Alternative` dropping a side — each failing
exactly one test. The other two `test_eql_rdr` files were audited and are clean.

This is the same lesson as §12 and §15 in a third variant: the assertion *looked* specific,
and only running a deliberately-wrong expectation showed it was not.

### The other nine

- **`ClassVar` → bound generic parameter.** `SelectorBranchSemantics` is now
  `Generic[SelectorType]` + `SubClassSafeGeneric`, each member binding it
  (`SelectorBranchSemantics[Refinement]`) and reading it back via
  `get_generic_type_parameters()`. One constraint found by spiking it first: **`frozen=True`
  had to go** — `SubClassSafeGeneric` is a plain dataclass and Python rejects a frozen
  dataclass inheriting from a non-frozen one.
- **Classmethods throughout**, so `most_specific_for` returns the class and nothing is
  constructed.
- **Quotes off the type alias**, which needed `GuardCondition` moved to
  `rdr/guard_condition.py`: `backward_inference` runtime-imports `branch_semantics`, so the
  reverse import was a cycle, and `from __future__ import annotations` does not help a
  type-alias *value*.
- Abstract methods take `ConclusionSelector`; `GuardedBranch.node` → `child_expression`;
  docstrings lose their cross-references to the grammar; test asserts on lengths and on
  `__name__` rather than literals.

### Also

- **PR #148** opened off `main` (draft) recording the `SubClassSafeGeneric` rule in
  `AGENTS.md`, at the reviewer's request. It deliberately does not migrate
  `PhraseRule.construct` or the `SpecificityRule` families, and says so.
- `scripts/format_docstrings.py` reproduced §12's `:return: ``True``` → `:return:``True```
  regression on the moved `guard_condition.py`; reverted that one line by hand. Third
  recorded instance of the same tool defect.
- Sweep unchanged from §15's baseline: 109 failed / 933 passed, 264 failed+errored ids
  byte-for-byte identical.
