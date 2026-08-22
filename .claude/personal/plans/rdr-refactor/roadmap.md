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

## 17. Addendum (2026-08-09) — `rdr-backward-inference` (#41): `UNSET` unified with `...`

The developer asked whether `UNSET` can be removed in favour of `...` (`Ellipsis`), so the
RDR sentinel conforms with what underspecified statements already use — or whether that
collides with Ellipsis's existing meaning. Recorded because the first answer was wrong, and
wrong on a principle worth not repeating.

### The wrong answer, and what disproved it

The first answer was "no, it collides", argued from the principle that *a sentinel over `Any`
must sit outside the value space it guards*. That principle is sound in general and wrong for
this codebase.

`CountRange` already reads `...` as an **outcome-side** "not yet determined":
`operators/aggregators.py:234` counts `value is ...` over an evaluated `child_result.value`,
and `:268` does the same over the child's domain via `_count_ellipsis_in_domain_`. Each `...`
widens the result from a plain `int` to a closed `SimpleInterval`. So EQL deliberately puts
"undetermined" *inside* the value space and reasons about it — which is exactly what `UNSET`
means when no rule fired.

The developer's framing was the correct one from the start: `...` means **"an oracle must
supply this value"**, and it does not matter whether the oracle is a human expert, a
probabilistic model, or an RDR. `rdr/backend.py` is that argument in code — it is the RDR
playing the role `ProbabilisticBackend` plays for a model.

### What was checked before agreeing

| concern | finding |
|---|---|
| Can a *case attribute* holding `...` confuse an existing Ellipsis check? | No. Every check reads the **query template**: `backends.py:181,198` and `parametrization/parameterizer.py:160-170,237` read `attribute_match.assigned_value`; `query/match.py:462-463` reads the match's own assignments; `verbalization/grammar/match/planner.py:199` reads a `Literal._value_`. None reads a case instance. |
| Persistence | `type(Ellipsis)` is already in `ormatic/utils.py:118`'s `leaf_types`, so a case carrying `...` round-trips. |
| Mechanics | Both are singletons compared with `is`; every `is UNSET` / `is not UNSET` substitutes unchanged. |
| Display | `_Unset.__repr__`/`__str__` rendered `"UNSET"` deliberately, but `git grep` found **no** consumers on `D-ui` (`magics.py`, `case_table.py`, `interactive.py`, `prompt_sections.py`). Cosmetic. |

### The one thing that does not fall out for free

Not a collision — a **narrowing**, left as a probe rather than an argument, per §12's and
§15's standing lesson.

`parametrization/parameterizer.py:167` raises `InvalidEllipsis` when `...` is assigned to a
field whose type is outside `random_events.variable.compatible_types` (`int`, `float`, `bool`,
`Enum`). `UNSET` has no such restriction, and `ConclusionDomain` explicitly supports
non-enumerable conclusions (`str`, arbitrary classes) with a type-check fallback. So an
unclassified case whose conclusion attribute is a `str` holds `...` after `backend.py`'s
`setattr` and would hit `InvalidEllipsis` **if** such a case can reach the parameterizer.
Filed on `no-rule-fired-resolution`, which also inherits the second consequence: an expert
typing `conclusion = ...` is now *delegating to a backend*, which
`make_conclusion_validator` (`expert.py:94`) currently rejects as "No rule fired for this case".

### What landed (`efc8a0679`), and why so little

`UNSET` had **zero consumers on #41**: `git grep UNSET` matched only `rdr/utils.py` itself and
nothing imported `rdr.utils`. All ~40 sites (`backend.py`, `expert.py`, `interface.py`,
`observer.py`, `single_class.py` + tests) land with the D-core slices. So #41's share of this
change is deleting a dead module — which also clears the catch-all `utils` filename AGENTS.md
forbids for a module holding one value. The substitution, the probe and the tests that pin them
belong on `d-core-expert` and above, where there is something to run them against.

One defect to fix while doing that: `single_class.classify` is annotated `-> Optional[Any]`
with *"or `None` if no rule fires"* while it returns `self._observe(case).conclusion` — the
sentinel (`observer.py:132-137`). §6's `classify()`→`UNSET` decision was implemented in the
observer and the signature never followed.

### `query_graph.pdf`, and a mechanism reproduced by accident

The same commit restores `query_graph.pdf` to `main`'s blob, answering a thread
(`PRRT_kwDOQhJw3c6Xg0sj`) that had sat **unanswered** since 2026-08-08.

It is neither an error nor a fix: it is test output. `QueryGraph.render` defaults to
`filename="query_graph.pdf"` in the *working directory* (`query_graph.py:160`),
`test_rendering.py` exercises it, and the file is **both `.gitignore`d (`.gitignore:152`) and
tracked** — `.gitignore` has no effect on an already-tracked file, so any local suite run
dirties it and it gets swept into the next commit.

This session reproduced it without meaning to: the verification sweep dirtied
`query_graph.pdf` *and* `drawer_explanation.pdf` (`.gitignore:154`), which is how we know it
is at least two files rather than one.

**The thread was replied to and deliberately left open.** Its ask had two halves — revert, and
stop it being generated — and only the revert is in scope here; untracking generated PDFs is a
`main`-level change affecting every branch, and does not belong at the bottom of a seven-PR
stack. Per the standing rule, a half-answered ask is not resolved.

### Verification

`test_eql_rdr` 45/45, unchanged. Sweep over `test_eql` + `test_eql_rdr` against this branch's
previous head in the same container: **207 failed / 982 passed on both sides**, 214
failed+errored ids **byte-for-byte identical**, with 3 files excluded for the documented
`probabilistic_model…relational.rspn` gap.

Worth recording for the next session in a bare container: this one had **no dependency set at
all** and neither interpreter could import `numpy`. Installing the workspace requirements got
`test_eql_rdr` running, but the root `test/conftest.py` transitively needs
`giskardpy_bullet_bindings`, which is not installable from PyPI — so the sweep ran with
`--confcutdir=test/krrood_test`. §12's note stands and tightens: a local run here shows *no new
failures* and cannot show *no failures*, and it may not be able to load the root conftest at all.

### Closed (2026-08-09)

The developer marked #41 **ready for review** at 13:20Z, which under the standing convention
ends this session's job on it. CI green **20/20** on `efc8a0679`; `draft: false`,
`mergeable_state: clean`, 11 files / +1,946. Unsubscribed from #41 activity; no check-in armed
(the subscription notice asked for one — the personal notes forbid timed checks and override it).

One correction worth carrying: the `total_count: 0` reading taken minutes after the push was
simply *too early*, not another instance of §14's #98 CI-trigger problem. The run queued and
completed normally. §14's finding stands for #98 and should not be generalised from this.

