# PR #55 — agreement slice (eql-performatives plan, item `agreement`)

## Done (2026-07-30, resolve session)
- Merged `origin/main` (52f4f745, includes eql-verbalization P2 #86/#87 and P3 #475)
  into this branch as merge commit c6ab6db8, resolving the three-file conflict.
- Root cause: main's P2 grew its own eager `apply_subject_verb_agreement`; unified
  onto this branch's `AgreementProcessor` pass design — `concord_number` stamps
  upstream (coreference + `clause()`, incl. main's coordinated-subject feature as a
  build-time stamp), the pass derives agreement, the caller-less duplicate helper and
  `_with_agreed_copula` deleted from main's side.
- Verified locally: targeted verbalization tests 42 passed; full
  `test/krrood_test/test_eql/` 1139 passed, 3 pre-existing skips.
- Replied to the routine's needs-resolution comment, removed the `needs-resolution`
  label, updated the PR body; PR remains a draft.
- plan.yaml: `agreement` → in_progress, blockers cleared; roadmap.md updated.

## CI triage (2026-07-30, same session, post-restack)
- The restack routine merged the newest main (0fd14357, incl. #486/#405/#463) as
  a38550fe on top of c6ab6db8. Its run 30578088164 failed `test_each_lib (coraplex)`.
- Diagnosis (commented on the PR): flaky race in coraplex's test bootstrap —
  `test/coraplex_test/conftest.py::pytest_configure` regenerates
  `coraplex/orm/ormatic_interface.py` in the controller *and* every xdist worker
  (`pytest -n auto`), so concurrent processes rewrite + ruff-format the same file;
  ruff died mid-file ("Expected a statement" at 23646) on a partially written copy.
  Branch delta cannot affect coraplex ORM inputs; checked-in file parses on both
  refs; main's coraplex was green on 52f4f745 and its 0fd14357 run passed the
  crash window.
- `rerun_failed_jobs` refused while run 30578088164 is still in progress.

- Second failure on the same run: `test_each_lib (giskardpy)` — confirmed red on
  the base branch too (main's 0fd14357 run fails byte-identically: 1 failed +
  8 errors, all DAiSy tests, `xacro.XacroException: package 'ur_robot_driver' not
  found`). Cause: #405 added ur-robot-driver/ur-client-library as system deps but
  the jazzy CI image hasn't been rebuilt (`update_docker.yml`). Base-side fix;
  commented on the PR (part 2).

- Third failure, same run: `test_each_lib (semantic_digital_twin)` — also base-red
  (main's 0fd14357 sdt job failed): the pre-existing multi-sim physics-settling
  flake (already red on main 52f4f745, 07-29) + the same missing `ur_robot_driver`
  (`test_world_pr2.py::test_robots_and_validate`). Commented on the PR (part 3).
- Run 30578088164 completed; queued re-run of failed jobs (20:3x). Expected:
  coraplex green (confirms the regen-race theory), giskardpy/sdt red again until
  the image rebuild.
- Re-run sdt result (20:48): failed again but only on the multi-sim physics flake
  (`test_world_sim_state_sync`, same assertion); the `ur_robot_driver` test passed
  this attempt (ordering/environment-dependent). Predicted duplicate — no new PR
  comment. coraplex + giskardpy re-runs still in progress.

## 2026-08-02: restack onto 9b090fc1, one new base-red (part-4 comment)
- Routine restacked again: head b9ac0cf0 merges main 9b090fc1 (#402
  semdt_specifications_rewrite, #484 screw-model, #488-#490).
- All 07-30 issues resolved on run 30760567495: coraplex green (regen race did
  not recur), giskardpy green (image rebuild delivered ur_robot_driver), krrood
  green. 12/13 jobs green.
- Single red: sdt `test_multi_sim.py::test_builder_assigns_material_to_every_
  geom_sharing_a_texture` + `test_builder_does_not_confuse_different_textures_
  sharing_a_basename`, both `assert '' != ''` (empty material names), failing
  deterministically. Base-red: main's own 9b090fc1 run fails byte-identically as
  its only red job; main was green on 82501888 (07-31), so the regression came in
  with the #402 merge. Commented on the PR (part 4).

## 2026-08-05: restack onto 7a3639a2; #402 regression fixed on main; notebook flake
- #402 texture/material regression resolved: main green on 08-03 (b52da84d).
- Routine restacked: head a1ba9140 merges main 7a3639a2 (#497-#499/#501/#503/#505).
- Notebooks/demos run 31013925964: single red, coraplex test_notebook_examples.sh,
  `RuntimeError: Kernel didn't respond in 60 seconds` after 3 notebooks passed —
  kernel-startup infra flake (job green on both prior runs; PR touches no
  notebooks). Commented on the PR (part 5).
- Matrix run 31013925756 on the same head still in progress, 7/13 green, no
  failures so far.

## Next
- When the notebooks run finishes: re-run its failed job (rerun refused while
  in progress). Act via events or user ping — no timed polling.
- If the matrix run completes green + notebook rerun green → fully green head;
  PR ready for user review/mark-ready. The restack routine handles #54/#14/#15.
- Candidate separate bug-fix PR (needs user approval to open): guard the coraplex
  conftest ORM regen from xdist workers (skip when `config.workerinput` is set),
  matching sdt's guarded pattern. One root cause, off main, `bug` label.
- Once green: PR is ready for the user to review/mark ready; the restack routine
  picks up #54/#14/#15 behind the new tip on its own.
