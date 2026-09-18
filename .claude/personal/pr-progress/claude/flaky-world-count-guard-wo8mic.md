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
10. [done] Asked to get rid of the magic number entirely and know the *expected*
    count instead of guessing one. Answered: the real answer is knowable - a
    world is expected to survive past its own test exactly when a fixture
    whose scope outlives a single test (module/package/session) is why it
    exists; everything else still alive at module end has no such excuse.
    Asked to build it and prove it actually catches real leaks.
11. [done] Built and validated the fixture-scope-owner redesign (commit
    8489a2579), replacing `MAXIMUM_LIVING_WORLDS` entirely:
    - `FixtureScope` (`living_worlds.py`) names a pytest scope and says whether
      it `outlives_a_single_test`. `LivingWorlds.ignore_worlds_created_here()`
      is a nesting-safe context manager stopping `record()` while active. A new
      `pytest_fixture_setup` hookwrapper in `conftest.py` wraps a durable-scope
      fixture's setup with it. `enforce_limit`'s default budget is now `0`.
    - Validated against a **real, separate pytest run** (the `pytester` plugin,
      now enabled via `-p pytester` in `pytest.ini`), not just unit tests - and
      it caught two real bugs the unit tests could never have shown:
      (a) checking at the original module-scoped fixture's teardown flagged
      the *last* test of every module using a function-scoped fixture, leak or
      not, since pytest keeps a finished test's own fixture arguments
      referenced on its item until the next test starts setting up - fixed by
      deferring the check to the next module boundary (moved into
      `pytest_runtest_setup`) plus `pytest_sessionfinish` for the last module,
      both reporting through the terminal reporter + exit status rather than
      raising (which would misattribute to an unrelated next test); (b) with
      that fixed, a real leak's own module reported correctly but the *next*
      module then reported the *same* stale leak again as its own - fixed by
      marking a `WorldCreation.reported` once raised (`newly_surviving_worlds()`
      excludes it from later per-module checks; the combined-across-workers
      ledger still counts it via the unfiltered `surviving_worlds()`, since
      the memory is genuinely still there).
    - New permanent regression coverage:
      `test_leaked_worlds_pytest_integration.py` runs three real isolated
      pytest sessions via `pytester` against a stand-in conftest mirroring the
      real hooks (`dataset/pytest_fixture_scope/`), proving: a durable
      fixture's world is never flagged, a genuine leak is caught and named,
      and an already-reported leak does not recur for a later module - none of
      which the existing in-process unit tests could verify, since they only
      exist at the level of how pytest itself schedules fixture/item teardown.
      Plus new unit tests for `ignore_worlds_created_here()` and the zero
      default in `test_leaked_worlds.py`. All 27 tests pass locally.
12. [done] "Ci has alot of failures" on commit 8489a2579's first real CI run
    (run 35403465461): `ConftestImportFailure: AttributeError: module pytest
    has no attribute FixtureDef`, breaking collection for every lib.
    `pytest_fixture_setup`'s `fixturedef: pytest.FixtureDef` annotation isn't
    part of pytest's public API in the version CI pins (7.4.4) - confirmed by
    downloading the real 7.4.4 wheel and checking its `__init__.py`:
    `FixtureRequest`/`Pytester`/`StashKey`/`ExitCode` are public,
    `FixtureDef` is not. My local pytester-based validation had used pip's
    pytest 9.1.1, which does expose `FixtureDef` publicly, masking this the
    whole time. Fixed with `from __future__ import annotations` in
    `conftest.py` (commit 26686b87b) - it was the one touched file missing
    it. Verified precisely against the extracted 7.4.4 package directly (not
    the sandbox's 9.1.1), then re-ran every unit and pytester-integration
    test for this guard under a real pytest 7.4.4 install (via a throwaway
    venv + sandbox mirroring the dataset tree): all pass.
13. [done] That fix exposed a second, narrower collection bug in the same CI
    run: `dataset/pytest_fixture_scope/leaking_test.py` matches pytest's own
    default `*_test.py` collection pattern, so the real suite collected and
    ran it directly in every lib whose job covers this tree - not only
    through the isolated `pytester` copy `test_leaked_worlds_pytest_integration.py`
    makes of it - and its `test_that_leaks_a_world` failed for real with
    "fixture 'function_world' not found" (that fixture only exists in the
    nested run's stand-in conftest). Renamed to `leaking_module.py` (commit
    37cbf0a61); confirmed under the sandbox that `pytest test/ --collect-only`
    no longer picks it up directly, and the isolated-run tests still pass.
14. [next - needs a human decision] With both of those fixed, CI now collects
    and runs everywhere, and surfaces a real, systemic finding rather than a
    guard bug: the combined-across-workers check (budget 0) reports worlds
    still alive at session end in every lib that draws on
    semantic_digital_twin's world fixtures, roughly proportional to how much
    of that fixture suite each lib's tests touch: semantic_digital_twin 25,
    giskardpy 14, coraplex 9, robokudo 3, segmind 2, experiments 1. These
    land in the same range this session's own step-6 investigation already
    called "legitimate session-scoped residual" (PR2/HSR/apartment/kitchen
    worlds) - which `ignore_worlds_created_here()` is meant to exempt but
    evidently isn't fully catching for this codebase's real fixture graph
    (suspect: fixtures with several layers of session-scoped dependencies,
    e.g. `pr2_apartment_world` depending on
    `_pr2_world_setup`/`_apartment_world_setup` - read but not run, since the
    workspace packages aren't installed here). Documented in the PR
    description's new "CI round" section. Left open rather than guessed at a
    fifth time, per the same reasoning as the worker-count question below -
    needs either a deeper dive into the exemption mechanism against this
    specific fixture graph, or a decision on an interim non-zero combined
    budget grounded in this real data.
15. [next] Still open from step 9's predecessor: how to respond to Tigul
    upstream about the original "depend on the workers" ask, now that it has
    been answered four different ways (reverted per-worker divisor,
    worker-scaled combined check, flat-total combined check, and removing the
    threshold concept entirely) - a decision for a human on the upstream
    thread, not something to guess a fifth time.

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
