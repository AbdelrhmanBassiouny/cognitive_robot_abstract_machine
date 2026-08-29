## Investigation: the scheduled Integration refresh times out after an hour

**Status**: diagnosis done, nothing implemented yet, no branch pushed, no PR.

### What happens
Runs 2, 3 and 4 of `Integration refresh` (33232698252, 33242242230, 33250116115)
all end with `the candidate's checks had not finished after an hour`. Every poll in
the loop reports `"verdict": "absent"` - not one check run was ever reported against
the candidate's head.

### Cause
`SettleCandidateCommand.run` (.claude/stack/integration.py, ~line 1731) closes the
candidate whenever the verdict is not RUNNING:

    if checks.verdict is not CandidateVerdict.RUNNING:
        fork.close_pull_request(candidate.number)

ABSENT is not RUNNING, and ABSENT is exactly what a candidate opened two seconds ago
looks like. So the first poll closes the pull request before GitHub has created its
`pull_request` run, and no check ever attaches to the head. Every later poll reads
ABSENT, `_verdict_exit_code` maps ABSENT to CANDIDATE_STILL_RUNNING (13), and the
shell loop waits out its 60 attempts.

Evidence: candidates 209, 212, 213 were each closed 2s after opening and have zero
runs of ci.yml or integration-checks.yml. Candidate 204 was closed 3s after opening
and its runs were created 1s after the close - it won the race, went RUNNING, and
ended with a real verdict (14, candidate-failed). The `mergeable_state: dirty` on the
three is not a real conflict: `git merge-tree origin/integration <head>` merges clean.

The same line is on the unification branch (#211), which is where the loop now lives
as RefreshPipeline._await_verdict.

### Fix, in three parts
1. Close only on a settled verdict (PASSED/FAILED). Derive it from one place shared
   with `_verdict_exit_code` so the two cannot disagree about ABSENT again.
2. Give ABSENT a bounded warm-up in the waiting loop, then stop with a status that
   says no check ever started (points at the trigger/token, not a slow matrix)
   instead of an hour-long wait ending in a misleading timeout message.
3. Tests first: settle-candidate leaves an ABSENT candidate open; the pipeline stops
   on ABSENT past its warm-up.

### Scope
`.claude/stack/integration*.py` and `.github/workflows/integration-refresh.yml` do
not exist on `main` - #154 introduces them and #211 (stacked on #154) rewrites the
loop. So this is a change to unlanded work, not a new PR: it folds into #211 unless
the user says otherwise.

### Landing hazard
The fork's default branch is `integration`, so the schedule runs the copy of the
pipeline that lives on `integration` - which only updates when a build publishes,
which is what is broken. The fix has to be pushed to `integration` by hand, or
validated first by `workflow_dispatch` on the fix branch.

### Next
Awaiting the user's decision on which branch to fix on before implementing.
