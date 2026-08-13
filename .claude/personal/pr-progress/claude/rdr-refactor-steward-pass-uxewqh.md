# rdr-refactor steward pass + PR #161 (2026-08-12/13)

Two pieces of work on this branch.

## 1. The steward pass (no PR of its own)

Landed on the plan's own stack branches. All three asks settled:

- **Whole stack cascaded** `main be377fdf` through #63 -> #64 -> #65 -> #66 -> #67 -> #98 -> #159.
  Nothing reads `dirty` any more; #159 is `clean`. Five of seven hops conflicted; resolutions
  in roadmap §21 and each item's `notes`.
- **#67 unblocked**: `dirty` -> `unstable`, `needs-resolution` cleared (also on #63).
- **#98's CI unwedged** — 21 jobs, first since 2026-07-30. §18's hypothesis holds in substance,
  not mechanism: the base move alone queued nothing for eight minutes; the push after it fired it.
- **Readiness rule: decided as no-change**, reasoning posted to workflow-unification's #102.
- `plan.yaml` + roadmap §21 saved; dashboard republished (0 drift, 0 auto-corrections).

## 2. PR #161 — finish the backward-inference rename (draft, `bug`)

The cascade surfaced two unfinished renames on `main` from #41. Five stale readers, not the
four first reported (`test_condition_resolver.py:5` was also stale):
`ConclusionKnowledge` -> `ConclusionSufficientConditionSets` (3 sites) and
`what_do_we_know_about` -> `get_conclusion_sufficient_conditions_from_a_rule_tree`
(a test name + its docstring).

- Test renamed for its **behaviour**, not the function it calls — naming it after the
  identifier is what let it go stale.
- `knowledge` left alone: still live vocabulary (`target_knowledge`, `current_knowledge`).
- **Not folded into the stack's base PR #63**, asked and answered by the mechanical test:
  `git ls-tree main` on the three paths is non-empty, so this is not a change to unlanded
  work — #41 introduced them and has merged. Propagation is identical either way since #63's
  base is `main`.
- Made **conflict-free against all four stack branches** by matching the docstring wrapping the
  stack already carries, so the cascade does not resolve the same fix twice. Measured, not assumed.
- Verified: 45 tests collected before and after, collected-name diff exactly the one rename;
  `test_eql_rdr` 45 passed, `test_eql` 1179 passed / 3 skipped / 0 failed.

## Next / outstanding

- **#161's CI was still running** when this ended. Not watched — no subscription, no scheduled
  check, per standing rules.
- **#98's 21 CI jobs were also still running.** Only failure seen anywhere was
  `test_each_lib (random_events)` on #67: a `503` fetching `bazel.sh`, infrastructure not code.
- **The stack still carries the stale names** in its own copies. Deliberate: the next cascade
  after #161 lands carries the fix up, conflict-free.
- **`format_docstrings.py` deviated a sixth time** (rewrote whole modules for a 6-line change);
  reverted, per the #41 precedent. `black` is still not clean on `backward_inference.py` /
  `test_backward_inference.py`, and was not before.
- **Importing the test suite rewrites two tracked files** — `dataset/ormatic_interface.py` and
  `test_verbalization/verbalization_results.py`. With a partial environment the regeneration
  *deletes* the coraplex / semantic_digital_twin DAOs. Kept out of both commits; a live trap,
  and a new instance of the tracked-and-regenerated class §17/§19 recorded for the PDFs.
- **#98 is out of draft** — the developer marked it ready, so the cascade merge was pushed but
  it was deliberately not re-drafted.
