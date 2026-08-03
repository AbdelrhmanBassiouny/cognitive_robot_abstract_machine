# PR #109 - personal-settings-sync (workflow-unification)

Unblocked 2026-08-03 by `/plan-item-resolve workflow-unification
personal-settings-sync`, session
https://claude.ai/code/session_01XkWmfMzYYAaCsgyrHDuoKn, in commit `5281e3f3`.
The item had sat `in_progress` since 2026-07-31 with a manifest entry claiming
"open and ready" and no `blockers` recorded.

## Done

- **Merged `main`.** The conflict was a duplicated artifact, not drifting text:
  `main` had `ScratchRepository` (from #101's review round), this branch had
  `ScratchProject` - the same hook-test fixture under two names. Adopted `main`'s
  (a superset, already used by `test_check_setup_sh.py`) and deleted
  `ScratchProject`, so `conftest.py` and `test_save_plan_sh.py` are now
  byte-identical to `main` and have left the diff entirely. Third instance of
  this pattern in the plan after `POINTER.md`/`routine-prompt.md` and
  `BOARDLESS_COMMANDS`/`BOARD_FREE_COMMANDS`.
- **Ported `test_personal_settings_sync.py`** onto the `scratch_repository`
  fixture with a module-level `run_hook`, mirroring `run_check_setup`/
  `run_save_plan`. Picked up `run_check_setup`'s environment scrub, which the
  old fixture lacked.
- **Added `ScratchRepository.update_notes_branch_file`** (+ optional `cwd` on
  `run_git`) - the one thing `ScratchProject` could do that it couldn't.
- **The three review threads**: JSON literals moved to
  `tests/fixtures/personal-settings*.json`, read via `FIXTURES_DIRECTORY`.
  Replied on the PR and resolved all three.
- **README** section re-authored against `main`'s rewritten step-based guide:
  30 lines, down from 53.
- PR back to draft, `needs-resolution` dropped (`cram2-link-sent` kept), body
  refreshed, manifest + roadmap updated, dashboard republished.

## State

36 tests pass under `.claude/hooks/tests` (`main`'s 28 + this module's 8), 194
under `.claude/skills/plan-dashboard/tests`. `test_claude_dev_tooling` green on
`5281e3f3`. `mergeable_state: unstable` (mergeable; robotics jobs still running -
historically flaky and unreachable from a `.claude/`-only diff).

## Next

Nothing outstanding on my side. Waiting on the developer's own review - the PR
is a draft by convention until they have reviewed it.

**Note for whoever replies here next**: the three review threads belong to an
*unsubmitted pending review*. GitHub allows one pending review per user, so any
inline reply returns `422 - user_id can only have one pending review per pull
request` until that review is submitted. Use a PR-level comment instead, or
submit the pending review first.
