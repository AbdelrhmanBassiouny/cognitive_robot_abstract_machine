# PR #154 - `integration-branch` + `integration-branch-ci-verdict` (Part D)

Resolve run of 2026-08-28, session_01FWoysReVCQMi9VBY5cVgcP, mode `auto`.

## Plan

1. Resolve the merge conflict against `main`. **Done** - 157 commits behind, both
   `plan-item-*` SKILL.md files, additive on both sides.
2. Give `integration-conflict` its clearing condition: marker, plugin, targeted job,
   `clear-fixed-breaks`. **Done**, 705 tests pass from 675.
3. Candidate pull request, Actions/check-run reads, force-update of `integration` on
   green. **Blocked** - see below.
4. Remove `integration_test_command`, `--test`, `--no-test`,
   `TestCommandNotConfiguredError`, `_run_tests`; move `locate-failure` to dispatched
   runs. **Blocked on 3** - `build_integration` moves `integration` unconditionally
   today, so removing the local verdict before the CI one is proven leaves the branch
   never moving.

## Blocking

Rebuild cadence: scheduled, per-session, or gated on #154 landing. It decides whether
the candidate is opened by a workflow holding `INTEGRATION_REFRESH_TOKEN` or by a
session, so step 3 builds the wrong thing until it is answered. Recorded as the item's
`blockers` and put to the developer in the session chat.

## Also outstanding on the PR, unchanged by this run

- 6 unresolved review threads (the pull request's own description says 10; live count
  is 6). Three are this item's: the whole-CI thread, the "why does nothing remove this
  automatically" thread that step 2 answers, and the `classproperty` pair that #151
  reversed.
- `needs-resolution` is on the pull request. It should clear on the next pass that sees
  a clean merge, which the merge in this run is the first to make possible since 08-18.
- The pull request is out of draft, and re-drafting it would drop it from every
  integration build. Put to the developer rather than decided here.

## Next

Answer rebuild cadence, then step 3, then step 4.
