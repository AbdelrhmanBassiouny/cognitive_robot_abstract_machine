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

**Measurement** (clean, same base commit both sides, n=7, 13 min apart): the
examples-and-demos "Build ORM" step went 102.0 s -> 68.3 s mean (main run 32567616992
vs PR run 32567072596), about 34 s / 33 %. Spread narrowed from 80-120 s to 64-79 s.

**PR**: #187 (draft), CI green (23/23). Base main is now fast-forwarded to cram2/main
(3f643cff) - the user did it - so the branch is one commit, 7 files, on top of it.
GitHub's PR page may briefly still show the 86 upstream commits until it recomputes
the merge base.

**Next**: waiting on the user's OK to fast-forward the fork's main to cram2/main
(0 ahead, 86 behind - a pure fast-forward). Not subscribed to PR activity (per notes).
