## Fix: the scheduled Integration refresh closed its own candidate

**Status**: implemented, committed and pushed as `59380858` on
`claude/plan-item-kickoff-workflow-unification-wg4w4x` (PR #211, still a draft).
Folded into #211 rather than opened as its own branch, since the files it changes
exist only on #154 and #211.

### Cause
`settle-candidate` closed the candidate on any verdict that was not RUNNING, and
ABSENT is what a candidate opened two seconds ago looks like - GitHub creates a
pull request's run a moment after the request is opened. The first reading closed
it, no run was ever created, every later reading found the same absence, and
`_verdict_exit_code` answered ABSENT as still-running so the loop waited out the
hour. Candidates 209, 212, 213: no run of ci.yml or integration-checks.yml at all.
204 was closed after three seconds instead of two, its runs were created one second
later, and it is the only build this pipeline has judged. `mergeable_state: dirty`
on the closed three is not a conflict - the merge is clean locally.

### What was changed
1. `ChecksVerdict.has_settled` - the close and the exit status now read one property,
   so they cannot disagree about ABSENT again.
2. `RefreshPipeline` gives an absent check a warm-up (5 readings) instead of the whole
   schedule, then stops with `CANDIDATE_UNCHECKED` (17). `_ask_repeatedly` is the one
   loop both waits are built from.
3. Found while fixing: a candidate left open would be merged into the next build -
   it is out of draft, unblocked and not red, which is everything `select_for_build`
   asks. Measured, not assumed. The stack is `work_in_flight` now: every open pull
   request except one opened against the branch the build would replace.

839 tests across the four CI directories, from 835. Four new tests, each written first.

### Done besides the code
PR #211's description carries a section on this round; the `workflow-unification`
manifest and roadmap have it under `red-candidate-localisation`; the dashboard was
republished.

### Outstanding - the user's call
The schedule runs the pipeline copy on the fork's default branch, which is
`integration`, and that only updates when a build publishes. So the fix reaches the
schedule by a `workflow_dispatch` of Integration refresh on this branch, or by a hand
push to `integration`. Neither was done: a dispatch is a real rebuild that publishes
on green.
