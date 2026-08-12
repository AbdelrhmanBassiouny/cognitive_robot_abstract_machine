
# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl`, now containing `main` (which carries
#139) and #151. Draft PR #154, head pushed 2026-08-12.
Sessions: https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g (built it, settled
the review round), https://claude.ai/code/session_01AYLtTRh7uZu64oLpMhGjQR (this one —
implemented parts A, B, C and E of that round's handover).

## Status: four of five parts done, part D not started

595 tests pass across the three directories CI runs, from 479. All five entry points
run standalone. Nothing is left uncommitted.

| handover part | state |
|---|---|
| A — rebase onto the parent chain | **done** (`abb7d994d`, `336b393e2`, `c3d0d1082`) |
| B — the escalation pipeline | **done** (`4e63b6fb3`) |
| C — mechanical threads | **done** (`375a9f013`) |
| D — CI as the verdict | **not started** — see below |
| new: only open-and-ready PRs | **done** (`fd008aa91`) |

## Three handover instructions had expired — check before following

#151 moved after the handover was written. Re-read the parent's tree before trusting
any of it:

- `GitCommandRunner` is `.claude/shared/git_commands.py`, not `maintenance_git_commands.py`
  (which now holds only `MaintenanceGitCommandRunner`).
- `maintenance_errors.py` is gone; it is `.claude/shared/exceptions.py`.
- `class_property.py` is deleted. The command base is `.claude/shared/command_line.py`'s
  `Command`, with abstract **instance** properties — not #139's `classproperty`.

## Part D — what it needs, and why it was not started

`build` pushes and exits printing the run URL; a separate subcommand reads the run's
conclusion; localisation pushes every prefix at once. Not begun because:

1. It needs a GitHub Actions client that does not exist in this tree. #146 measured
   that `actions/runs`, `jobs` and job-logs answer 200 from a session, but #146 is
   unlanded, so the client has to be written here.
2. It rewrites the localisation path that `escalate` (part B) now depends on, so a
   half-migration leaves the verdict path split across two mechanisms.
3. Its verification is a real CI run on a pushed branch. Everything else on this branch
   was verified against real git in the scratch fork; this cannot be.

`integration_test_command`, `--test`, `--no-test`, `TestCommandNotConfiguredError` and
`_run_tests` all still exist and all still work — part D is what removes them.

## What changed beyond the handover

- **Only reviewed work is carried.** `BranchStatus.is_out_of_draft` (covering `READY`
  *and* `IN_REVIEW`), read down the whole chain by `select_for_build`, because a tip
  contains its stack. Live board: 22 tips → 9. Everything left out is named in the
  report as `unreviewed`, and does not reach the `tip-left-out` exit status.
- **`integration-conflict`** is a second blocking label, read with `needs-resolution`
  through `Configuration.blocking_labels`; only `needs-resolution` is auto-cleared.
  `WithholdBranchStillConflicting` → `WithholdBlockedBranch`.
- **`integration.py escalate`** localises a break, labels the branch causing it, and
  comments naming what it breaks.

## If this is picked up again

- **Reply to and resolve the 28 threads.** All are addressed in code; none has an
  inline reply and none is resolved. Two must stay open with a reply: `r3758277971`
  (a GitHub issue per collision — answered *no* on 2026-08-12) and `r3758728157`
  (the `classproperty` ask, which #151 reversed by deleting the file).
- **#154's base ref is still #139's branch.** The base-field `PATCH` 403s through the
  agent proxy, so the reparent onto #151's branch is a manual step in the UI.
- Re-draft #154 after any push.
- The `greenlet` claim recorded here earlier is retracted; judge any `test_each_lib`
  red on its own evidence.

