## Branch: claude/orm-interface-deduplication-uczwj4

**Goal**: the ORM build started one subprocess per generator, so every package of the
dependency chain was imported once per generator. Build them all in one interpreter.

**Base**: first written on the fork's main (90c24116), which is 86 commits behind
cram2/main and predates the ORM build rework. Rebuilt on cram2/main (3f643cff) after
the user pointed this out. Lesson: check the upstream remote before starting, not only
`origin`.

**Plan / status**
- [x] Run all generators in ONE child process (`cognitive_robot_abstract_machine/
      orm_generation.py`, `python -P -m ...`), not one per generator. A child rather
      than the caller's interpreter, because the conftests build interfaces and
      importing every package into the pytest process would change what tests see.
- [x] `importlib.invalidate_caches()` after each generator (interfaces are deleted
      before a build, so each writes a file its folder was scanned without).
- [x] Restore root logging around each generator.
- [x] Reorder to sdt -> giskardpy -> segmind -> coraplex -> experiments.
- [x] Declare each interface's dependencies as data on `OrmInterface`.
- [x] Failure names the package whose interface is missing (fixes --debug blame).
- [x] Tests in `test/cognitive_robot_abstract_machine_test` (existing CI matrix entry,
      no new job). 36 pass locally.

**Local test loop**: `PYTHONPATH="$PWD/krrood/src:$PWD" python -m pytest
test/cognitive_robot_abstract_machine_test --confcutdir=test/cognitive_robot_abstract_machine_test`
(the root test/conftest.py needs the full workspace, which the container lacks).

**Measurement**: 104.5 s -> 74.3 s mean over CI's four "Build ORM" steps, but that was
on the OLD base (fork main), where ci.yml still had that step. Not re-measured on
cram2/main, where the build happens inside the test run.

**PR**: #187 (draft) - shows 87 commits until the fork's main is fast-forwarded to
cram2/main. The real change is one commit, 02b6e671.

**Next**: waiting on the user's OK to fast-forward the fork's main to cram2/main
(0 ahead, 86 behind - a pure fast-forward). Not subscribed to PR activity (per notes).
