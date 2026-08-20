## claude/fix-ci-failing-tests-202965 -> PR #183 (draft, `bug`)

The **ormatic PR**. Seven commits, head `df64ab60`:

- `a4990cfe` krrood: import scope past an unimportable module + unit test
- `a2385ec0` full-recovery regression test
- `6884cfcf` design B: ignore + untrack every interface, delete the guard
  machinery, build once per test run
- `d70a8d03` drop CI's redundant Build ORM step for test jobs
- `0ac188b0` tqdm bar, generator output captured, `--debug`
- `01be730e` build only where interfaces are read; bar counts classes
- `df64ab60` docstring/`__future__` stay first in a building conftest

**CI at `01be730e`: 2 red.**

1. `experiments` - **mine, fixed in `df64ab60`.** Its conftest opens with a
   module docstring *and* `from __future__ import annotations`; prepending the
   build pushed both down -> SyntaxError, whole package failed to collect. Only
   experiments_test has a future import; the other three open with `import os`.
   Now covered by `test_interface_building_conftests.py`, which compiles every
   building conftest and checks none lost its docstring. Verified it fails on
   the broken form. My local runs used `--noconftest`, which is exactly why this
   got through - remember that gap.

2. `semantic_digital_twin` - **not an assertion, a worker crash:**
   `worker 'gw0' crashed while running test_gazebo.py::
   TestSmallWarehouseWorld::test_world_is_valid` (1 failed, 1215 passed).
   Segfault/OOM signature in COLLADA mesh loading, which this PR does not touch.
   Green on `d70a8d03` and on main. **Not yet concluded - the `df64ab60` run is
   the second data point.** If it crashes again it is real and needs digging;
   do not write it off as a flake on one occurrence.

**Next.** Read the `df64ab60` run: confirm experiments collects, and see whether
the SDT gazebo worker crash reproduces. Not subscribed to any PR; no check-ins
armed.
