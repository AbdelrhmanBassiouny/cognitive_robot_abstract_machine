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
5. [done] committed, pushed, PR #267 opened off main with the `bug` label:
   https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/267
   (not opened as a draft by this session - it pre-existed from an earlier one, already
   promoted to upstream cram2#646).
6. [done] Round 1 review response (Tigul on upstream #646, two asks):
   - "Module level variable" on `test_leaked_worlds.py`'s `FINISHED_MODULE`: moved
     `FINISHED_MODULE`/`LEAKING_TEST`/`TIDY_TEST` off the module into a
     `StandInTestNames` fixture. Landed clean, commit c082bb42c.
   - "the maximum number of worlds should not be static but depend on the amount of
     xdist workers": implemented as `MAXIMUM_LIVING_WORLDS // worker_count` via a new
     `default_limit()` reading `PYTEST_XDIST_WORKER_COUNT` (commit c082bb42c) - **this
     broke CI**: `test_each_lib (semantic_digital_twin)` and `test_each_lib
     (giskardpy)` failed with ~49 `LeakedWorldsError`s, none real leaks. Each xdist
     worker is a separate process with its own object graph; how many worlds survive
     in one worker is driven by which session-scoped world fixtures that worker
     happened to build (PR2/HSR/apartment/kitchen etc., legitimately 18-25 residual),
     not by the total worker count - so dividing the budget by worker count doesn't
     track anything real, it just shrinks an already-tight threshold. Reverted in
     commit aca39e582; flat `MAXIMUM_LIVING_WORLDS` default restored, the 3 tests for
     the worker-split behavior removed, `PYTEST_XDIST_WORKER_COUNT` enum member
     removed (unused after the revert). Documented the finding in the PR description's
     "Review round" section since this session cannot comment on the upstream PR.
7. [next] **Needs the developer's call, not this session's**: how to respond to Tigul
   upstream about the worker-count ask, since the literal implementation is
   technically unsound for this design (see above) - a different way to honor the
   spirit of the request, or a reply explaining why it doesn't apply, is a decision
   for a human on the upstream thread. CI on commit aca39e582 was queued as of last
   check, not yet confirmed green.

**Verification notes**
- The workspace packages are not installed in this container (no `semantic_digital_twin`,
  no `objgraph`), so the repo suite cannot run here. The new module and its tests were
  run in a sandbox copy under pytest 7.4.4 and 9.1.1, plus an end-to-end sandbox pytest
  session reproducing the conftest wiring against a stand-in `World`: the report named
  `test_that_leaks: 6`, the import-time world, and the deepcopied one, while the error
  still surfaced under the last (blameless) test - which is the point.
- CPython detail found while building this: a class that has ever been given `__new__`
  keeps dispatching through it, so watching cannot be undone; `LivingWorlds` documents
  that and has no `stop_watching`.
- Real CI is the only signal that caught the worker-count regression - the sandbox
  copy has no `semantic_digital_twin` session fixtures to exercise, so it couldn't have
  shown this. Worth remembering next time a "should depend on X" review ask touches
  this guard: verify against real CI before calling it done, not just the unit tests.
