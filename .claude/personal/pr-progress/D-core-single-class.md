# rdr-refactor steward pass (2026-08-12)

No PR of its own: a steward pass, so the work landed on the plan's own stack
branches, not on `claude/rdr-refactor-steward-pass-uxewqh`.

## Plan (all three asks settled)

1. Cascade `main` (#41, merged 2026-08-10) through #63 → #64 → #65 → #66 → #67 → #98 → #159.
2. Unblock `D-core-support` (#67), frozen `dirty` since §14.
3. Decide the `check_dependency_readiness.py` / `mergeable_state` question.
4. Test §18's base-change hypothesis against #98's wedged CI.

## Done

- **Whole stack cascaded and pushed.** Nothing reads `dirty` any more; #159 is `clean`.
  Five of seven hops conflicted; the resolutions are recorded in roadmap §21 and in each
  item's `notes`.
- **#67 unblocked**: `dirty` → `unstable`, `needs-resolution` cleared (also cleared on #63).
- **#98's CI is unwedged** — 21 jobs, first run since 2026-07-30. §18's hypothesis holds in
  substance but not in mechanism: the base move alone queued nothing for eight minutes; the
  push after it is what triggered the run.
- **Readiness rule: decided as no-change**, with the reasoning and the residual refinement
  posted to workflow-unification's tracking issue #102.
- Verified locally throughout: `test_eql_rdr` 114 (at #67) / 164 (at #98 and #159),
  `test_eql` 1181 passed / 3 skipped, 0 failed everywhere.
- `plan.yaml` + `roadmap.md` §21 saved; dashboard republished (0 drift, 0 auto-corrections).
- Comments posted on #67, #98 and #102.

## Next / outstanding

- **#98's 21 CI jobs were still running** when this pass ended. Not watched — no
  subscription, no scheduled check, per standing rules. Worth a look when convenient.
- The only failure seen anywhere was `test_each_lib (random_events)` on #67: a `503`
  fetching `bazel.sh`, infrastructure rather than code.
- **`main`'s own two unfinished renames**, found by the cascade and deliberately not fixed
  here: `backward_inference.py:180,246` still say `ConclusionKnowledge` in docstrings, and
  `test_backward_inference.py:81-82` still name `what_do_we_know_about`.
- **`black` is not clean on the stack** and was not before this pass
  (`backward_inference.py`, `test_backward_inference.py`, `serialization.py`). Left alone.
- **#98 is out of draft** — the developer marked it ready, so the cascade merge was pushed
  but it was deliberately not re-drafted.