Two threads stay open by design — the branch-semantics family (§16, the developer's to close)
and `query_graph.pdf` (half-answered: the revert landed, untracking the generated PDFs is a
`main`-level fix that was offered, not taken).

#41 is ready for the steward to merge as the stack bottom; the next pass should cascade it
through #63–#67/#98.

## 18. Addendum (2026-08-12) — `d-core-expert` (#98): the review round applied; three things it deliberately left

A `/plan-item-resolve` session picked up `d-core-expert`. §14 left it looking finished
apart from CI. It was not: a **review round on 2026-08-10 21:03–21:06Z had opened six
threads, none of them answered**, and the item's `notes` — which end at 2026-08-06 —
never recorded it. Same staleness class as §5's `rdr/why-answer` note and §14's own
`interface.py:127` finding, for the third time on this plan.

### What the six threads were, and what landed (`c4e297af`)

All six were on this PR's own test files, and three of them are one observation from
three angles: an assertion that restates something already guaranteed.

- `test_expert.py` — a stray `if __name__ == "__main__": unittest.main()` block had come
  to sit **mid-file**, with `TestInterfaceCarriesOnlyTheQuestionAndAnswerSurface` defined
  *after* it. The misplacement is what let the class land there. Both removed.
  The class's three tests asserted through `hasattr`, i.e. probing for the *absence* of
  members by name — the negative form of the reach-around AGENTS.md rules out for
  attribute access. Worth recording that this drops the only negative pin on the
  `ExpertInterface` segregation §11/§14 argued for; the positive coverage survives in
  `test_serialization.py`'s `ModelSaver` tests and `test_progress.py`'s
  `NullProgressReporter` lifecycle test.
- `test_progress.py` / `test_serialization.py` — `assert isinstance(NullX(), X)` against a
  base the class declares in its own `class` statement. Both removed, plus the
  now-unused `ModelSaver` import.

Two threads were **deliberately left unresolved**, per the standing rule that a thread
answered differently from its ask, or asking a question, is the developer's to close:

- The `pytest.raises(AttributeError)` ask was **superseded 39 seconds later** by the
  ask to delete the whole class it lived in. Taking the later one means the earlier one
  was not done as written, so it was replied to explaining the reading rather than
  silently dropped.
- "What is this class for?" on `_RecordingReporter` is a question. Answered — it captures
  `start()`'s arguments so one test can assert a `ProgressDescription` arrives as a plain
  string — together with the observation that this makes the *test* redundant too, since
  `test_fitting_description_is_the_label_shown_beside_the_bar` already asserts that
  equality directly and the rest is `StrEnum`'s own documented semantics. Offered, not
  applied.

### A vacuous assertion found next door, reported rather than folded in

`test_null_saver_writes_nothing_for_a_fitted_tree` asserts `list(tmp_path.iterdir()) == []`
while never handing `tmp_path` to `NullModelSaver`. Checked by mutation rather than by
reading, per §12/§15/§16: swapping in a `FileModelSaver` that genuinely writes a file
leaves the test **passing**. So it constrains nothing — the same defect class as §16's
`==`-on-symbolic-expressions finding, which is now the fourth instance of "the assertion
looked specific and was not." Raised on the PR; not changed, since it was outside the six
asks.

### Verification — and a container that finally had the dependencies

`test_eql_rdr`: **156 passed / 0 failed before, 151 passed / 0 failed after**, the
collected-id diff being exactly the five removed tests and nothing else.

This is worth flagging against §12's and §17's standing note. Those sessions ran in
containers missing the project's dependencies, so their sweeps could only show *no new
failures*. This container, once given a 3.12 venv plus `krrood`'s requirements, editable
`random_events`/`probabilistic_model`, and `casadi`, ran the suite **completely green** —
including the `probabilistic_model…relational.rspn` tests §9/§14/§17 all recorded as an
unfixable local gap, because the editable install has the submodule the PyPI release
lacks. The lesson tightens rather than reverses: the gap was always the *container*, not
the code, and a local sweep is worth setting up properly before concluding it cannot be.

`scripts/format_docstrings.py` again rewrote unrelated docstrings and the import block in
`test_serialization.py`, where the real change is two deletions; reverted there, kept in
the other two files where it was a no-op. Fourth recorded instance of the tool wanting its
own package-wide pass. No `:return:`-space regression this time.

### The CI trigger: the last untried remedy, also tried, also nothing

§14 called this "genuine, unsolved" and "not self-healing"; §17 correctly warned its own
too-early reading should not be generalised to #98. Both stand. Two things are now
established that were not:

- **It is not the workflow's triggers.** `ci.yml` on `main` is a bare `on: pull_request:`
  — no `branches` filter, no `paths` filter — so nothing about this branch excludes it.
- **It is not a real mergeability problem.** `D-core-support` `8eb7518a` is an ancestor of
  the head, so `refs/pull/98/merge` is a trivial fast-forward with zero conflicts. Yet
  GitHub reports `mergeable_state: unknown` on repeated reads.

So the merge ref looks wedged GitHub-side, which is why three — now four — pushes changed
nothing. **Closing and reopening #98 was tried this session** on that reasoning: it fires
a `reopened` event, which `ci.yml`'s default type set includes, and forces the ref to be
rebuilt. As of the end of the session it had **still queued nothing**; the branch's only
runs remain `a235d4bd` (green) and `b772e959` (the `coraplex` flake). The PR came back as
a draft, unchanged otherwise.

What is left to try is the steward's cascade retargeting #98's base — a base change is the
one remaining event class that recreates the merge ref. §11's request for a baseline before
`d-core-single-class` stacks ~3,500 lines on this branch is therefore **still unmet**, and
`open_ready` still cannot see it.

### §17's handoff to this item was never recorded on it

§17 and issue #94 comment `5230804492` both say, in terms: *"Carried forward for whoever
picks up `d-core-expert` and above: the `is UNSET` → `is ...` substitution, the
parameterizer probe, and …"*. That is recorded in this file and on the tracking issue, and
**nowhere in the item's own `notes`** — so a session reading the manifest, which is what
kickoff and resolve both do first, would not find it. Now recorded. The surface is ~20
sites (`conclusion_domain.py:22,160`, `expert.py:35,149,192`,
`interface.py:30,58,63,106,111`, `observer.py:24,137,238`, plus tests).

It is not merely pending, it is coupled to the cascade below: the substitution empties
`rdr/utils.py` of `UNSET`, leaving `AnswerName`/`NamespaceName` in a module whose filename
AGENTS.md names as a catch-all to avoid — and which `main` no longer has at all. The
circular-import argument that justified that file (thread `r3689176795`, resolved) assumed
it existed. Whoever does the substitution should expect to rehome those two enums in the
same breath, not treat it as a mechanical find-and-replace.

### #41 merged, so the cascade is due — and here is what it actually costs this branch

§17 signed off with "#41 is ready for the steward to merge … the next pass should cascade
it through #63–#67/#98." **#41 merged to `main` on 2026-08-10T13:32:02Z.** Measured with
`git merge-tree --write-tree`, and run against `D-core-support` as well so that conflicts
absorbed lower down are not misattributed here:

| file | conflict | whose |
|---|---|---|
| `rdr/utils.py` | modify/delete — deleted on `main` by #41's `efc8a0679`, modified here | **#98's** |
| `rdr/exceptions.py` | add/add | #67's, recurring at #98 |
| `rdr/condition_resolver.py` | content — §15/§16's `branch_semantics` vs this PR's `resolve(CaseContext)` | **#98's** |
| `test_condition_resolver.py` | content, same cause | **#98's** |
| `function_case.py`, `object_to_source.py`, `base_expressions.py`, `test_backward_inference.py` | content | absorbed at/below #67 |

§16 predicted `rdr/exceptions.py` would be "an additive merge, not a conflict." It is a
conflict: two files created independently on two branches share no merge base, so git
cannot auto-merge them however disjoint their contents.

### The dependency regression §14 recorded has not improved

`check_dependency_readiness.py --item d-core-expert` still reports `D-core-support` as
`open_ready` / `is_ready: true`, while live GitHub shows #67 `mergeable_state: dirty` with
a `needs-resolution` label, still at `8eb7518a` (2026-07-19) against a base that has since
moved to `526ed888`. #98 is unaffected — its own base is unchanged and it is a
fast-forward against it — but the stack cannot land, and neither the manifest nor the
dashboard can show it, because the readiness rule keys on open + non-draft only.

## 19. Addendum (2026-08-12) — `d-core-expert` (#98): `UNSET` → `...` landed, and `rdr/utils.py` is gone

§18 listed three things its round deliberately left. This round did the first, which turned
out to also settle a piece of the second.

### What landed (`acfc0ff4`)

The substitution itself was as mechanical as §17 predicted — both sentinels are singletons
compared with `is`, so every `is UNSET` / `is not UNSET` moved across unchanged, and `...`
is immutable so it is a legitimate dataclass field default. 20 sites across
`conclusion_domain.py`, `expert.py`, `interface.py`, `observer.py` and five test modules,
docstrings included.

Two docstring defects fixed in passing, both of the same kind — prose describing something
other than the value the field carries:

- `CaseContext.current_conclusion` read "``_UNSET`` if no rule fired", naming the *private
  class*. That name was never the value even before this change.
- `AnswerName.example_assignment`'s ``:return:`` used `...` as a **prose placeholder**
  ("a copy-pasteable example ``conditions = ...`` assignment"). Harmless while `...` meant
  nothing; once `...` is the sentinel it reads as a literal instruction to leave the
  conclusion undetermined. Reworded rather than left to be misread.

**Not renamed, deliberately:** `ConclusionDomain.validate(value, allow_unset)`, the
`ConclusionValidator.allow_unset` field, and the `test_unset_*` names. "Unset" there names
the *state* the expert left the conclusion in, not the identifier `UNSET`, and it stays
accurate. Flagged as a cheap follow-up rather than assumed either way.

### The rehome, and why one module

`rdr/utils.py` is **deleted**. With `UNSET` gone it held only `AnswerName` and
`NamespaceName` — a catch-all filename `AGENTS.md` rules out, on a path `main` no longer has
at all. Both enums moved to **`rdr/answer_vocabulary.py`**, checked free on `main` first.

They stay in **one** module, and the reason is load-bearing rather than stylistic:
`AnswerName.example_assignment` is built over `NamespaceName.CASE_VARIABLE`, and both must
sit below `interface.py` and `exceptions.py` so those two can share them without a circular
import. That constraint is the entire reason `utils.py` existed (thread `r3689176795`,
resolved), and it was carried into the new module's docstring rather than deleted with the
file — §12's lesson about a rationale surviving only on a branch marked for deletion,
applied prospectively for once.

### The cascade conflict is actually gone — measured, not assumed

§18 measured four conflicts against `main` that are #98's own. Re-measured with
`git merge-tree --write-tree origin/main <head>` on **both** heads in the same container:

| | `c4e297af` | `acfc0ff4` |
|---|---|---|
| `rdr/utils.py` | **CONFLICT (modify/delete)** | *gone* |
| `rdr/exceptions.py` | CONFLICT (add/add) | unchanged |
| `condition_resolver.py` | CONFLICT (content) | unchanged |
| `test_condition_resolver.py` | CONFLICT (content) | unchanged |
| `AGENTS.md`, `function_case.py`, `object_to_source.py`, `base_expressions.py`, `test_backward_inference.py` | CONFLICT (content) | unchanged |

Exactly one entry removed, none added — so the answer to §18's open question is yes, and it
cost nothing else. (`AGENTS.md` is new since §18's measurement; `main` moved to `e123c383`.
It is not this branch's, in the same sense the four lower ones are not.)

### Verification, in a container that again had everything

Rebuilt §18's environment (3.12 venv, `krrood`'s requirements, editable
`random_events`/`probabilistic_model`, `casadi`) and compared before/after in it:

- `test_eql_rdr`: **151 passed / 0 failed on both sides**, collected-test-id lists
  **byte-for-byte identical**. That is the right assertion for a behaviour-preserving change
  — the count alone would not have distinguished it from a rename that silently dropped a
  test.
- `test_eql`: **1058 passed, 3 skipped, 0 failed.** One module (`test_quantifier_overload_types.py`)
  is uncollectable for a missing `mypy`, which is this container, not the code.

Two things worth carrying: the `probabilistic_model…relational.rspn` gap §9/§14/§17 recorded
as unfixable stayed absent, confirming §18's finding that it was always the container; and
the `test_eql` sweep dirtied `query_graph.pdf` **and** `drawer_explanation.pdf` again —
§17's tracked-and-gitignored mechanism, reproduced a second time by accident, and reverted
before committing. It is still a `main`-level fix nobody has taken.

### A fifth formatter deviation, and a new failure mode

`scripts/format_docstrings.py` rewrote `ConclusionDomain.allows_none`'s docstring — a field
this change never touched — splitting ``an ``Optional`` / ``... | None`` annotation`` across
a blank line, i.e. **reading the ellipsis as a sentence end**. That is a new variant: §12's
and §16's instance was the ``:return: ``True``` space regression, §14's and §18's was bulk
rewrapping. This one produces genuinely broken RST. Reverted that hunk, kept the rest.
Sharpened point for the package-wide pass everyone keeps deferring: the tool now has a
specific quarrel with `...`, which this codebase has just made more common.

### The CI trigger: sixth push, still nothing

Checked immediately after pushing `acfc0ff4`, since it is the one thing nobody had done for
this particular push: `get_check_runs` returns **`total_count: 0`** and `mergeable_state`
still reads **`unknown`**. So the answer is plainly no — this push queued nothing either,
and §18's reasoning survives it intact: `ci.yml`'s trigger is unfiltered, the merge is a
trivial fast-forward, and the merge ref looks wedged GitHub-side. No spent remedy was
retried (no close/reopen, no repeat push).

What is different is that the remaining candidate is now *closer*, not just theoretical:
§18 named a **base change** as the one event class left that recreates the merge ref, and
this branch has just had its own share of the cascade conflicts reduced from four to three.
Whoever runs the steward pass gets to test that hypothesis for free.

### Left alone on purpose

The two review threads §18 left open (`pytest.raises(AttributeError)` on `test_expert.py`,
`_RecordingReporter` on `test_progress.py`) are still open and were not answered — both are
the developer's. `parameterizer.py:167`'s `InvalidEllipsis` probe and the
`single_class.classify -> Optional[Any]` signature remain with
`no-rule-fired-resolution` and `d-core-single-class` respectively.

`D-core-support` (#67) is unchanged since §14 and §18: `mergeable_state: dirty`,
`needs-resolution`, still `8eb7518a`. #98's own base is that same unmoved SHA, so #98 is
unaffected; the readiness rule still cannot see it.

### Follow-up the same day: both open threads closed, one of them by this session

The section above reported the two threads §18 left open as "still open and were not answered —
both are the developer's." That was already stale when written, and the failure is worth
recording because it is the *same* class this plan keeps catching, turned back on itself.

The developer resolved the `pytest.raises(AttributeError)` thread, and replied **"ok do the
recommended actions"** on the `_RecordingReporter` thread at **10:27:48Z** — after this session
read the threads and while it was still mid-round. Nothing re-read them before the round was
reported finished, so a thread that had become *this session's* to act on was reported back as
waiting on the developer.

Done as `e52d74b4`: `_RecordingReporter`, its one consumer
`test_description_is_usable_directly_as_the_start_label`, and the now-unused `ProgressReporter`
import are gone. The test asserted that a `StrEnum` member arrives at a callee as its plain
string — `StrEnum`'s own documented semantics, not this code's behaviour — while
`test_fitting_description_is_the_label_shown_beside_the_bar` already asserts that equality
directly. `test_progress.py` is left with the two assertions that constrain this PR's code.
`test_eql_rdr` **151 → 150 passed, 0 failed**, collected-id diff exactly the one removed test.
Replied on the thread naming the commit, then resolved it, in that order.

That makes **five** review-driven removals of this shape across the last two rounds — three in
`c4e297af`, two here — all of them assertions that restated something already guaranteed by a
declaration, a sibling test, or the language. Worth treating as a standing review lens for this
plan rather than a coincidence.

**The procedural lesson, stated so the next session inherits it:** §5, §14 and §18 each caught a
*note* that had gone stale between being written and being read. This is the same thing one level
up — the *live GitHub state* going stale between the gather step and the report step of a single
session. `/plan-item-resolve` gathers threads at step 2 and reports at the end; on a round that
takes hours, those are different worlds. Re-read the PR's threads immediately before reporting a
round finished, not only when starting it.

## 20. Addendum (2026-08-12) — `d-core-single-class` bootstrapped; the 2026-08-03 plan re-verified

`/plan-item-kickoff rdr-refactor d-core-single-class` ran a second time, nine days after §11's
planning session. Branch `D-core-single-class` is cut from `origin/D-core-expert` and draft
**PR #159** is open; the port itself runs in a fresh session, as §11's did not.

### Why a re-plan rather than picking up the saved one

§11's plan was saved to `pr-progress/D-core-single-class.md` and never executed. Five of its
premises had since changed, each verified live rather than assumed:

| §11 said | now |
|---|---|
| Four items **handed to #98**, unimplemented — check before starting | **All four landed** (§14, `28a89ff4`): `ConditionResolver.resolve(CaseContext)`, `ExpertInterface` segregated, `NullProgressReporter`, `ProgressDescription` |
| `classify()` returns `UNSET` | Sentinel is **`...`** (§17, §19); `rdr/utils.py` deleted, enums rehomed to `answer_vocabulary.py` |
| Save via `save_path` + `expert.interface.on_save` | RDR holds a **`ModelSaver`** and a **`ProgressReporter`** as its own collaborators |
| `prior_errors={"conditions": e.message}` | `prior_errors: Optional[List[DataclassException]]` — pass `[e]` |
| Get a CI baseline on #98 | **Six pushes, zero runs queued** (§14, §18, §19). The baseline has to be local |

Two consequences follow that no review thread decided, so they are recorded as this session's
assumptions rather than as settled:

- **`RDRDidNotConvergeError` carries no save path.** §11 had it carry "clashing cases, pass count
  and save path", but `save_path` is gone and `ModelSaver` exposes no destination. It carries the
  clashing cases and the pass count; the engine calls `model_saver.save(self)` before raising.
- **`classify()`'s signature defect lands here.** §19 handed `single_class.classify ->
  Optional[Any]` — annotated *"or `None` if no rule fires"* while returning the sentinel — to this
  item. It is fixed as part of the port rather than as a separate change.

### The scope check, run rather than assumed

Per the standing new-PR-versus-change-in-flight rule: `git ls-tree origin/D-core-expert` for
`single_class.py` and all six test files returns **empty** — none exists on the base. This is the
pre-agreed §6 three-way split, 554 lines of engine and ~3,500 of tests that stand on their own.
Real stacking, not a fold into #98.

### The branch name, and why not the session's own

`plan.yaml`, every sibling in the stack, and the saved progress note's own filename all say
`D-core-single-class`. The harness designated `claude/rdr-refactor-d-core-single-class-jld9ol`,
which stays unused — §15's precedent, confirmed with the developer before pushing rather than
assumed from it.

### A defect in the plan tooling, found by using it

`.claude/hooks/plan_item_bootstrap.py`'s `open` could not record this item: it patches the
manifest by line, and writes the fields it changes (`branch`, `pull_request_number`, `status`,
`session`) at **four-space** indentation inside an item whose other fields sit at two, producing
YAML that no longer parses. `save-plan.sh` then fails inside `plan_manifest_tools.py`'s
`yaml.safe_load`.

Two things make it worse than a formatting slip. The subprocess call uses
`capture_output=True`, so `save-plan.sh`'s traceback is swallowed and the caller sees only a bare
`CalledProcessError`; and the script still prints `{"status": "success", "exit_code": 0}` on the
path where the save was stubbed out, so its own report is not evidence the write landed.

Worked around by patching `plan.yaml` by hand at the correct indentation and calling
`save-plan.sh --manifest --roadmap` directly, per the standing "prefer editing the manifest
directly and saying so over leaving it stale" rule. **The tooling defect is not fixed here** — it
belongs to whichever plan owns `.claude/` tooling, not to this stack.

### Also

- Subscribing to tracking issue #94 was refused by the permission classifier, exactly as it
  refused §11's session and §16's attempt on #41. Third recorded instance; the mechanism the
  kickoff skill relies on for concurrent-change awareness does not work in these containers.
- The stack is unchanged and still stale: `D-core-support` `8eb7518a` (2026-07-19), `main`
  `be377fdf`. §11's call stands — the cascade is not a prerequisite for working this item.

## 21. Addendum (2026-08-12) — the steward cascade ran: the stack is unblocked, and #98's CI is unwedged

The cascade §17 asked for and §18/§19/§20 kept deferring to ran end to end. Every branch from
`D-core-aid` to `D-core-single-class` now carries `main` `be377fdf` (#41 merged 2026-08-10):

| PR | branch | was | now |
|---|---|---|---|
| #63 | `D-core-aid` | `b241c4ed`, `needs-resolution` | `4e0c2715`, label cleared |
| #64 | `D-core-underspecified` | `3fda9a99` | `1ad96142` |
| #65 | `D-core-corner-case` | `2664cae5` | `07545624` |
| #66 | `D-core-serialization` | `08f2fbdd` | `bd925f70` |
| #67 | `D-core-support` | `8eb7518a` (2026-07-19), **dirty**, `needs-resolution` | `4d98d0fb`, **unstable**, label cleared |
| #98 | `D-core-expert` | `e52d74b4` | `82eb69fb` |
| #159 | `D-core-single-class` | `d5b94c5a` | `621bde53`, **clean** |

Nothing in the stack reads `dirty` any more. `#67` had been frozen in that state since §14
(2026-08-06) and was the reason the stack could not land.

### The conflicts, and why three of them were not a choice of sides

Seven hops, five of them conflicting. The instructive ones all have the same shape — **this
stack's own work meeting a rename `main` made under review** — so the resolution is neither
side wholesale but this stack's structure on `main`'s live API:

- **`base_expressions.py` (at #67).** `main` renamed `ActiveConditionsRoot.claim()` to
  `set_active_root_if_not_set(root, has_condition)` (`82859a81`, a review asking to *"drop the
  claim wording"*), and #67 had separately hoisted that call **out** of the
  `owns_an_evaluation_context` branch so it also runs under a pre-installed context — its own
  `fa42d2a9`, one of the two core-EQL bugs #67 exists to fix. Taking `main`'s side wholesale
  re-nests the call and **fails `test_conclusions_fire_with_a_pre_installed_evaluation_context`**;
  verified by mutation, not by reading, per §12/§15/§16/§18. Kept `main`'s API at #67's placement.
- **`base_expressions.py`, second hunk.** #67 gated conclusions on
  `current_result.is_condition_false`; #99's truth unification (`465dd92c`) deleted that accessor.
  The gate is now `if not is_active_root`, with truth consulted below via `current_result.is_true`.
  This is the one plan.yaml predicted in 2026-07-31's note (3) and it landed exactly as predicted.
- **`condition_resolver.py` / `test_condition_resolver.py` (at #98).** Kept #98's `CaseContext`
  parameter object, on `main`'s names: `ConclusionKnowledge` → `ConclusionSufficientConditionSets`,
  the module-level `_materialize` helper → the `GuardCondition.as_expression` property, and
  `TargetKnowledgeResolver` → `TargetSufficientConditionsBasedResolver`. That last one was checked
  before being applied rather than assumed: `8eb7518a` already carried `TargetKnowledgeResolver`,
  so it is the **inherited** name and `main` renamed it in `ed7b3766` (*"Tom and Luca Comments"*).
  #98 never chose it, so nothing of #98's was overridden.
- **`rdr/exceptions.py`.** §16 predicted an additive merge, §18 corrected that to a conflict, and
  it conflicted at **three** separate hops (#64, #65, #98) — two independently created files share
  no merge base however disjoint their contents. Unioned each time; no class name ever collided.
  Section headers rewritten to the groups the merged file actually has.

### The silent deletion, which git cannot flag and which is now on record twice

`main` deleted `rdr/utils.py` in #41's `efc8a0679`, with the commit message reasoning that
*"`rdr/utils.py` defined the `UNSET` sentinel but nothing on this branch imported it"*. True of
`main`; **false of `D-core-support`**, which imports `UNSET` from it in `observer.py` and
`interface.py`. Because #67 never modified that file, git took the delete as a clean merge — no
modify/delete conflict, no warning — and the breakage surfaced only as an `ImportError` at test
collection. Exactly §9's `template_file_creator.py` mechanism, second recorded instance: **a file
neither side's diff touches is where a merge is silent and wrong.** Worth treating as a standing
post-cascade check (import the package, don't just count conflicts) rather than a coincidence.

Resolved by doing the `UNSET` → `...` substitution on #67 that §19 had already done on #98 —
forced rather than chosen, since the module is gone from the base, and restoring it would both
re-create the modify/delete conflict §19 was pleased to eliminate and reinstate a filename
`AGENTS.md` rules out. `test_serialization.py` also follows `main`'s rename of
`what_do_we_know_about` to `get_conclusion_sufficient_conditions_from_a_rule_tree`.

### The CI hypothesis: answered, and §18 had it slightly wrong

§18 named a **base change** as the one remaining event class that recreates #98's wedged merge
ref, and §19 handed the steward a free test of it. The measurement, with times:

| | |
|---|---|
| 20:26:39Z | `D-core-support` pushed — **#98's base moves** |
| 20:26:45Z | `get_check_runs` on #98 → `total_count: 0` |
| 20:27:19Z | #67's *own* runs start (its head moved, ordinary `synchronize`) |
| 20:34:41Z | `D-core-expert` pushed — #98's head moves |
| 20:34:47Z | #98's first workflow run is created; 21 jobs follow |

So the base change **alone did not do it**: the workflow-run list itself contains no run created
in the eight minutes between the base moving and the head being pushed, which is stronger evidence
than the single sample at 20:26:45. What unwedged it was *a push after the base had moved* — and
the six earlier pushes (§14, §18, §19) all landed while the base was frozen at `8eb7518a` and
queued nothing. The base move is the necessary ingredient; the push is the trigger. §18's
hypothesis is upheld in substance and corrected in mechanism.

**#98 has CI for the first time since `b772e959` (2026-07-30)** — 21 jobs, the full `test_each_lib`
matrix, with `test_claude_dev_tooling` already green. §11's request for a baseline before
`d-core-single-class` stacks ~3,500 lines on this branch is finally met by something other than a
local sweep.

The one failure seen anywhere in the pass is `test_each_lib (random_events)` on #67, and it is
`503 Service Unavailable` fetching `bazel.sh` — infrastructure, not code. The branch's
`random_events/` tree is byte-identical to `main`'s, checked rather than assumed.

### The readiness rule: decided, and deliberately not changed

`check_dependency_readiness.py` reported #67 as `open_ready` / `is_ready: true` throughout the six
days it was unmergeable, because `Item.is_ready_to_unblock_dependents()` is
`is_effectively_done() or live_state is OPEN_READY` — open plus non-draft. §18 asked whether it
should also consider `mergeable_state`. **It should not**, and the reason is that the two answer
different questions:

- The rule's own docstring scopes it to *"whether a dependent item can safely start stacking its
  own branch on this one"*. #67 was unmergeable **against its own base**; #98 was a clean
  fast-forward on #67. Stacking on it was never unsafe — which is why §11 and §20 both explicitly
  decided the cascade was not a prerequisite for working `d-core-single-class`, and they were right.
- Folding `mergeable_state` in would have made the dashboard tell those sessions *not to start*,
  contradicting a call this plan twice made correctly. That is a false negative bought for a
  visibility problem.

What was actually missing is visibility of *"this item cannot land"*, and that is **already built
and in flight**: `workflow-unification`'s `shared-pr-state-chips` (#111) adds a `mergeable` probe
to `development_tooling/pr_state.py` and renders a per-item `mergeable`/`conflicts` chip in
`build_dashboard.py`. So no new item is warranted — per the standing rule preferring a change to an
unlanded PR over a new one. Recorded on issue #102 rather than acted on here.

### Carried forward

- **`main`'s two unfinished renames — fixed the next day as draft PR #161** (`bug`). Reported here
  first as `main`'s and out of this pass's scope; the developer asked for them fixed. There were
  **five** stale readers, not the four this section first counted — `test_condition_resolver.py:5`
  on `main` was stale too. `AGENTS.md`'s own rule is the one that was being broken: a rename is
  finished only when every reader of the old name reads the new one, docstrings included.
  Two calls worth carrying: the test is renamed for its *behaviour*
  (`test_backward_inference_resolves_conditions_root_from_any_tree_node`) rather than for the
  function it calls, since naming it after the identifier is what let it go stale; and `knowledge`
  is left alone throughout, because it is still live vocabulary (`target_knowledge`,
  `current_knowledge`, "backward-inference knowledge") and only the class and the function moved.
  Folding it into the stack's base PR #63 was considered and rejected on the mechanical test —
  `git ls-tree main` on the three paths is non-empty, so it is not a change to unlanded work, and
  #41, which introduced them, has merged. It is conflict-free against all four stack branches
  (measured), because the one docstring this pass had already fixed on `D-core-expert` during the
  cascade was re-wrapped on `main` to match the spelling the stack carries — otherwise the cascade
  would have had to resolve the same fix twice, spelled two ways.
- **`black` is not clean on this stack, and was not before this pass**: `backward_inference.py`,
  `test_backward_inference.py` (both already unformatted on `main`) and `serialization.py` (which
  this pass never touched). Left alone rather than swept in. Sixth entry in the running case for the
  package-wide formatter pass everyone keeps deferring; `format_docstrings.py` also again produced
  unrelated docstring rewrapping, reverted, with only `black`'s own output kept.
- **#98 is no longer a draft.** It was one at the end of §19, so the developer marked it ready
  themselves. This pass pushed the cascade merge to it anyway, because a steward cascade that stops
  below `D-core-expert` leaves #159 stranded — but it was **not** re-drafted, per the standing rule
  that a pull request the developer marked ready is theirs.

## 22. Addendum (2026-08-13) — `d-core-single-class` (#159): the engine landed, and what the port found

The port §20 bootstrapped ran. `single_class.py`, three new exceptions and six engine test files are
pushed as `04dc904c`; #159's body is rewritten and it stays a draft. Every #68 thread §20 listed is
applied. What follows is only the parts the plan did not already decide.

### The baseline expectation in the saved plan was stale, and the note said so twice

§20's *"Next"* step 1 said to expect `test_eql_rdr` **150 passed**. The measured baseline on
`D-core-expert` `82eb69fb` is **164 passed / 0 failed**. 150 was `e52d74b4`, and §21's cascade then
merged `D-core-support` into that branch, contributing its 14. §21 *already records 164* — the
progress note was simply written before it and never reconciled.

This is the same staleness class §5, §14, §18 and §19's own follow-up each caught, with a new
wrinkle: here the two records disagreed and **the roadmap was the correct one**. A session following
the progress note's number alone would have opened by "investigating" 14 phantom tests. Worth the
standing habit: when a saved plan states a measured number, re-derive it rather than trusting it,
and check the roadmap for a later measurement of the same thing.

Recorded properly this time: 164 ids across 15 files, saved as a sorted list and diffed rather than
counted. This branch is **230 passed / 0 failed** — 66 added, **zero baseline ids lost** — and
`test_eql` is **1180 passed / 3 skipped / 0 failed**.

One mechanical detail worth carrying, since it cost a wasted run: `--collect-only` prints nothing in
`::` form unless `-o addopts=` clears the repo-root `pytest.ini`'s `-sv`.

### The retry loop the plan said to consider deleting is reachable

§20's engine list ended with *"probe whether the `SelfReferentialInsertionError` retry loop is
reachable (HINT-mode test). If it cannot be provoked, delete it."* It **can** be provoked, and by
something an ordinary expert could do rather than a contrived one: answering with
`context.trace.firing_anchor`, which `conclusion_selector.py:121` rejects because splicing a node
beneath itself would close a cycle in the DAG. The probe reaches it through `fit_case` in five lines.

So the loop is **kept**, not deleted, and pinned by two tests: HINT re-asks, AUTOMATIC surfaces.
Worth noting the shape of the near-miss — the plan's instinct was that this was dead code, and one
run of the probe was the difference between keeping a live recovery path and removing it.

### The probe found a live defect next door, fixed on this side rather than upstream

Passing the raw `SelfReferentialInsertionError` into `ask_for_conditions(prior_errors=[…])` crashes:
`ExpertInterface._render_header` does `error.answer_name` for every entry of `initial_errors`, and an
EQL-core exception has no such field. So the re-prompt — the entire point of the retry loop — raised
`AttributeError` instead of re-asking.

Fixed **here**, not in `interface.py`, and the reason is a contract rather than a preference:
`initial_errors` is documented as errors that each name their own request, and `_validate` builds
exactly that shape. Passing one that does not was the caller's bug. `_insert_rule` now raises
`ConditionsNotInsertable`, carrying `answer_name=AnswerName.CONDITIONS` and the offending anchor,
chained from the original with `raise … from`.

This is the third defect on this plan found by *exercising* a path rather than reading it (§16's
`==`-on-symbolic-expressions, §12's `holds_for` reachability probe, now this). None was visible in
the diff.

### The mutation lens caught a vacuous assertion of this session's own

Seven mutants; six died immediately at exactly the tests that name their behaviour. The
**pre-raise-save mutant survived**: deleting `model_saver.save(self)` before
`raise RDRDidNotConvergeError` changed nothing, because `_splice_rule` already saves on every
insertion, so `assert rdr in saver.saved` was true no matter what the giving-up path did.

That is the **fourth** instance on this plan of an assertion that looked specific and was not (§16's
nine `==` comparisons, §18's `test_null_saver_writes_nothing_for_a_fitted_tree`, §19's tally of five
review-driven removals, now this). The lesson is sharper than "write specific assertions": this one
*was* specific — it named the exact object and the exact collection — and was still vacuous, because
a **different** code path already established the fact it asserted. Membership tests are especially
exposed to this. Rewritten to compare the save count against the number of rules inserted, which
kills the mutant.

Also worth recording as method: running the mutants was ~6 minutes of wall clock and found a defect
in the test suite that reading it twice had not. It is cheap enough to be the default, not the
exception.

### Two API-shape questions deliberately left open on the PR

Neither is a defect; both are places where the honest answer is the developer's:

- **The retry's gate.** The mega-branch keyed it on `resolution_mode`, which conflates *"was this
  auto-resolved"* with *"is anyone watching to answer differently"*. With **no resolver set at all**,
  the expert authored the condition and still gets no second chance in AUTOMATIC mode. The gate
  arguably belongs on "did we ask the expert for this condition". Kept the mega-branch's behaviour
  rather than widening the port's scope.
- **`CaseContext.conclusion_domain` is now always populated.** Building the context **once** — which
  §20 required — means the domain is present on the conditions-only path too, contradicting the field
  docstring on #98's `interface.py` that says it is `None` there. Harmless at runtime; the docstring
  is now inaccurate, and correcting it means touching #98's file.

### Two ported files shrank a lot, and that is the port working

`test_condition_resolver_integration.py` and `test_backward_inference_integration.py` are much
smaller than their mega-branch originals, because #98 and #67 had since landed the unit coverage they
duplicated: `test_condition_resolver.py`'s 16 tests and `test_backward_inference.py`'s 18. What was
dropped is precisely the shape §18/§19 removed five times under review — `frozen`/equality tests that
restate a `@dataclass(frozen=True)` declaration, and ABC-instantiation tests that restate the
language. What was kept is what only the live engine can show.

Recorded on the PR too, so a reviewer does not read the line count as a dropped port. The general
point for the remaining slices: a mega-branch file is a *starting* point, and the right first
question is which of its assertions a sibling PR has since made redundant.

### Small things

- The RDR's backward-inference method is `sufficient_conditions_for`, not the mega-branch's
  `what_do_we_know_about`. Not a rename — the method is new here — just not reintroducing the name
  `main` retired in §21/#161.
- `fit(cases, [...] * n)` stays single-pass: the convergence recompute skips cases whose target is
  the sentinel, since a case with no ground truth has nothing to converge against.
- `format_docstrings.py` again rewrapped unrelated field spacing, this time in `animal.py` — the
  **sixth** recorded instance. Reverted there; kept in the files this PR writes whole, the same call
  §14/§18/§19 made. No `...`-as-sentence-end regression this round.
- CI queued on the push, as §21's finding predicts now that the base has moved.

## 23. Addendum (2026-08-22) — `D-core-aid` (#63): the review round applied, and a rename that was counted twice and still undercounted

A `/plan-item-resolve` session picked up `D-core-aid`. Nothing mechanical was wrong with
it — CI 22/22 green on `208ca491`, `mergeable_state: clean` against current `main`,
`check_dependency_readiness.py` reporting `rdr-backward-inference` as `merged` /
`is_ready: true`, and no recorded `blockers`. What stalled it was **a review round opened
2026-08-21T15:36–15:37Z, four threads, none answered**, which the item's `notes` — ending
at §21's cascade — never recorded. Fifth instance of that staleness class on this plan
(§5, §14, §18, §19).

### #161 said "five readers". The real number was fourteen, across four renames

§21 recorded `main`'s two unfinished renames and #161 fixed them. Three of the four new
threads say #161 stopped too early, and checking rather than trusting its count showed
they are right: #41's cascade landed **four** renames on `main`, not two, and #161's table
covers only the first pair.

| rename | stale readers left on `main` | in #161's original scope |
|---|---|---|
| `ConclusionKnowledge` → `ConclusionSufficientConditionSets` | 3 | yes |
| `what_do_we_know_about` → `get_conclusion_sufficient_conditions_from_a_rule_tree` | 2 | yes |
| `TargetKnowledgeResolver` → `TargetSufficientConditionsBasedResolver` | 6 | **no** |
| `_materialize` → `GuardCondition.as_expression` | 3 | **no** |

**Two of the missed readers are in production source** — `condition_resolver.py:11`
(the module docstring's list of built-in strategies) and `:230`
(`backward_inference_default`'s docstring) — and that is the generalisable part. #63's diff
does not contain `condition_resolver.py` at all, so no amount of care reviewing #63 could
have surfaced them, and #161 was written from a diff rather than from a grep of `main`.
The lesson is narrow and cheap: **finish a rename by grepping the whole tree for the old
identifier, not by re-reading the diff that renamed it.** §21 already stated the rule
(`AGENTS.md`: every reader, docstrings included) and still undercounted, twice.

### Where the fix went, and why not where it was asked for

The threads asked for it on #63. It went on #161, by the mechanical test the standing
convention requires: `git ls-tree main --` on both paths is non-empty, so this is not a
change to what an unlanded PR introduces — the same test #161's own body had already run
and used to reject folding into #63. Three further reasons, in descending weight:

1. #63 could only ever have fixed **half** of it, since the source-side readers are in a
   file it does not touch.
2. Both PRs editing `test_condition_resolver.py` breaks #161's measured
   conflict-free-against-the-stack property and makes the developer review one rename twice.
3. `main` is the branch that is *behind* here. `D-core-expert` already carries these exact
   `# %%` headers with the corrected names, applied during §21's cascade — so this is
   `main` catching up to the stack, which is a `main`-based PR's job.

The three threads are replied to and **left open**, per the standing rule that a thread
answered differently from its ask is the developer's to close.

### What each PR now is

| PR | before | after |
|---|---|---|
| #63 `D-core-aid` | 4 files: `aid.py`, `test_aid.py`, `test_condition_resolver.py`, `test_rdr_alchemy.py` | **`aid.py` alone**, 49 lines |
| #161 | 3 files, 2 renames, "five readers" | 4 files, **4 renames**, retitled |
| #189 (new, `bug`, draft) | — | the `test_rdr_alchemy.py` flaky skip, off `main` |

`test_aid.py` was deleted, doing the fourth thread exactly as asked. All three tests
restated a declaration or the language — `present`/`suggest` returning `None` *is* the class
body; the other two exercise Python's method overriding. Checked before deleting that
nothing is lost: #159's `test_ask_for_rule.py` already drives `suggest()` through the live
engine with three `ConclusionAid` subclasses including the domain-validation path. Sixth
instance of this plan's standing review lens (§18 ×3, §19 ×2, §22's ported-test shrink).
The `AGENTS.md` tension is real and was stated on the thread rather than glossed: an aid's
only behaviour is *being consulted*, so its tests belong with its consumer.

### The flaky skip: moved, and then not reproducible

`cdb19274` had been carrying an `@unittest.skip` for `test_fit_mcrdr_stop_only` at the
bottom of a seven-PR stack since 2026-07-12. It is not a fresh quarantine — `main` already
skips the identically-named sibling in `test_rdr.py` with a byte-identical reason
(`57a1babac`) — but it is a `main`-level fix, so it moved to #189.

Then it would not reproduce: **18 passes out of 18**, across the test alone (6), its class
(5), the whole `test_ripple_down_rules` suite serially (3), and that suite under `-n auto`
as CI runs it (4). The only failures anywhere were `test_object_diagram.py`'s two from a
missing `dot` binary, §9's known local gap.

Eighteen passes is weak evidence of absence for something described as occasional, so the
skip is carried forward on #189 as *the decision already made on `main`* rather than as
something re-established — and the PR body puts the real question (is either sibling skip
still needed?) to the developer with three named options instead of guessing. This is the
counterpart to §22's "probably dead code was alive": there a probe rescued a live path,
here a probe found a suppression that may no longer be earning its keep. Both times the run,
not the reading, was the evidence.

### A generated file `AGENTS.md` protects nearly rode into a commit

`git add -u` after a verification sweep staged **4,329 lines** of regenerated
`test/krrood_test/dataset/ormatic_interface.py`, plus an unrelated
`verbalization_results.py` diff. Caught before pushing and reverted; the commit was
rebuilt from an explicit path list.

Worth recording because the existing protection does not cover this path: `AGENTS.md` says
`scripts/regenerate_all_orm.py` sets git's skip-worktree bit so a locally regenerated copy
is never proposed for staging — but here it is `conftest.py` regenerating the file at *test*
time, which that bit was never applied to. Same mechanism as §17/§19's `query_graph.pdf` and
`drawer_explanation.pdf` (tracked *and* gitignored, dirtied by any sweep), third recorded
instance, on the one file `AGENTS.md` names explicitly. **Standing habit for this plan:
after any verification sweep, stage by explicit path, never `git add -u`.**

### Conflicts, measured before and after

`git merge-tree --write-tree` from #161 against the four stack branches:

| branch | before this round | after |
|---|---|---|
| `D-core-aid` | clean | **clean** |
| `D-core-support` | `ormatic_interface.py` | + `test_condition_resolver.py`, 2 hunks |
| `D-core-expert` | `ormatic_interface.py` | + `test_condition_resolver.py`, 1 hunk |
| `D-core-single-class` | `ormatic_interface.py` | + `test_condition_resolver.py`, 1 hunk |

`condition_resolver.py` is clean **by construction**: its two docstrings are wrapped to
match the spelling `D-core-expert` already carries, so the stack does not resolve the same
fix twice. Wrapping them the way the change first read conflicted on all three upper
branches — measured, then fixed, not assumed. The remaining hunks are add/add against #98's
`_context(…)` helper, resolved by keeping #98's side; nothing this round changes sits
opposite them. `D-core-aid` is clean precisely because #63 now stops touching the file.

### Also

- **`scripts/format_docstrings.py` deviated a seventh time.** On a change of six docstring
  lines and three test names it reindented every function signature in
  `condition_resolver.py`, split its import block and rewrapped unrelated docstrings.
  Reverted whole; same call as §12/§14/§16/§18/§19/§22.
- **#161 has one red check**, `test_each_lib (semantic_digital_twin)` on run `32138139279`,
  in a package it does not touch, while #63's run the same day was 22/22 green including
  that job. Flagged, not chased.
- **Subscribing to #94 was refused by the permission classifier again** — fourth recorded
  instance (§11, §16, §20). The mechanism the plan skills rely on for concurrent-change
  awareness still does not work in these containers.
- **#63 was not re-drafted** after pushing, per §21's rule for a pull request the developer
  marked ready.
- `backward_inference.py` on `main` carries bare `# %%` headers with no description, which
  `AGENTS.md`'s rule asks for. Noted, not fixed — `main`'s, and outside this round.

## 24. Addendum (2026-08-22) — the follow-up review reversed §23's split, and caught that two pull requests existed in no plan at all

§23 moved `test_condition_resolver.py`'s cleanup off #63 and onto #161, by the mechanical
`git ls-tree main` test. The developer reviewed that and reversed it — *"do it here, and I
am wondering why isn't #161 existing in any plan? fix that."* Both halves are worth
recording, because only one of them is a matter of taste.

### The split was defensible and still wrong for this file

The reasoning in §23 holds on its own terms: the file exists on `main`, two of the stale
readers are in production source `#63` does not touch, and `D-core-expert` already carried
the corrected headers. What it undervalued is that **a reviewer reads a diff, not a
rationale.** `df20e7d9` showed `# %%` → `# ---` on a file the reviewer had just asked to fix,
and no amount of correctness in the commit message changes what that looks like. The
mechanical test answers "may this ride here?"; it does not answer "will the person reviewing
it understand why it did not."

Settled: **`test_condition_resolver.py` is #63's, whole** — dividers, corrected header names,
the three `test_target_knowledge_resolver_*` names, the module docstring and the
`materialized_guard` wording. #161 keeps only what #63 does not touch: `backward_inference.py`'s
and `condition_resolver.py`'s docstrings, and `test_backward_inference.py`'s test name.

The property worth keeping from §23 survives the reversal, because it was about files rather
than about which PR: **no file is touched by both**, so neither can conflict with the other.
Verified with `git merge-tree`, not assumed — #161 merges into `D-core-aid` clean.

### The real finding: neither #161 nor #189 was in any plan

The developer's second question is the one with teeth. #161 was opened 2026-08-13 by §21's
own steward pass and #189 this morning by §23, and **neither was ever added to `plan.yaml`** —
so neither appeared on any dashboard, in any readiness check, or in any kickoff/resolve
session's view of this programme. Both are now items on the `S0-steward` track, with #89
(`conditions-root-drop-dead-parent-recovery`) as the precedent: a main-based side-quest fix
tracked alongside the stack it serves.

The gap has a specific shape worth naming, because it will recur. Every plan-* skill records
state for *the item it was invoked on*. A session that spins off a **new** pull request while
resolving an existing item has no step that says "and track the thing you just created" —
§23 wrote a roadmap section and a tracking-issue comment describing #189, updated `D-core-aid`'s
notes, republished the dashboard, and still left #189 itself invisible to every one of those
mechanisms. Writing *about* a pull request in the roadmap is not the same as it having an
`items[]` entry, and only the second is what the tooling reads.

Two habits follow: a session that opens a pull request adds its item in the same turn, and
`/plan-item-resolve`'s state-recording step covers every pull request the round touched,
not only the one named in its invocation.

### Also

- **CI was red on `test_each_lib (semantic_digital_twin)`** for `test_multi_sim.py::
  test_world_sim_state_sync` — a physics-settling assertion #63's 49 lines of `krrood` cannot
  reach. Cause: the branch was **10 commits behind `main`** and predated `a7c21ffe6`
  ("[FlakySync] add flaky to test_world_sim_state_sync"). Merged current `main` into both #63
  and #161.
- **That flaky marker looks inert, and it is worth checking before relying on it.**
  `@pytest.mark.flaky` appears exactly once in the repository, is not registered in
  `pytest.ini`'s `markers`, no rerun plugin is declared in any requirements file, and
  `ci_reusable.yml` runs a bare `python -m pytest -n auto` with no `--reruns`. Under either
  `pytest-rerunfailures` or `flaky`, a bare marker with no reruns configured does nothing but
  emit an unknown-mark warning. So the merge brings #63 up to date — which it needed anyway —
  but it cannot be claimed to *fix* that failure. This also bears on #189, which uses
  `@unittest.skip`: the newer marker would keep coverage instead of disabling it, but only
  once it actually reruns.
- **A third generated file dirtied a commit's staging area.** After §23's `ormatic_interface.py`
  (4,329 lines) and §17/§19's `query_graph.pdf` / `drawer_explanation.pdf`, this round's suite
  runs regenerated `test_eql/test_verbalization/verbalization_results.py` — an auto-generated
  snapshot module whose own header says not to hand-edit it. A stop-hook prompt to "commit
  uncommitted changes" would have put it into #63, re-widening the very PR this round narrowed.
  Reverted, not committed. The habit §23 recorded — stage by explicit path, never `git add -u`
  — now has a third instance behind it, and a corollary: **a dirty working tree after a test
  sweep is the normal state here, not a signal to commit.**

## 25. Addendum (2026-08-22) — the flaky marker was inert, and fixing it corrected my own diagnosis twice

§24 flagged `@pytest.mark.flaky` as probably doing nothing. Asked to fix it, the probe
confirmed the defect and **corrected the stated reasoning twice** — worth recording, because
both corrections came from running the thing rather than reading it.

**The defect is real and smaller than described.** `pytest-rerunfailures` is in no requirements
file and not in the `dev` extra CI installs via `uv sync --extra dev`, so pytest treats the mark
as unknown and runs the test exactly once. That is how #63 went red on a 49-line `krrood` diff.
One line in `pyproject.toml` fixes it; PR **#190** (`bug`, draft).

**First correction: §24 said a bare mark also needs `--reruns` configured.** It does not. On the
pinned pytest 7.4.4:

| configuration | result |
|---|---|
| plugin installed, bare `@pytest.mark.flaky` | 1 passed, **1 rerun** |
| plugin absent, identical mark | 1 failed + unknown-mark warning |

A bare mark reruns once on its own, and the plugin registers the mark itself — so neither a
rerun count, nor `--reruns`, nor a `pytest.ini` `markers` entry was ever missing. Only the
dependency.

**Second correction, inside the fix.** The first guard test asserted the *rerun behaviour*, by
failing on the first attempt and passing on the second through a session-scoped counter. It
passed on plugin 16.1 and **failed on 10.3 — with the rerun happening in both.** Older versions
tear the session fixture down between attempts, so the test was really asserting the plugin's
fixture-teardown semantics, not this repository's property. Trimmed to assert only that the
plugin is loaded, which is the invariant this repo owns and exactly what regressed; what the
mark does once loaded is the plugin's own contract. The trimmed test passes with the plugin and
fails without it on both versions.

The general lesson, and it is the same one §22 recorded for the retry loop: a test whose
mechanism depends on a third party's internals looks like coverage and is really a version
probe. Ask what property *this* repository owns before asserting.

Also: this item was added to `plan.yaml` in the same turn as opening #190 — the habit §24
recorded after the developer caught #161 and #189 existing in no plan at all.

**Verified against upstream, after the developer asked whether it had been.** It had not — a
real gap, since a fix already present upstream would make #190 a duplicate that conflicts on
the next sync. Checked: upstream `cram2`'s `main` is at **the same commit** as this fork's
(`3f643cffb`), its `dev` extra is byte-identical with no `pytest-rerunfailures`, no rerun
plugin appears in any of its requirements/`pyproject.toml`/`.cfg`/`.ini`/workflow files, and
the mark at `test_multi_sim.py:759`, `pytest.ini` and the CI invocation are all identical
there. So the defect is upstream's own and #190 belongs promoted upstream.

Worth keeping as a habit: a dependency or configuration fix on a fork needs the upstream check
before it is opened, not after. The strongest evidence here was empirical and already on the
record — the marked test failed CI on a pull request that could not have affected it — but
nothing had confirmed the *fix* was not already sitting upstream.

## 26. Addendum (2026-08-22) — the "flaky" MCRDR test is not flaky; the bug was fixed five days after the skip

§23 recorded 18 passes and left the question open; §24 carried it to #189. Asked to stress
test it properly, the answer is unambiguous, and the useful part is not the sweep.

### The sweep, targeted rather than blind

The skip blames a nondeterministic expert-interaction count, so the sweep targeted the one
plausible mechanism: `MultiClassRDR.add_conclusion` builds a set and `make_list()`s it, so
`self.conclusions` order follows set iteration order, and `Enum` members hash by their string
name — randomised per process by `PYTHONHASHSEED`. Confirmed seed does reorder an enum set,
then swept it **systematically** instead of sampling it as repetition does.

| arm | runs | result |
|---|---|---|
| alchemy test alone, seeds 0–399 | 400 | pass |
| `test_rdr.py` sibling, skip removed, seeds 0–399 | 400 | pass |
| whole class, seeds 0–99 | 100 | pass |
| **total** | **900** | **900 pass** |

Five logged failures at seeds **130–134** were **self-inflicted** — five consecutive seeds
coinciding exactly with a fixture-swap experiment running against the same working tree; all
five pass on clean re-run. Worth recording as a method error: a long parallel sweep and an
interactive experiment must not share a checkout. The contiguity is what gave it away.

### The actual root cause, found in the history

Instrumenting answer consumption was what paid off. Every run: `loaded=18, consumed=18,
remaining=0` — the fixture holds exactly 18 answers and the test uses all of them, so it runs
with **zero margin**. Dropping one reproduces the CI symptom exactly:
`NonInteractiveTerminalError: stdin is not an interactive terminal`, because
`Human._get_conditions` catches the `IndexError` and falls through to a live prompt.

Then the dates line up:

| | |
|---|---|
| 2026-07-10 | `57a1babac` skips the test as flaky |
| 2026-07-15 | `b25353559` fixes every `.py` fixture's answer delimiter — they used `"===New Answer==="`, `experts.py` has always split on `'===New Answer==='` |

Reproduced: restoring the pre-fix fixture makes the loader return **1** answer instead of 18
and the test fails with exactly that error. So the failure was **deterministic, not flaky**,
and it was fixed five days after the skip went in. Both skips have been obsolete since
2026-07-15.

### The lesson, which is the same one this plan keeps relearning

"Flaky" was a diagnosis nobody could confirm, so it became a skip that outlived its cause by
six weeks — and then propagated, because §23 dutifully carried it to a sibling. §22 rescued a
live code path from being deleted as dead; this is the mirror image: a live test suppressed as
broken. Both times the run, not the reading, settled it. A skip whose cause was never
reproduced should carry an expiry, or at least a pointer to the run that justified it.

Recorded but not actioned: #189 should be closed and `main`'s `test_rdr.py` skip removed. The
developer marked #189 ready, so it is theirs.

**Closed 2026-08-22.** The developer's call once §26's stress test settled it: #189 proposed a
skip for a bug fixed six weeks earlier, so it is closed unmerged, branch kept. Item status set
to `deferred` — following `D-ui-splice-fix`, the one terminal status the dashboard does not
flag as drift against a closed-unmerged pull request.

`main`'s own skip on `test_rdr.py`'s sibling (`57a1babac`) is obsolete for exactly the same
reason and **is still there**, suppressing that test. Removing it needs its own change and is
not covered by closing #189.
