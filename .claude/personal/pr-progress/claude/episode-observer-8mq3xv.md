## PR #316 - episode observer, recorded runs, record/ask scripts (base: #265 `claude/icra-experiments-simulation-pipeline-w4ep7n`)

Plan: observer + listener hook; EpisodeRecording keeps ticks/queries/artifacts; OperatorPrompt on REAL runs;
`record_episode.py` and `ask_episode.py` over StrEnum choices; both scripts run headless; then merge into #265.

Done:
- All six build items, tests in test/experiments_test, both scripts verified headless on `scene-stands-still`.
- Merged #265's updates (2026-09-11). Its ORMatic fix `WrappedTable.is_stored_as_a_value` replaces my
  one-line `type_endpoint not in type_mappings` guard; my krrood dataset/test for it was dropped as a duplicate.
- Two caplog failures in test_episode_recording.py and two in krrood feature_extraction fail on the base in this
  environment too (logging capture), untouched.

- Adapted test_episodes' `plan_id` assertion to `_plan_id` (main's #619 foreign-key rename reached #265; it failed there too).
- Pushed, PR body refreshed, merged into #265's branch as `d2a39f92b` (2026-09-11). #316 is MERGED; nothing left to do here.

Known limits (in the PR body): only scene-stands-still runs end to end on Tracy (PickUpAction is one-armed);
episode world not recorded (temp-file meshes); --record-bag not exercised.
