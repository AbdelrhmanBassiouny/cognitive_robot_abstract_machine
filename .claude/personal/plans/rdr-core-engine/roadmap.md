# The RDR core engine — Roadmap

Narrative half of `rdr-core-engine`. One of seven plans the oversized
`rdr-refactor` was split into on 2026-08-30; the predecessor's full 3,259-line
roadmap remains in the personal-notes branch's history immediately before that
split commit. This plan carries the programme's working method, because that is
where it was learned and where most of the remaining work is.

## What is being built

An EQL-native Ripple-Down Rules engine: the rule tree is a live EQL DAG rather
than strings or an AST round-trip, RDR is an `EvaluationObserver` over EQL
evaluation, the tree grows by inserting `Refinement`/`Alternative` selectors
into that live DAG, expert answers are live EQL expressions, and persistence is
Python source through the unparser. It is delivered as a stack of
topic-oriented pull requests rather than as one mega-branch, each carrying its
own tests, merged bottom-up with a cascade after each landing.

The chain, in dependency order: `ripple-down-rules-refactor` (#53) →
`rdr-backward-inference` (#41) → `D-core-aid` (#63) → `D-core-underspecified`
(#64) → `D-core-corner-case` (#65) → `D-core-serialization` (#66) →
`D-core-support` (#67) → `d-core-expert` (#98) → `d-core-single-class` (#159) →
`d-core-backend` (#210). The user-facing layers continue in
`rdr-interface-and-decorator`, stacked on #210.

## Decisions locked in, and what depends on them

**1. The three-way split of the mega-slice.** `D-core-engine` (#68) drew 71
review threads and a request to split; it is superseded by `d-core-expert` →
`d-core-single-class` → `d-core-backend`, and is kept only as a branch. Nothing
can land through it, which two later sessions each rediscovered the hard way
when an item's own note named it as a restack target.

**2. Engine behaviour, settled in #68's review.** `classify()` returns the
sentinel rather than `None` when no rule fires; non-convergence raises
`RDRDidNotConvergeError` and `max_passes` is gone, bounded instead by
oscillation detection plus a termination test; `rdr/exceptions.py` holds the
`DataclassException` hierarchy; conclusion validation lives on
`ConclusionDomain`; an `AnswerName` enum replaces the duplicated `"conditions"`
/ `"conclusion"` strings; `CaseContext` is built by the engine and threaded down
as a parameter object; progress and save use Null-Object defaults; and
`backend.infer` splits into a pure `infer` yielding `UnificationDict` and an
eager `fill`.

**3. `GuardCondition.negated` is a polarity flag, not a `Not()` wrapper.**
`not_()` reparents a live rule-tree node, which corrupts the tree the guard
belongs to. The decision carries an explicit expiry: `Not()`-wrapping is cleaner
at four of six use sites and wins outright once `dag-facade-hardening` (#96)
lands a non-mutating negation. The rationale lives in the field's own docstring,
because its design document is on a dropped path and will never land.

**4. Per-selector traversal semantics are a family, kept over advice.**
`rdr/branch_semantics.py` holds one `SelectorBranchSemantics` class per
selector, carrying both `sibling_guards` and `branches`, dispatched through
`krrood/patterns/specificity_ranking.py`. This session's own recommendation was
to collapse it onto the selector classes; the developer kept the family, and
that thread is theirs to close. One coupling worth carrying if it ever does
move: the natural return type would be an `(expression, polarity)` pair, which
is an EQL-level concept rather than an RDR one.

**5. Neither the selectors nor `GuardCondition` move.**
`rules/conclusion_selector.py` is on main with EQL-core consumers — the public
`refinement()`/`alternative()`/`next_rule()` DSL, `scope.py`, `query_graph.py` —
so moving the selectors into `rdr/` points the DSL front door at the RDR
subpackage. Moving `GuardCondition` into `rules/` is the same error smaller: it
is a backward-chaining concept whose every consumer is in `rdr/`.

**6. `...` replaces `UNSET`, and `rdr/utils.py` is gone.** Both are singletons
compared with `is`, so every site substituted unchanged. `AnswerName` and
`NamespaceName` moved together into `rdr/answer_vocabulary.py` — one module,
because `AnswerName.example_assignment` is built over
`NamespaceName.CASE_VARIABLE` and both must sit below `interface.py` and
`exceptions.py` to avoid a circular import. `allow_unset` and the `test_unset_*`
names are deliberately unchanged: "unset" there names the state the expert left
the conclusion in, not the identifier.

**7. `ExpertInterface` carries only the expert Q&A surface.** Model persistence
and fitting progress were three unrelated responsibilities in one class, and the
engine reached two levels deep to write `expert.interface.on_save`. The RDR now
holds a `ModelSaver` and a `ProgressReporter` as its own collaborators with
Null-Object defaults. Giving the RDR the *whole* interface was considered and
overshoots — it would hand the engine the Q&A mechanism and force it back on
every `ask_for_*` call.

**8. A fit saves once on its way out, not once per inserted rule.** The save
sits in a `finally`, so a crash keeps the rules it authored. An empty tree is
deliberately not saved: saving unconditionally let `EmptyRuleTreeError` from
inside the `finally` replace the exception the caller actually needed to see. A
saver that fails for any *other* reason still masks the fit's exception, and
catching that to hide it is what `AGENTS.md` rules out, so it is the developer's
call.

**9. The condition resolver takes the RDR.** `resolve(rdr, context)`, typed
under `TYPE_CHECKING`, so nothing is imported from `single_class` at runtime and
the unit tests still need no engine. The corner-case gate applies once on
`ConditionResolver.resolve` and delegates to an abstract
`_resolve_against_corner_case`, so a future strategy inherits the precondition
rather than restating it. An earlier objection that this created coupling was
wrong, and checking the import graph before offering a coupling argument is the
habit that would have caught it.

**10. `RDRBackend` inherits `QueryBackend`.** Neither concrete base fits —
`SelectiveBackend` raises on exactly the ellipsis matches this backend exists
for, and `GenerativeBackend` constructs new instances where this completes an
attribute on existing ones — but neither reaches `QueryBackend` itself, whose
whole ABC is `evaluate(expression)`. `evaluate` is `fill`'s eager completion and
returns an iterator rather than being a generator, so a non-`Match` expression
raises `QueryIsNotAMatch` at the call rather than at first iteration. Narrowing
the parameter to `Match` was rejected as a Liskov violation.

## Open, and genuinely undecided

- **A labelling fit never checks convergence.** Two cases labelled differently
  but justified by a condition they share end with `fit` returning normally and
  the first classifying as the second's label; the same input *with* targets
  raises `RDRDidNotConvergeError`. Reproduced. Not fixed, because the fix
  changes what a labelling fit costs a human — a second pass re-asks about cases
  their own rule broke. Three options are on thread `r3838361318`.
- **Seven design threads from the 2026-08-23 review on #159** remain open and
  were deliberately not guessed at, among them whether the retry's gate should
  key on *"did we ask the expert"* rather than on `resolution_mode`.
- **The `GroundTruth` type alias on #210** — whether it should become a class.
  Nothing in `entity_query_language/rdr/` expresses a per-case ground-truth
  supplier; the only thing that does is the legacy package this split retires.
  Three options are on the thread.
- **`test_null_saver_writes_nothing_for_a_fitted_tree` asserts nothing** on #98
  and is reported but unfixed.

## Standing hazards

- **CI is wedged on #98, #159 and #210's own merge refs.** All three read
  `mergeable_state: unknown` and queue no runs however many times they are
  pushed; `ci.yml`'s trigger is unfiltered and the merges are trivial
  fast-forwards, so the wedge is GitHub-side. A base move followed by a push
  cleared it once and has since failed twice. A branch opened fresh off a wedged
  one gets one working push and then wedges too. The remedy nobody has tried is
  closing the wedged pull request and opening a new one for the same branch.
- **The cascade did not stall uniformly.** Measure how far behind each branch is
  before planning a steward pass rather than assuming stack order tracks it.
- **Two generated files, not one, were conflicting on #67 — cleared
  2026-08-31.** `test/krrood_test/dataset/ormatic_interface.py` was tracked
  only here and is now removed from the index, with `main`'s
  `**/ormatic_interface.py` ignore rule arriving in the same merge. The second,
  `verbalization_results.py`, is tracked *everywhere*, so untracking was never
  its answer: this branch's older generator emitted `typing_extensions.Tuple`
  where the current one emits stdlib `tuple[...]`, and the fix was to take the
  base's output. Both remain regenerated at test time, so a dirty tree after a
  sweep is still the normal state.
- **`open_ready` means open plus non-draft, and deliberately not more.** It
  answers *"can a dependent safely start stacking on this?"*, which stayed true
  of #67 throughout the six days it was unmergeable against its own base.
  Folding `mergeable_state` in would buy a visibility problem with a false
  negative; the visibility belongs in a per-item mergeable chip instead.
- **`scripts/format_docstrings.py` regresses ```:return: ``x``` ``` to
  ```:return:``x``` ** and rewrites unrelated docstrings wholesale — fourteen
  recorded instances. Every round reverts its churn by hand and keeps its output
  only where the file is being rewritten anyway. It wants a package-wide pass of
  its own, which nobody has taken.

## The working method this programme arrived at

Recorded because each entry cost a round to learn, and because the next session
inherits them rather than rediscovering them.

- **Run the probe; do not reason about the code.** It rescued a retry loop about
  to be deleted as dead, disproved a claimed soundness bug in `_leaf_guards`,
  disproved a claimed simplification of `evaluate()` that would have made every
  false leaf guard read as true, showed that comparing only against the
  preceding pass makes the convergence check hang rather than fail, and caught a
  `finally` that swallowed the caller's exception. Six entries, none visible in
  a diff.
- **An assertion that looks specific is often vacuous.** `==` on symbolic
  expressions builds a truthy `Comparator`, so nine assertions constrained
  nothing until they compared `_id_`. A membership test passed because a
  *different* code path already established the fact it asserted. The lens that
  catches these is mutation: six minutes of wall clock, and it should be the
  default rather than the exception.
- **Compare sorted collected test ids, never counts.** A conflict resolved the
  obvious way silently dropped six tests and the count read as a clean merge.
- **A local sweep in a bare container shows *no new failures*, never *no
  failures*.** CI is the load-bearing check. But the gap was always the
  container: a 3.12 venv with the workspace requirements and editable
  `random_events`/`probabilistic_model` runs the suite green, including the
  tests earlier rounds recorded as an unfixable local gap.
- **Before untracking a generated file, check whether it is tracked on
  `main`.** #67's conflict was recorded for six weeks as one file's problem
  with one file's answer. When it finally got worked, a second generated file
  was conflicting too — and that one is committed on `main` and on every branch
  in the chain, so untracking it would have been a regression rather than the
  fix. "It is generated" says how it got there, not whether the repository
  keeps it.
- **A routine that reports the same conflict every pass is not making
  progress.** Six identical skip comments accumulated on #67 between 08-13 and
  08-28 while the branch and everything stacked above it sat still. The label
  is working as designed — later passes skip rather than re-report — so the
  signal that needs watching is the repeat count, not the newest comment.
- **Stage by explicit path; never `git add -u`.** A test sweep regenerates
  `ormatic_interface.py`, `query_graph.pdf`, `drawer_explanation.pdf` and
  `verbalization_results.py`. A dirty tree after a sweep is the normal state
  here, not a signal to commit.
- **Finish a rename by grepping the whole tree, not by re-reading the diff.**
  One rename was counted twice from its own diff and still undercounted: four
  renames, fourteen stale readers, two of them in production source the diff
  never contained.
- **A reviewer reads a diff, not a rationale.** Where a change to an earlier
  pull request's file belongs is settled mechanically — if making it downstream
  conflicts, it belongs upstream — but a correct commit message does not rescue
  a diff the reviewer cannot make sense of.
- **Re-read a pull request's threads immediately before reporting a round
  finished.** Nine recorded rounds were reported as complete while a review that
  had opened minutes earlier went unrecorded, twice by less than ten minutes.
- **Read upstream state before concluding why a branch is not moving.** A
  branch that looked unpromotable was already promoted and under review; the
  label three separate mechanisms key on is applied by hand, so it is the part
  most likely to be wrong.
- **A session that opens a pull request adds its item in the same turn.** Two
  pull requests existed in no plan at all for over a week, invisible to every
  dashboard and readiness check, while the roadmap wrote about them.

## Standing conventions

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small
  dataclass implementations, and strategies stay substitutable without touching
  the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in
  `test/krrood_test/dataset`.
- `plan_item_bootstrap.py` writes item fields at four-space indentation while
  these manifests sit at two, so `open`/`record`/`update`/`block` produce YAML
  that does not parse, and `save-plan.sh`'s error is swallowed by
  `capture_output`. Edit the manifest directly and say so. The fix is
  `plan-tracking-skills`' `plan-item-bootstrap-yaml-indent` (#160), unlanded.
- Subscribing to tracking issue #94 has been refused by the permission
  classifier in every container that has tried it, nine times. A skill relying
  on it for concurrent-change awareness should assume it will not work.
