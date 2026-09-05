## PR #271 — episodes recorded through ORMatic (`icra-experiments` lane 2 foot item)

Base #262 (`claude/montessori-results-recording-jnrgfy`), with #261 merged in. Draft.
Mode: auto. Design rationale is in the plan's `roadmap.md`, section "2026-09-05: the
episode model, where it lives and what it records", and in #271's description.

### Done

- Branch cut off #262, #261 merged clean, pushed; draft PR #271 opened.
- Manifest: `in_progress`, branch/session/PR recorded; roadmap section appended; dashboard
  republished.
- `episodes/episode.py` — `Episode`, `RecordedTrial`, `Tick`, `RecordedQuery`,
  `AnsweredPredicate`, `InsertionAttempt`, `InsertionOutcome`, `FailureType` (empty
  `StrEnum` base), `FailureResolution`.
- `episodes/recording.py` — moved from `montessori/results_recording.py`; commits one
  trial each through one shared `ToDataAccessObjectState`, plus `EpisodeRecording`, the
  runner subclass that records each finished trial.
- `scenarios/runner.py` — no-op `trial_finished` hook, so the scenario model needs no
  episode import.
- Deleted `montessori/sorting_results.py` and its test; repointed
  `test_montessori_results_database.py`'s three DAO witnesses at `RecordedTrialDAO`;
  renamed the conftest fixture to `experiments_database_session`.
- Tests: `test_episodes.py` (ORM round trip of a fully populated episode),
  `test_episode_recording.py` (one episode row across two trials, per-trial commit,
  unreachable database records nothing, `EpisodeRecording`), two runner-hook cases in
  `test_scenarios.py`.
- `format_docstrings.py` run on every modified file. Committed and pushed; description
  rewritten to match.

### Next

- Nothing outstanding in this session. CI is the first real run of any of it.

### Known and outstanding

- Nothing here executes: no ROS, and the workspace does not install (`random_events` needs
  a native library; its PyPI build fails too). Verification was static — parse, workspace
  import resolution, and reading the ORMatic paths the new fields rely on. Same limit #262
  and #265 recorded for this track.
- `ShapeInsertionExperience`, which the item's notes also ask to replace, is on no ancestor
  of this branch; it lives on the montessori demo branches only.
- `sorting_results.py` is also carried by #256 and #265; whichever lands after this takes
  the deletion.
