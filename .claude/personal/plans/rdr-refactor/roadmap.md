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
2. Null-Object defaults on `interface.py` + `progress.py`.
3. A `ProgressDescription` `StrEnum` replacing the `_FITTING_DESCRIPTION` module global.
4. Open question: should `save()` / `make_progress_reporter()` move from
   `ExpertInterface` onto `Expert`? Default is no; it changes #98's public API, so it is
   cheaper to settle while #98 is open.

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
