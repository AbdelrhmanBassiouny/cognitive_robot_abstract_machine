## claude/flaky-world-count-guard-wo8mic - world leak guard reports what leaked

**Problem (seen on #259):** `test/conftest.py`'s `count_worlds` is a module-scoped
autouse fixture that counts `objgraph.count("World")` at module teardown. pytest
attributes the failure to whichever test ran last (there: a three-line test creating
no world), and the message said "more than 20 worlds" while the check was `> 30`.

**Plan**
1. [done] Failing tests first: `test/cognitive_robot_abstract_machine_test/test_leaked_worlds.py`
   against a new `test/living_worlds.py` API - attribution per test, ordering, the
   before-any-test bucket, copies, boundary at the limit, reported limit == enforced limit.
2. [done] `test/living_worlds.py`: `LivingWorlds` records every world against the test
   running when it was created (replaces `World.__new__`, so copies and unpickles are
   recorded too), holds weak references, and `enforce_limit` raises `LeakedWorldsError`
   (a `DataclassException`) listing worlds-in-memory, the limit, and per-test counts.
3. [done] Wire it in `test/conftest.py`: watch in `pytest_configure` (before collection),
   name the current test in `pytest_runtest_setup`, module fixture renamed
   `check_for_leaked_worlds` calls `enforce_limit`. Dropped `objgraph`/`gc` use there.
4. [done] Formatted with `scripts/format_docstrings.py`.
5. [next] commit, push, open draft PR off main with the `bug` label.

**Verification notes**
- The workspace packages are not installed in this container (no `semantic_digital_twin`,
  no `objgraph`), so the repo suite cannot run here. The new module and its 9 tests were
  run in a sandbox copy under pytest 7.4.4 and 9.1.1, plus an end-to-end sandbox pytest
  session reproducing the conftest wiring against a stand-in `World`: the report named
  `test_that_leaks: 6`, the import-time world, and the deepcopied one, while the error
  still surfaced under the last (blameless) test - which is the point.
- CPython detail found while building this: a class that has ever been given `__new__`
  keeps dispatching through it, so watching cannot be undone; `LivingWorlds` documents
  that and has no `stop_watching`.
