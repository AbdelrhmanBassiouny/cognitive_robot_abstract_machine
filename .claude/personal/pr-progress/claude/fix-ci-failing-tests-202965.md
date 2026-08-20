## claude/fix-ci-failing-tests-202965 -> PR #183 (draft, `bug`)

The **ormatic PR**. Six commits:

- `a4990cfe` krrood: import scope past an unimportable module + unit test
- `a2385ec0` full-recovery regression test
- `6884cfcf` design B: ignore + untrack every interface, delete the guard
  machinery, build once per test run
- `d70a8d03` drop CI's redundant Build ORM step for test jobs
- `0ac188b0` tqdm bar, generator output captured, `--debug`,
  `OrmGenerationFailedError`
- `01be730e` build only where interfaces are read; bar counts classes

**CI was all 15 green** at `d70a8d03`. Re-running for `01be730e`.

**Measured cost that drove `01be730e`.** Root conftest ran for every session, so
the 7 libs that never read a mapping paid ~99s each (min 88, max 106) for a
build they never touched. Now only `semantic_digital_twin_test`,
`coraplex_test`, `giskardpy_test`, `experiments_test` build - the only four
that reference a workspace interface (`krrood_test` uses its own dataset one,
generated in-process by its own conftest). `regenerate_orm_interfaces` is
`@cache`d so a multi-package run builds once.

**Per-class bar.** Profiled a real generation: `ClassDiagram(...)` is ~95% of
the time, `make_all_tables()` ~0% - so instrumenting the table pass would have
given a bar that never moves. Progress is emitted from
`ClassDiagram._create_association_relations`, the per-class loop that resolves
field types. Generators run as subprocesses, so krrood carries the protocol
(`krrood/class_diagrams/progress_report.py`) - krrood may not import cram, so
it has to live there and cram imports it. Env var `KRROOD_REPORT_CLASS_DIAGRAM_
PROGRESS` turns emission on; the parent pipes stdout+stderr, routes progress
lines to the bar and keeps the rest for the failure report. `--debug` sets no
env var and does not pipe, so logging stays live and there is no bar.

**Not validated locally:** the real generators (no robotics env here). Both
halves are covered by real code - krrood's emission against a real ClassDiagram,
cram's reading against a dataset generator calling krrood's real
`report_progress` - but the join only runs in CI.

**Still open, user's call:** nothing outstanding. Not subscribed to any PR; no
check-ins armed.
