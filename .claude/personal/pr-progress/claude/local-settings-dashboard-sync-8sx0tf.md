# Plan

Two asks, one branch:

1. Sync a personal `settings.local.json` off the personal-notes branch the way
   CLAUDE.local.md already is, seeded with a rule allowing the Artifact tool
   without prompting.
2. Add a personal-notes rule: republish a plan's dashboard whenever any session
   changes that plan's data.

# Done

- `resolve-personal-notes-config.sh`: `PERSONAL_SETTINGS_PATH`,
  `LOCAL_SETTINGS_RELATIVE_PATH`/`LOCAL_SETTINGS_JSON`, the sync-stamp path, and the
  `personal_settings_are_locally_modified`/`record_personal_settings_sync` helpers.
- `session-start.sh`: copies the branch's settings into `.claude/settings.local.json`
  unless it changed locally since the last sync (Claude Code writes its own
  "don't ask again" grants there), plus a `local settings:` summary line.
- New `save-personal-settings.sh`, delegating commit/push to
  `write-personal-notes-file.sh` and re-stamping afterwards.
- Tests: scratch-project fixture extracted into `conftest.py` as a `ScratchProject`
  class (shared with the save-plan.sh tests); `test_personal_settings_sync.py` covers
  both halves. `.claude/hooks/tests` + `plan-dashboard/tests` all green (24 + 187).
- `.gitignore` for the settings file and the stamp; hooks README section, safety
  bullets, and intro updated.
- Committed and pushed to `claude/local-settings-dashboard-sync-8sx0tf`.
- Personal-notes branch: `.claude/personal/settings.local.json` allowing `Artifact`,
  and the "always republish the dashboard when plan data changes" rule under
  "Keeping plan state current".

- Draft PR #109 opened on the fork, subscribed to its activity.
- CI: `test_claude_dev_tooling` green (the job covering this PR's changes); everything
  else green except `test_each_lib (semantic_digital_twin)`, which fails on
  `test_multi_sim.py::test_world_sim_state_sync`. Identical failure on `main` at this
  PR's base commit 52f4f74, so it is pre-existing, not ours - said so in a PR comment
  and did not bundle a fix.

# Next

- React to PR #109 events as they arrive (no scheduled polling, per notes). Keep it a
  draft after any push; mark ready only when told to.
- If the sim failure is worth chasing, it wants its own `bug`-labelled PR off `main`:
  the box settles in z but never moves in x/y, so the sim never picks up the
  connection-origin update.
