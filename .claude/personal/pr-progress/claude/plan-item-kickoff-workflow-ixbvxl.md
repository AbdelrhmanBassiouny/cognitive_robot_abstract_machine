# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl`, containing `main` (which carries #139)
and #151. Draft PR #154, head pushed 2026-08-13.
Sessions: https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g (built it),
https://claude.ai/code/session_01AYLtTRh7uZu64oLpMhGjQR (parts A/B/C/E),
https://claude.ai/code/session_01RhwNdD7ChskkomV1TCiRLU (this one — the 08-13
review round; Part D split out).

## Status: the code is done; Part D is now a separate item

599 tests pass across the three directories CI runs, from 595. All five entry points
run standalone. Nothing uncommitted. `mergeable_state` clean against `main`.

**Part D is no longer this branch's work.** `integration-branch-ci-verdict` is a new
plan item stacked on this one — the CI verdict, plus the two things review added to it
(a stable/candidate branch pair, and a pytest marker with a job that runs only what it
marks). `integration_test_command`, `--test`, `--no-test`,
`TestCommandNotConfiguredError` and `_run_tests` all still exist here and all work;
that item is what removes them.

## The 08-13 round, seven threads

| thread | outcome |
|---|---|
| labels as a `StrEnum` | done — `DefaultLabel`, one contract test pinning the wire spelling |
| rename `semantic break` | done — `IntegrationTestFailure` (see below) |
| rename `escalate` | done — `block-branch` |
| join the failure methods into a class | done — `IntegrationTestFailure` + `FailureLocation` |
| `unreviewed` as a status with a `carried` bool | done, **left open** — the inheritance edge is not literal |
| `UnreviewedBranch` onto `Branch` | unified into the outcome type, **left open** — pushed back on `Branch` |
| pytest marker + targeted CI job | **left open** — became the new item |
| (carry-over) whole-CI | **left open** — became the new item |

Two carry-over `classproperty` threads stay open too: #151 reversed the ask by deleting
`class_property.py`.

## Three things worth carrying

**`TestFailure` is a name pytest penalises.** The user proposed it; a module-scope class
named `Test*` in a test file is collected, and `test_integration.py` imports these names
directly — `PytestCollectionWarning: cannot collect test class`. `TestCommandNotConfiguredError`
escapes it only because the tests reach it through the module. Hence `IntegrationTestFailure`.

**A review reply promised a test that was never written.** The earlier round's reply on the
report-keys thread described `test_the_report_keys_are_the_ones_a_caller_parses` in detail;
it did not exist. Found by renaming a wire key and noticing nothing failed. Grep for anything
a reply claims to have added before resolving the thread.

**`ci.yml` triggers on `push` to `main` and `pull_request` only.** So a pushed integration
branch gets no CI unless a pull request exists for it — which is why the stable/candidate
design is the only shape that reaches a verdict, and is the first fact the new item needs.

## If this is picked up again

- The base stays `main`. Reparenting onto #151's branch is *possible* (the MCP tool does it;
  only raw `curl` 403s) and *wrong today* — #151 is 159 behind `main`, and basing on it took
  the diff from 45 files to 261. Correct once #151 merges `main`.
- `needs-resolution` is stale; the maintenance pass clears it itself.
- Re-draft #154 after any push. It is a draft now.
- A `main` merge (#543, the ORM-interface change) landed on this branch from outside the
  session mid-round. Merged and the whole suite re-run rather than trusted.
