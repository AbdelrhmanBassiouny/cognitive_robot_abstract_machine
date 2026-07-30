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

## Next
- When run 30578088164 completes: re-run its failed coraplex job (should go green);
  user can also click "Re-run failed jobs". No timed polling per personal notes —
  act on the next event or user ping.
- Candidate separate bug-fix PR (needs user approval to open): guard the coraplex
  conftest ORM regen from xdist workers (skip when `config.workerinput` is set),
  matching sdt's guarded pattern. One root cause, off main, `bug` label.
- Once green: PR is ready for the user to review/mark ready; the restack routine
  picks up #54/#14/#15 behind the new tip on its own.
