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
Draft PR, CI green (18/18), `mergeable_state: clean`. One review thread (asking for
broader test coverage) replied-to and resolved. PR description updated with the full
history/verification (not yet updated with the #78 reconciliation — consider adding
a short note there too, low priority since it doesn't change #89's content).
Subscribed to all PR activity; hourly check-ins scheduled via `send_later` (re-arms
itself silently when nothing's actionable — confirmed CI still green / no new
comments as of the last two check-ins).

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
