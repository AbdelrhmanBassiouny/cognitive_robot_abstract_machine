## `/plan-item-resolve workflow-unification plan-item-execution-modes`

This branch opens no PR of its own. It is a resolve/planning session for
`workflow-unification` item `plan-item-execution-modes` (fork PR #149, promoted
upstream as cram2 #537). The implementation belongs on the item's own branch,
`claude/plan-item-kickoff-modes-p1yuwc`.

### Plan
Answer LucaKro's 2026-08-19 changes-requested review on cram2 #537 (six threads,
all on `.claude/hooks/plan_item_mode.py`), push the changes they justify to the
item branch, record the round in the plan, and split the one cross-file naming
problem out as its own item.

### Done
- Installed the missing dashboard dependencies (`markdown`, `nh3`);
  `check-setup.sh` now exits 0.
- Gathered the item's state: `plan.yaml`, `roadmap.md` (execution-modes section
  plus the precedent rounds), #149's CI and review threads, tracking issue #102.
- Read #537's six review comments via `WebFetch` - this session cannot reach
  cram2's API at all (`add_repo` refuses a cross-owner attach; api.github.com
  403s), which is the gap item `upstream-review-reader` (#146) exists to close.
- Wrote the resolution plan: `/root/.claude/plans/ancient-forging-hummingbird.md`.
- Two user decisions taken: push fixes only and hand over reply text (no writes
  to cram2, per AGENTS.md); fix the serialization naming in this PR's own file
  only and record the cross-file rename as a new item.

### Next
- Await approval of the plan, then implement on
  `claude/plan-item-kickoff-modes-p1yuwc`: `ModeSetting`/`SettingsFile` types,
  a `Report` ABC, `ExitCode.USAGE`, the stale `ask`-is-the-default docstring,
  and a member-to-wire-value contract test.
- Record the round in `roadmap.md` + `plan.yaml`, `save-plan.sh`, republish
  `/plan-dashboard workflow-unification`.
- New item `report-document-naming` on `personal-data`, announced on issue #102.
- Hand over six per-thread reply texts for #537.

### Outstanding / flagged
- #149's only red check is `test_each_lib (semantic_digital_twin)` ->
  `test_world_sim_state_sync`, a physics settle assertion, on a PR whose ten
  files are all under `.claude/`. Not this PR's failure.
- `plan.yaml` has no field for a promoted upstream PR, so #537 will be recorded
  in `notes` and `roadmap.md` rather than as a new schema field.
