# #111 `claude/shared-pr-state-chips` - plan-dashboards / shared-pr-state-chips

## Where it stands

Draft, based on #185 (`claude/plan-item-kickoff-workflow-cuare2`). `test_bastler`
green on head `9dc34b3a`; 730 tests pass locally in one invocation.

## What this session did (2026-09-03, /plan-item-resolve, auto mode)

The recorded blockers named the bastler dependency and a `main` conflict on #185.
Both were stale - #185's conflict had cleared, and #111 itself was green and
`clean`. The real stall was a review round from that morning that the manifest
never mentioned: seven threads, all naming rules.

Recorded the real blocker in `plan.yaml` and republished the dashboard *before*
resolving, then applied all seven in `9dc34b3a`:

- `bastler/pr_state.py` -> `bastler/pull_request_state.py` (+ its 3 test modules)
- `ci` -> `continuous_integration` on `BoardEntryKey`, `PullRequestDataKey`,
  `PullRequestLiveState`, `PullRequestRecord`
- `PullRequestDetailPayload` -> `PullRequestPayload`
- `PullRequestLabel.IN_REVIEW` / `.BUG` in place of literals;
  `BOARD_DOCUMENT_NAME` for `board.json`, swept across `test_maintenance.py` too

Eight threads replied to and resolved (six from this round, two from the round
before that this round superseded).

## What is next

1. **Open thread, waiting on the user**: whether the `"ci"` *value* behind the
   renamed `CONTINUOUS_INTEGRATION` members should change too. Left alone because
   it is the on-disk key in `board.json`/`pr_data.json`, read by `stack.py`'s
   pre-existing `ForkPullRequest.ci` and `maintenance_board.py`. Answering "yes"
   means renaming those two files' fields in the same pass.
2. Two threads from 2026-08-30 still waiting on the user: `GitCommandRunner` in
   tests, and the rebase-options discussion.
3. Still unimplemented and this item's own: the stack chip read from the pull
   request's native stack object (specified 2026-07-31).
4. Landing waits on #185.

## Gotcha worth not relearning

`format_docstrings.py` prints its decline message on the same line as the tqdm
progress bar, so `grep -v '^Formatting'` hides it. And check convergence *in the
repository* (a clean `git worktree`), never on a scratch copy - black reads its
line length from the nearest `pyproject.toml`, so a scratch copy reports a
conflict the real file does not have.
