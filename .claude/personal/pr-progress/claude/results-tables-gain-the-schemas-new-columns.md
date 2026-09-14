Branch claude/results-tables-gain-the-schemas-new-columns, stacked on #378
(claude/the-lid-found-by-how-high-it-stands). Bug-fix draft PR #379, label bug. Found on the
robot 2026-09-14: pickup_demo_real --record (with perturbations) failed recording the episode:
UndefinedColumn "_landing_region_id" of relation "ApertureDAO".

Plan: a lasting results database gains the columns the schema added since.
- [x] cause: ResultsDatabase._prepared_sessions -> metadata.create_all only creates missing
      tables; lab DB drifted by 3 columns (ApertureDAO._landing_region_id,
      BoardDetectorDAO.lid_standing_height, PlaceActionMujocoDAO._grasp_description_id)
- [x] test first: TestOpeningADatabaseRecordedToEarlier (sqlite, ApertureDAO rebuilt without
      the column + one row) failed before the fix
- [x] fix: _add_missing_columns before create_all; ALTER TABLE ADD COLUMN nullable, FK via
      AddConstraint where dialect.supports_alter; never drops anything
- [x] test_montessori_results_database.py 35 passed
- [x] applied to the lab Postgres by opening a session: 3 columns + 2 FKs added, 103 trials
      kept, no column missing (7 NullType-excluded tables stay absent, as before)
- [x] commit 80c03ccad6 pushed, draft PR #379 with bug label
- [ ] user reruns pickup_demo_real --record with this branch checked out in ~/bass
- still open elsewhere: #378 rerun of framework demo; cube-evidence feature follow-on
  (worktree ~/bass/cram-board-by-the-cube, files also in scratchpad/feature_files)
