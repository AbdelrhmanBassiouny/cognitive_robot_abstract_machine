## PR #262 (`claude/montessori-results-recording-jnrgfy`) - resolve pass

Task: "Resolve pr 262", which carried two blocking labels: `needs-resolution`
(stale merge against `main`) and `integration-conflict` (semantic break
reported against PR #261, `claude/icra-experiments-scenario-domain-n7zwpr`).

Done:
- Checked out the PR's actual head branch (not this session's scratch branch,
  which descends from `integration` and can't be a PR base) and merged
  `origin/main` into it. The only real conflict was
  `test/experiments_test/conftest.py`, where `main`'s side of the hunk was
  empty and ours held the whole fixture block - resolved by keeping our
  content. Verified none of PR 262's own files (the `montessori/` modules,
  the four ORM declarations) were touched by the merge. Pushed
  (`d7d4e633dc`). PR's `mergeable_state` is now `unstable` (was `dirty`), so
  the `needs-resolution` label should clear on the next maintenance pass.
- Re-drafted the PR after pushing (it was ready-for-review via automated
  promotion - `cram2-link-sent` - not a human flip, so the standing
  re-draft-after-push rule applies).
- Investigated the `integration-conflict` (PR 262 vs PR 261): confirmed the
  two merge cleanly (reproduced locally: `main` + PR 261 + PR 262 merges with
  no conflicts, including both branches' independent edits to
  `experiments/scripts/generate_orm.py`), and found no class-name or contract
  collision between `experiments.montessori.*` and `experiments.scenarios.*`.
  The `integration_test_command` in `.claude/stack/stack.toml` is only the
  dev-tooling suite (`.claude/stack`, `.claude/hooks`,
  `.claude/skills/plan-dashboard` tests), which neither branch touches, so
  that can't be what the original block-branch comment's "the suite fails"
  refers to - it must be the real CI/candidate suite, which needs a
  ROS-enabled environment this sandbox does not have (same limitation PR
  262's own description already documents for `regenerate_all_orm.py`).

Not done / left open:
- Could not reproduce the actual semantic failure between PR 261 and PR 262
  to reach an `adapt`/`reconcile`/`sequence` verdict - needs a ROS-capable
  environment or a real candidate-PR CI run. Left the `integration-conflict`
  label in place (correctly never auto-clears) rather than guessing at a fix.

Next: once a ROS-enabled environment or a fresh candidate build is available,
re-run `locate-failure`/`locate-candidate-failure` against this pair to find
the actual break, then apply the appropriate verdict from
`integration-conflict-triage`.

## Follow-up: real CI failure on the `test_each_lib (experiments)` job

After the push above, the user reported a failing CI check. Pulled the actual
job log (run 35401713657, job 105782863025) rather than guessing:
`test/experiments_test/test_montessori_sorting_results.py::test_events_are_persisted_under_their_own_attempt`
failed with `AttributeError: 'ShapeInsertionAttemptDAO' object has no
attribute 'plan_id'. Did you mean: '_plan_id'?`.

Root cause: unrelated to PR 261 or the integration-conflict label. `main`'s
`b3faf503c2` ("Fixed a naming clash issue in ormatic interfaces", landed
2026-09-11, after PR 262 branched) renamed every generated one-to-one/many-
to-many FK column with a leading underscore (`wrapped_table.py`'s
`create_one_to_one_relationship`), specifically so a real domain field of the
same name is never shadowed - confirmed by that commit's own
`test_field_name_clash.py` and by `test_eql.py`'s own call sites, which it
migrated from `.parent_id`/`.child_id`/etc. to `._parent_id`/`._child_id`.
Merging `main` into PR 262 (the needs-resolution fix above) brought that
rename in, so `test_montessori_sorting_results.py`'s pre-existing
`.plan_id` assertions - written before the rename existed - went stale.

Fix: renamed `plan_id` -> `_plan_id` in the three assertions, matching the
exact migration pattern `test_eql.py` already used for the same rename.
Pushed as `3a437c060c`. PR is still draft (per the redraft-after-push rule);
`mergeable_state` is now `clean`.

Not verified: could not run pytest locally (no ROS, and this environment's
pip installs of the workspace's own heavy dependency set time out), so this
fix is confirmed correct by reading the generator's own source and its own
test precedent, not by re-running the suite. Left for the next CI run or the
user to confirm.
