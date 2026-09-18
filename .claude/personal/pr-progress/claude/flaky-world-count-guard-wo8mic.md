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
7. [done] Asked whether the per-worker check should also detect a leak as the
   *combination* of all workers rather than only thresholding each worker on its
   own; answered no (per-worker was always independent, never summed, both before
   and after the revert) and explained why a naive sum-and-threshold would be
   either redundant with the per-worker check (if scaled by worker count) or
   reintroduce the exact regression from step 6 (if not). Asked to build it anyway.
8. [done] Built the combined-across-workers check as a genuinely separate,
   additive mechanism (commit 211af96d9, merged with a routine main-sync in
   ac40bfb02 - no conflicts, unrelated files): `WorkerTally` (one process's final
   surviving-worlds breakdown, JSON round-trip) and `WorldTallyLedger` (a shared
   directory every process writes its tally into at `pytest_sessionfinish` and
   reads back from) in `living_worlds.py`; `LeakedWorldsAcrossWorkersError` when
   the summed total exceeds `MAXIMUM_LIVING_WORLDS * how-many-processes-reported`.
   Wired into `conftest.py`: `pytest_configure` clears the ledger once (the one
   process not itself an xdist worker, before any tally is written);
   `pytest_sessionfinish` records this process's tally and, on the controller (or
   the sole process of a non-distributed run), enforces the combined limit -
   caught and reported through the terminal reporter plus `session.exitstatus`
   rather than left to raise (which would otherwise surface as an internal error
   rather than a clean test-run failure). `collect_surviving_worlds()` factored
   out of `LivingWorlds.enforce_limit` so both the per-module and the
   session-finish path share one "collect garbage, drop the dead, read back what
   survived" step. 15 new unit tests (ledger record/read/clear, JSON round-trip,
   combined-limit pass/raise/ranking/empty-ledger) plus an actual multi-process
   verification: a small sandbox package run under real `pytest -n 2` confirmed
   the whole wiring (worker/controller detection, ledger clearing, sessionfinish
   ordering) end-to-end - passed when each worker's leak stayed under its share of
   the combined budget, failed with exit code 1 and the aggregate message when it
   didn't. This is the thing the unit tests alone could not have caught, per the
   lesson from step 6.
9. [done] Told the combined budget should be a flat total, not the per-worker
   figure times worker count (I had scaled it in step 8, same shape of mistake
   as the reverted step-6 divisor, just inverted). Commit 2de5219fb:
   `enforce_combined_limit`'s parameter renamed `limit_per_worker` ->
   `limit`, no more `* len(tallies)` - it now compares the summed total
   straight against one shared `MAXIMUM_LIVING_WORLDS` (30), whatever number
   of processes reported. Added a test pinning that two processes each within
   the per-module budget can still combine to more than the flat total, which
   is exactly what distinguishes this from the reverted shape. Updated every
   existing ledger test for the renamed parameter.
10. [next] **Needs real CI data, not a guess**: whether flat 30 actually holds
    once real xdist workers report their tallies in is unverified - CI on
    commit 2de5219fb has not run yet (heavy account-wide runner contention;
    commit ac40bfb02 before it never got a CI run at all, 0 statuses). If the
    real combined total comes back over 30, per direct instruction: raise
    `MAXIMUM_LIVING_WORLDS` to roughly double that *observed* number rather
    than inventing one - i.e. wait for the actual `LeakedWorldsAcrossWorkersError`
    (or a passing run) to report the true summed total, then act on that
    number. Also still open from step 9's predecessor: how to respond to Tigul
    upstream now that three different implementations of "depend on the
    workers" have been tried (reverted divisor, worker-scaled combined check,
    now flat-total combined check) - a decision for a human on the upstream
    thread, not something to guess a fourth time.

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
  Applied that lesson in step 8 by additionally verifying against real `pytest-xdist`
  multi-process runs in a throwaway sandbox, not only in-process unit tests.
