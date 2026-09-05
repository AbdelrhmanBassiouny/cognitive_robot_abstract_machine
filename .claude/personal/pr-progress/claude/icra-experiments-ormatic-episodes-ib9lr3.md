## PR #271 — episodes recorded through ORMatic (`icra-experiments` lane 2 foot item)

Base #262 (`claude/montessori-results-recording-jnrgfy`), with #261
(`claude/icra-experiments-scenario-domain-n7zwpr`) merged in. Draft. Mode: auto.
Design rationale is in the plan's `roadmap.md`, section "2026-09-05: the episode model,
where it lives and what it records".

### Plan

1. `experiments/src/experiments/episodes/episode.py` — `Episode`, `RecordedTrial`, `Tick`,
   `RecordedQuery`, `AnsweredPredicate`, `InsertionAttempt`, `InsertionOutcome`,
   `FailureType` (empty `StrEnum` base), `FailureResolution`.
2. `experiments/src/experiments/episodes/recording.py` — moved from
   `montessori/results_recording.py`; records one `RecordedTrial` per commit through one
   shared `ToDataAccessObjectState` so the episode stays one row.
3. Delete `montessori/sorting_results.py` and its test; repoint
   `test_montessori_results_database.py`'s three `ShapeInsertionResultDAO` witnesses.
4. `scenarios/runner.py` — `ScenarioRunner` records each finished trial as it goes.
5. Tests: `test_episodes.py` (ORM round trip of a fully populated episode),
   `test_episode_recording.py` (two trials, one episode row; unreachable database records
   nothing), plus a runner-records-as-it-goes case in `test_scenarios.py`.

### Done

- Branch cut off #262, #261 merged clean, pushed; draft PR #271 opened.
- Manifest: `in_progress`, branch/session/PR recorded; roadmap section appended.

### Next

- Steps 1 to 5 above, tests first.
- Republish `/plan-dashboard icra-experiments` after the manifest write.

### Known and outstanding

- Nothing here runs in a session container: no `sqlalchemy`, no ROS, and the workspace
  does not install. ORM regeneration and every `experiments_test` module are CI-verified.
  Same limit #262 and #265 already recorded for this track.
- `ShapeInsertionExperience`, which the item's notes also ask to replace, is on no ancestor
  of this branch — it lives on the montessori demo branches only.
- `sorting_results.py` is also carried by #256 and #265; whichever lands after this takes
  the deletion.
