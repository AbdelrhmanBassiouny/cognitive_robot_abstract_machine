PR #89 — branch `conditions-root-drop-dead-parent-recovery`, off `main` (not the
session's designated `claude/ripple-down-rules-refactor-mivivh` branch, which never
got its own commits — this PR was a side-quest that came out of surveying that
branch's whole "ripple down rules refactor" stack).

## How this started
Asked to check the ripple-down-rules-refactor status and all related PRs. Found the
stack: query-class-refactor (#452) and eql-core-prep (#453) merged to main;
code-extraction (#58), code-generation-extract (#39), ripple-down-rules-refactor
(#53, replaces closed #40) open/clean/CI-green (#58 later picked up an `in-review`
label); rdr-backward-inference (#41) blocked by a real merge conflict (an automated
restacking bot flagged it `needs-resolution`) in `base_expressions.py` over whether
`_last_parent_of_type_` should exist; D-core-aid (#63) through D-core-engine (#68) —
the full re-split RDR engine chain replacing closed #60 — open, stacked on #41,
inheriting its staleness.

## What #89 actually does
Root-caused the #41 conflict: `_last_parent_of_type_` was `_conditions_root_`'s
fallback for a condition node reused across separate queries. Verified — first via
targeted probing, then exhaustively (instrumented the old method, ran the *entire*
test_eql/test_ormatic/test_class_diagrams/test_ripple_down_rules suite, 1275 tests,
with it reinstated: zero calls anywhere) — that `_conditions_root_`'s own use of it is
genuinely dead, not just redundant with `ActiveConditionsRoot` (the reasoning
`rdr-backward-inference`'s own deletion commit used, which doesn't actually hold —
`ActiveConditionsRoot` solves a different, evaluation-time problem). Traced its real
origin: added for `ConclusionSelector.insert_at` (the API `insert_refinement`/
`insert_alternative` — the RDR engine's live rule-growth — call) to patch a
node-clobbering bug PR #47 later fixed at the source; commit `84924e87` (already on
`main`) already proved it dead for `insert_at` specifically and removed it there. #89
finishes that cleanup for `_conditions_root_`'s own remaining use — and ONLY that use;
it never touches `insert_at`/`conclusion_selector.py` at all.

Four regression tests added (TDD, each confirmed passing before *and* after removal,
per a review comment asking for broader coverage than the first one alone gave):
condition shared directly by two Filters; a subexpression shared two hops down inside
AND compounds; a rule's condition reused as a different query's filter after its own
tree was built; and `Refinement.insert_at` called directly with an already-parented
condition (the literal clone-before-splice path `insert_refinement` uses).

## CRITICAL: a real regression was found in review (2026-07-21) and fixed — read before touching this PR again
The developer (via a review comment, commit-style but posted as a plain PR comment)
found a genuine gap the "1275 tests, zero calls" exhaustive verification missed: a
variable first used ONLY as a selected/output variable of a `Filter`-less query
(`entity(flag)`, no `.where(...)`), then reused as a *different* query's
where-condition, lost `satisfied_condition_ids` on the second query's evaluation.
Reproduced exactly as given, confirmed it passes on `main` and fails on this branch's
prior state. Root cause: the variable's primary `_parent_` is fixed at its first,
`Filter`-less attachment, so the simplified `_conditions_root_` fallback (`self._root_`)
lands on that same wrong root — and `SatisfiedConditionTracker.on_conclusions_processed`
(`evaluation.py`) then spuriously matches `expression._conditions_root_ is
expression._root_`, incorrectly triggering its "no where-clause" bypass.

Did NOT reinstate `_last_parent_of_type_`. Investigated why the ambiguity was reachable
specifically here and fixed it at the source instead: `on_conclusions_processed` is only
ever invoked (per its one call site in `_evaluate_conclusions_and_update_bindings_`)
after the caller already confirmed `expression` is the pass's active conditions root via
`evaluation_context.active_conditions_root.is_active_root(self)` — so recomputing
`_conditions_root_` on that same (possibly-shared) node a second time is both redundant
and, in this exact shape, wrong. The real, unambiguous answer to "does this pass have a
genuine Filter condition" is decided once, correctly, when `ActiveConditionsRoot.claim()`
runs on the evaluation's own STARTING expression (never itself a shared/reused node,
since `.evaluate()`'s caller is always a fresh top-level query). Extended
`ActiveConditionsRoot` with `has_condition()`, computed at claim time as `root is not
originating_expression._root_` (NOT `root is not originating_expression` — a `Query`
wrapper's `_conditions_root_`/`_root_` both delegate to its compiled product, a
different object from the wrapper itself, so comparing against the wrapper directly gives
false positives for the plain Filter-less case; caught this via a real test failure
before shipping it). `SatisfiedConditionTracker` now consults `has_condition()` instead
of recomputing anything. This is the same evaluation-scoped explicit-context-threading
pattern already used for the neighboring "which Filter's pass is running" question —
applied to the one place that had been silently bypassing it.

TDD: added the exact reported repro as `test_satisfied_condition_ids_for_a_variable_
first_used_in_a_filterless_query` in `test_explanation.py` (that file already had the
`satisfied_condition_ids` test pattern via `_get_true_results`/`_get_satisfied_names`),
confirmed it fails against the prior code and passes with the fix. Added direct unit
tests for `ActiveConditionsRoot.has_condition()` in `test_evaluation_context.py`
(`_NodeStub` extended with a `_root_` attribute, defaulting to self). Full test_eql/
test_ormatic/test_class_diagrams/test_ripple_down_rules: 1282 passed, 9 skipped.
Re-verified against PR #78's branch (see reconciliation below) after fixing a
mechanical error in my OWN merge-probe conflict resolution — not a problem with this
PR's actual content, but worth knowing about if merge-probing #78 again: `D-ui-splice-fix`
already carries PR #67's fix, which moved `active_conditions_root.claim(...)` OUTSIDE
the `if owns_an_evaluation_context:` guard (unconditional, called from every node) so
that `classify_case`/`trace_case`'s pre-installed-context pattern still gets a claim.
When resolving the textual conflict between that placement and my added second
argument, I initially kept MY placement (still inside the `if` block), silently
reverting #67's fix — this caused `test_single_class_rdr.py`/`test_ask_for_rule.py`/etc.
to hang or fail on the merged probe branch. Not a bug in `main`/this PR itself (which
never had #67's restructuring to begin with — verified the actual committed PR branch
passes 1282/1282 both before and after this whole detour). Fixed by keeping the claim
call unconditional (outside the `if`) with my 2-arg signature, on the SCRATCH probe
branch only. Also found and confirmed pre-existing, unrelated to this PR entirely (via
checking out `D-ui-splice-fix`'s own files with zero trace of this PR's diff): a hang in
`test_single_class_rdr.py`/`test_underspecified_rdr_integration.py` on that branch's
current tip. Flagged it in the PR #89 comment reply for the record; not investigated
further, not this PR's problem.

Pushed as commit `c69b6e9d`. Replied on the PR comment thread explaining the fix. PR
description updated to match. Still draft, CI was 18/18 green as of the previous push;
re-check CI on `c69b6e9d` specifically next time this PR is touched (not yet confirmed
green on this exact commit as of this note).

## IMPORTANT reconciliation with PR #78 (found 2026-07-20, same day)
PR #78 (`D-ui-splice-fix`, base `D-core-engine`) independently **reintroduced
`_last_parent_of_type_`** for a real, proven bug: reloading a human-fitted zoo model
dropped 12/21 rules (101/101 -\> 71/101 accuracy) because `insert_at` spliced above
`anchor._parent_`, and a shared-identity `MappedVariable` anchor (e.g. `animal.eggs`)
keeps whichever parent attached *first* as primary — which can be an incidental
`Comparator` from an earlier sibling branch, not the rule-tree structure `insert_at`
actually needs to splice into. #78's own commit message flags exactly the risk I
needed to check: "The earlier removal of this fallback ('empirically dead') was based
on an instrumented run of suites that did not yet exercise this reload scenario."

Investigated directly rather than assuming either way:
- Diffed #78's actual change: it adds `_last_parent_of_type_` fresh to
  `base_expressions.py` (D-core-engine doesn't have it) and uses it **only** in
  `conclusion_selector.py`'s `insert_at`, to recover the anchor's structural parent.
  It does **not** touch `_conditions_root_` at all.
- Confirmed `_conditions_root_` on #78's own branch is byte-identical to what #89
  produces (plain graph walk, `self._root_` terminal default, no fallback) — meaning
  #78's own regression test suite (including its new
  `TestAttributeReusedInEarlierSiblingBranch`) already passes today with
  `_conditions_root_` in exactly the state #89 leaves it in.
- Merged #89 into #78's branch directly (scratch probe) to be certain, not just
  reason about it: clean merge, no conflicts. Ran #78's specific regression test
  (`test_nested_refinement_on_reused_attribute_stays_in_rule_tree`) on the merged
  state: **passed**. Ran the full `test_eql_rdr` suite on the merged state: **229
  passed, 0 failed** (even cleaner than the D-core-engine-only check below — those 8
  pre-existing progress-bar NamedTuple/tuple failures aren't present on #78's branch).

**Conclusion: #89 and #78 are fully compatible, not in tension.** They independently
rediscovered the same method name for two genuinely different call sites — one dead
(`_conditions_root_`'s fallback, #89's target), one very much alive and buggy without
it (`insert_at`'s anchor-parent recovery, #78's fix) — and the "empirically dead"
mistake #78's commit message warns about was `84924e87`'s conclusion about
`insert_at` specifically, not anything #89 touches. #78 will simply reintroduce
`_last_parent_of_type_` itself (it already does, in its own diff) regardless of
whether #89 has merged to main yet; no coordination needed between the two PRs, and
no changes needed to #89 as a result of this finding.

## Status
Draft PR (still draft — no push has ever marked it ready). `mergeable_state: unstable`
as of the 2026-07-27 push (head `596b7d08`), because of the pre-existing
`test_world_sim_state_sync` MuJoCo flake (see 2026-07-27 entry below) — not a real
conflict. 9 review threads total, all replied-to and resolved (the original
broader-coverage one from 2026-07-20, plus the 8-comment round from 2026-07-27). PR
description updated to reflect the 2026-07-27 round (design change to
`ActiveConditionsRoot.claim`, the specific-value test assertions, the AGENTS.md rule
addition) and the #78 reconciliation.

## 2026-07-27 — restack + 8-comment review round, all addressed
Branch had been restacked several times since the 2026-07-22 note (base now `main`
directly, 229 files/18k+ lines of unrelated churn from the rest of the repo moving —
confirmed via `git log` that none of it touches this PR's own files). A CI check
fired first: `test_each_lib (semantic_digital_twin)` → the same
`test_world_sim_state_sync` MuJoCo physics-settling flake seen on 2026-07-21/22
(different job, same root cause: box doesn't reach target position within tolerance).
Confirmed unrelated again via job log; did not rerun (same no-rerun-without-approval
default). Then a real 8-comment review round landed, all on the previous
`has_condition`-via-`ActiveConditionsRoot` design and its tests:

1. `evaluation.py` `on_conclusions_processed`: hash-comment block → proper docstring.
2. `base_expressions.py` `_conditions_root_`: `expr` loop variable → `expression`
   (no-abbreviations rule).
3. `evaluation_context.py` `ActiveConditionsRoot.claim`: reviewer flagged the
   `root is not originating_expression._root_` identity-comparison inference as "weird
   and unintuitive" — agreed, and it was also the awkward bit the Query-wrapper caveat
   existed to explain. Replaced it with an explicit `has_condition: bool` parameter;
   `claim()` no longer takes `originating_expression` at all. The caller
   (`SymbolicExpression._evaluate_`) now computes that boolean via a new, symmetrically-
   named `_has_condition_` property (walks `_all_expressions_` for a `Filter`, same as
   `_conditions_root_` does, just answering the yes/no question directly instead of
   returning the condition). This is a real design improvement, not just a docstring
   fix — the caller no longer needs to reverse-engineer "was there a Filter" from an
   identity comparison against a value it has to reason about the provenance of.
4. `test_evaluation_context.py` `_NodeStub`: converted to `@dataclass` per the "always
   use dataclass" rule; simplified to a single `_id_` field since it no longer needs
   `_root_` at all now that `claim()` dropped `originating_expression`.
5-7. Three `test_rules.py` assertions (`shared_subexpression`/`refinement_condition`/
   `new_condition` `._conditions_root_ is not None`) — reviewer wanted the actual
   expected value asserted, not just non-nullness. Probed each empirically with a
   throwaway script rather than guessing:
   - `shared_subexpression._conditions_root_ is first_compound` (had to name the
     previously-inline `and_(...)` to assert against it) — deterministic because the
     subexpression's primary parent is fixed at first attachment.
   - `refinement_condition._conditions_root_ is query._conditions_root_` — resolves to
     the *originally owning* query's own conditions root (a `Refinement`, not the plain
     top-level condition, since `Add(...)` was used inside `with query:`), never
     `other_query`'s.
   - `new_condition._conditions_root_ is query._conditions_root_` — after `insert_at`
     splices it into `query`'s (the anchor's) rule tree, it resolves into that same
     tree's (now-grown) conditions root.
   Mind the gap: initially cross-wired two of these three replies (posted the
   `refinement_condition` explanation onto the `new_condition`/`insert_at` thread and
   left the actual `refinement_condition` thread unanswered) — caught it by re-checking
   `original_line` on each reply via the API before resolving, posted a correction on
   the wrong thread and the correct reply on the right one. Worth double-checking
   `original_line`/diff_hunk content against intent before replying when several
   same-file comments land in one batch — this is the second time in this PR's history
   a batched round caused a mis-targeted reply (see P1's note in the roadmap for the
   first).
8. `test_explanation.py` filter-less-query regression test: reviewer asked what it
   tests and, again, why only `is not None`. Traced the actual expected value: `flag`
   is a bare variable (not Comparator/Predicate/LogicalOperator), so
   `is_condition_participant` correctly excludes it — the true expected value is an
   *empty* `OrderedSet`, not "some ids". Reworded the docstring to say so explicitly
   and tightened the assertion to `== set()` (strictly stronger than `is not None`:
   catches both the old `None` regression and a wrong non-empty result). The comment
   also asked to add a Testing rule to AGENTS.md about specific assertions — added it
   ("Make assertions as specific as possible: when the correct expected value can be
   determined, assert equality to that value rather than only a weaker check such as
   not-None or not-empty") in its own commit.

Verified locally: set up a proper local test environment for the first time this
PR (`/tmp/krrood-venv`, Python 3.12 — python3.11 breaks `make_dataclass(module=...)` in
`class_diagram.py`, matching the P1-P4 roadmap's known caveat; needed `--confcutdir=
test/krrood_test` to dodge the root `test/conftest.py`'s full semantic_digital_twin/
mujoco/ROS dependency chain, plus `pip install inflection` for `code_generation.naming`,
a new dependency that arrived via the restack). Full `test/krrood_test/test_eql` +
`test_ripple_down_rules`: **1188 passed, 6 skipped** both before and after the fix
commit. `scripts/format_docstrings.py` (black + docformatter) run on every touched
file. Reverted two incidental PDF diffs (`drawer_explanation.pdf`, `query_graph.pdf`)
that a test run regenerated as a side effect — not part of this change.

Two commits pushed: `486dfeb5` (the 7 code/test fixes above) and `596b7d08` (the
AGENTS.md rule, kept separate since it's a docs-only, cross-cutting change rather
than part of this PR's actual fix). All 8 new threads plus the original 2026-07-20
thread (9 total) replied-to and resolved. PR description rewritten to describe the
final `has_condition`-parameter design and this round's outcome.

## The bigger picture (found while answering "what's the rest of the refactor plan")
There's a much larger master roadmap than what loaded into any single session:
`.claude/personal/rdr-roadmap.md` on `claude/personal-notes` (not auto-pulled into
CLAUDE.local.md — only the generic `cram-notes.md` + this branch's own progress file
are). It documents three original design docs (EQL-native RDR engine; the forward
architecture — feature layer/"poor man's Rete", MCRDR+GRDR port, concept trees, OO
integration, TMS/JTMS; truth unification) and a full wave-by-wave delivery plan:
- **Wave 0** (in progress): the split-PR stack #452→...→#68 (D-core-engine, draft);
  then D-ui split into #78→#79→#76 (splice fix → case-table rendering → interactive
  shell), then D-store (#80) → D-deco (#77) (RDRFileStore, then the `@rdr` decorator).
  All currently open/draft, CI green or green-with-known-unrelated-flakes, per their
  own detailed progress notes (`pr-progress/D-ui.md`, `D-store.md`, `D-deco.md`).
- **Why & Montessori track** (priority after Wave 0, per a 2026-07-16 decision): W1
  `rdr/why-answer` (base D-core-engine — its own note says "not started" but is
  stale; W2/W3 are clearly built on real `WhyAnswer`/`rule_code` functionality, so W1
  shipped, just never had its progress note updated) → W2 `eql/causal-verbalization`
  (PR #82, draft, deep in review: 20/22 threads resolved, 2 blocked on PR #83) → W3
  `rdr/why-query-surface` (PR #84, draft, stacked on W2, 21 tests, CI green). Plus
  C1 `rdr/decision-queries` (parallel to W3), M1/M2 Montessori demo (deferred,
  waiting on an unrelated `montessori_ijcai` branch).
  PR #83 (`eql/attribute-predicate-verbalization`, boolean-predicate verbalization,
  labeled `in-review`) is a dependency of W2's last 2 open threads.
- **Wave 1** (after Wave 0 lands): Track F (feature registry), Track G (multi-class
  RDR + general fixpoint), Track T (truth unification — must wait for #28/#453 to be
  on main, which it now is).
- **Wave 2**: concept trees (needs F+G). **Wave 3**: OO integration + TMS/JTMS
  (needs Wave 2).
Full detail, live PR numbers, and the dependency graph are in `rdr-roadmap.md`
itself — re-read it directly rather than trusting this summary once acting on Wave
0/Why-track items, since several per-PR notes (D-ui.md especially) have their own
detailed restack/flake history worth checking before touching those branches.

## 2026-07-21 (later) — restack + a flaky CI failure, left alone on purpose
Branch got auto-restacked onto a newer `main` (merge commit `49383ac1`, PR base sha
advanced). One CI job failed on the new tip: `test_each_lib (semantic_digital_twin)`
→ `test_multi_sim.py::test_world_sim_state_sync`, a MuJoCo physics-settling timing
assertion (dropped box's final position off by fractions of a meter) — confirmed
unrelated: the `krrood` job itself (the one that actually exercises this PR's diff)
passed, and this PR never touches `semantic_digital_twin`/physics code at all. Asked
the user whether to trigger a rerun; they declined answering via the structured
question and said to continue, so left CI as-is rather than rerunning unilaterally
(reruns are a visible, resource-consuming action per this repo's own established
precedent — don't do it without clear approval). `mergeable_state` is currently
"unstable" because of this one red job, not a real conflict. Re-check on the next
check-in; rerun only if explicitly asked, or note it again if it's still red and
blocking.

## 2026-07-22 — second restack, another unrelated flake, left alone
Branch restacked again (now 6 commits, base advanced to `efad238d`, head `5ce760af`).
One more CI failure, different job this time: `test_each_lib (coraplex/scripts/
test_notebook_examples.sh)` — a `treon`-run Jupyter notebook (`motion_designator.ipynb`)
hit `zmq.error.ZMQError: Address already in use` from a leftover kernel process, then
`RuntimeError: Kernel didn't respond in 60 seconds`. Pure Jupyter/ZMQ port-contention
flake in coraplex's notebook test infra, zero relation to this PR's `entity_query_
language` diff — confirmed via job log, and the `krrood` job itself passed. Did not
rerun (same "don't rerun without clear approval" default as the 2026-07-21 note above;
the user directed "continue" rather than answering the rerun question, so treating that
as staying with the default of not taking the visible/resource-consuming action
unprompted). Re-check next time this PR is touched — rerun only if asked.

## 2026-07-27 (later) — follow-up round on the already-addressed review

IMPORTANT process lesson: this session was dispatched to "handle the review
comments" and redid the entire 8-comment round from scratch before noticing it was
ALREADY DONE. Both `mcp__github__pull_request_read` (review threads showed
`is_resolved: false`) and the local git ref (2 commits behind) were stale at session
start. The round had in fact been handled at 07:43-07:46 in `486dfeb5` + `596b7d08`,
with replies on all 9 threads. **Re-fetch the branch (`git fetch`) AND re-read the
threads before starting work on any "handle the review" task** — a stale thread list
is not proof the work is outstanding. The duplicated work was discarded (kept locally
on branch `review-followup-local`), branch reset to origin, nothing force-pushed.

What did ship (commit `b5d72adb`, pushed): four genuine loose ends the previous round
left, approved by the user before pushing.
1. `_conditions_root_` and `_has_condition_` each walked `_all_expressions_` for a
   `Filter` independently — two implementations of one question. Both now derive from
   a single new `_filter_condition_` property (gating Filter's condition, or `None`).
2. `_conditions_root_` was annotated `Optional[SymbolicExpression]` + documented as
   returning None, but never returns None (fallback is `_root_`). Tightened on both
   `SymbolicExpression` and `Query`'s override.
3. `Query._root_`'s docstring justified the override by the
   `_conditions_root_ is _root_` comparison **this PR deletes** — stale the moment the
   fix landed. Rewritten to describe the actual behaviour (root-relative resolution
   must reach the compiled product), matching how `_all_expressions_`/`_descendants_`
   are explained.
4. The filter-less regression test's `satisfied_condition_ids == set()` assertion:
   reasoning was right (bare variable isn't an `is_condition_participant`) but an
   empty-set assertion cannot distinguish "tracked the right ids" from "tracked
   nothing", which is exactly the failure mode being guarded. Shared node changed from
   a bare variable to a `Comparator` (`value > 5`) — same bug shape, exact expected
   value `{condition._id_}`. Re-verified it still fails against pre-fix source
   `8ce63b0d` (`satisfied_condition_ids` is `None`). This one revisits a decision the
   reviewer had already accepted and resolved, so it was called out explicitly in the
   PR comment with an offer to revert.

Verification env note (reusable): no pytest in the sandbox. Built a venv at
`$SCRATCHPAD/venv` with `/usr/bin/python3.12` (NOT `python3`, which is 3.11 and breaks
`make_dataclass(module=...)`), then `pip install pytest ./random_events
./probabilistic_model casadi objgraph mypy black docformatter tqdm` + `pip install -e
./krrood --no-deps` (editable, or source edits don't take effect). Run with
`--confcutdir=test/krrood_test` to dodge the root `test/conftest.py`'s
semantic_digital_twin/mujoco chain. Results: 1332 passed, 6 skipped across
test_eql/test_ormatic/test_class_diagrams/test_ripple_down_rules/
test_underspecified_knowledge; the only 2 failures are `test_object_diagram`'s missing
Graphviz `dot` binary, confirmed identical on a stashed clean tree.

Two traps hit while verifying, worth remembering:
- Running the suite regenerates `drawer_explanation.pdf` and `query_graph.pdf`.
  `git checkout --` them before committing (happened twice).
- `git checkout <sha> -- <paths>` **stages** those paths. After restoring the working
  tree by hand, `git diff` compares against the stale index and shows phantom changes.
  `git reset` (mixed) fixes it. Nearly mistook this for formatter churn.
- `scripts/format_docstrings.py` reflows unrelated pre-existing docstrings in files it
  touches (`EvaluationContext` fields, four `test_rules.py` one-liners). Revert that
  churn to keep the diff focused.

PR #78 cross-check redone against my signature change: only overlap is one mechanical
conflict in `base_expressions.py` (resolution: keep #78's *unconditional* `claim()`
placement — outside the `owns_an_evaluation_context` guard, per PR #67 — with this
branch's argument list). The merged state's 2 failures
(`test_conclusions_fire_with_a_pre_installed_evaluation_context`,
`test_conclusions_respect_a_bare_attribute_conditions_root_truthiness`) **already fail
on #78's own tip**, verified separately — not caused by #89.

PR description rewritten to match; explanatory comment posted
(`#issuecomment-5088926308`). PR still draft. Branch note: the session's designated
branch `claude/rdr-refactor-conditions-root-recovery-31difc` held unrelated
plan-dashboard commits, so (user-confirmed via AskUserQuestion, same as PR #87's
precedent) the push went to PR #89's real head `conditions-root-drop-dead-parent-recovery`.

## 2026-07-28 — 3-comment review round: extract test helpers into production methods
Restacked branch pulled first (47 commits behind, all unrelated churn elsewhere in the
repo). Three new review comments, all on the `test_explanation.py` helpers the
filter-less-query regression test had introduced:

1. `_get_true_results`: "can this be a method on `SymbolicExpression`/`Query` instead
   of a test function? Check if something similar already exists. How is it different
   from `.tolist()`?" — checked first (grepped for other `is_true`-filtering in
   production code) and found `evaluate()` already had almost the identical filter
   inline: `(self._process_result_(res) for res in self._evaluate_() if res.is_true)`.
   Extracted it into `SymbolicExpression._true_results_()`, had `evaluate()` call it
   too. Real answer on `.tolist()`: not interchangeable — `tolist()`/`evaluate()` map
   through `_process_result_` into user-facing output values, which is exactly what
   discards the raw `OperationResult` (and its `satisfied_condition_ids`) these tests
   need. `_true_results_()` returns the pre-mapping raw results; `_get_true_results`
   stays as a thin test wrapper (`query.build()` + `list(query._true_results_())`).
2. `_get_satisfied_names`: "same comment applies." No existing similar method found.
   Added `SymbolicExpression._names_for_ids_(ids)` (self + `_descendants_`, matching
   the helper's exact prior semantics — deliberately not `_all_expressions_`, which
   would walk the *whole* tree from the top root rather than just this node's own
   subtree). Deleted the test helper entirely; every call site now calls
   `condition_root._names_for_ids_(ids)` directly.
3. One test (`test_satisfied_conditions_and_both_true`) had `_get_satisfied_names`'s
   body duplicated inline instead of calling it — reviewer caught it, replaced with a
   direct call to the new `_names_for_ids_` method.

Verified: `test_eql`/`test_ripple_down_rules` 1188 passed; full
`test_eql`/`test_ormatic`/`test_class_diagram`/`test_ripple_down_rules`/
`test_underspecified_knowledge` 1384 passed, 6 skipped, no failures (grew from 1332
via unrelated upstream test additions picked up by the restack). `scripts/
format_docstrings.py` run; reverted the `drawer_explanation.pdf`/`query_graph.pdf`
regen artifacts again (same trap as the 2026-07-27 note — happened a third time,
worth just checking for these two files by habit after any local test run on this
branch from now on). Pushed as `d248328e`. All 3 threads replied-to and resolved. PR
description updated to describe the extraction.

## 2026-07-28 (later) — immediate 1-comment follow-up on `_names_for_ids_`
Same day, next comment batch, on the method the previous round had just added:
"why loop over all expressions? don't we already have a helper that caches these
given an id? And is this only for this node + descendants — if so name it that way."
Both right. `_get_expression_by_id_` already existed (per-instance `_expression_id_cache_`
dict plus an evaluation-scoped index) — the loop-and-check-membership implementation
was reinventing it. Rewrote to `{self._get_expression_by_id_(id_)._name_ for id_ in ids}`;
renamed `_names_for_ids_` → `_subtree_names_for_ids_` (fixed the reviewer's suggested
spelling "descendent" → "descendant"/"subtree" to match the codebase's own
`_descendants_` spelling) with a docstring stating the precondition explicitly: ids
must belong to this node's own subtree. Note this technically resolves through the
whole tree internally (`_get_expression_by_id_`'s fallback walks from `_root_`), not
just self+descendants — harmless in practice since every caller only ever passes ids
that are already within this node's own subtree by construction (satisfied_condition_ids
computed from this same node's own evaluation pass), and if that precondition were ever
violated the lookup now raises `NoExpressionFoundForGivenID` instead of silently
excluding the id, which is the more correct failure mode per AGENTS.md. Verified:
`test_explanation.py` 33 passed; full `test_eql`/`test_ripple_down_rules` 1188 passed.
Pushed as `4c01e286`. Thread replied-to and resolved. CI kicked off on the new push,
not yet resolved as of this note — re-check next check-in.

While CI for `4c01e286` was running, `test_each_lib (probabilistic_model)` hung on its
"Install dependencies" step for over an hour (every sibling job finished in under 15
minutes) — flagged it to the user rather than rerunning unilaterally; the user didn't
answer the rerun question directly and instead sent the standard recurring check-in
prompt twice, so treated that as staying with this PR's established no-rerun-without-
explicit-approval default (same as the 2026-07-21/07-22 precedent) and just kept
reporting it as still stuck each check-in.

## 2026-07-28 (yet later) — immediate 1-comment follow-up: name still overstated scope + Set→List bug
Same day, next comment batch, on the method the previous round had just renamed to
`_subtree_names_for_ids_`: "there's nothing in this method that makes sure the ids are
in this node's subtree, it's just getting names by id — if that's intended, name it
`_get_expression_names_by_their_ids_`. And why is this a `set()`? Are names guaranteed
unique? Won't that remove needed ones?" Both right, and the second one is a real latent
bug, not a nit: expression names collide (e.g. `and_(x > 5, y > 3)` has two `>`
comparators), so a `Set[str]` result could silently collapse two genuinely-satisfied,
distinct conditions into a single `">"` entry — indistinguishable from only one being
satisfied. Renamed to `_get_expression_names_by_their_ids_` and changed the return type
to `List[str]` (one entry per id, in input order); all 5 call sites in
`test_explanation.py` updated, `in`/`not in` assertions still work unchanged on a list.
Verified: `test_explanation.py` 33 passed; full `test_eql`/`test_ripple_down_rules`
1188 passed. Pushed as `b054a048`. Thread replied-to and resolved. This resolved the
stuck-CI situation too, incidentally — the new push superseded the hung
`probabilistic_model` run with a fresh one.

## Next
- Keep watching #89 until merged — re-arm check-ins, act on any CI failure or
  comment.
- Once merged to `main`, the automated restacking bot should cascade this down
  through code-extraction (#58) → code-generation-extract (#39) →
  ripple-down-rules-refactor (#53) → rdr-backward-inference (#41), clearing #41's
  conflict for free since `rdr-backward-inference` already independently deleted the
  same method. Verify that actually happens after merge; nudge manually if the bot
  doesn't pick it up.
- After #89 lands: #58/#39/#53 still need actual review/merge (clean, CI-green, not
  blocked on #89 at all — could proceed in parallel; #58 already has an `in-review`
  label as of 2026-07-20).
- Separately, not blocking #89: the Why-track (W1–W3, #82/#84) and D-ui/D-store/D-deco
  (#76/#78/#79/#80/#77) chains are far along and mostly just need review/merge — see
  their own progress notes and `rdr-roadmap.md` for what's actually next on each.
