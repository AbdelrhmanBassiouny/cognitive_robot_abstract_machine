# SimulationTimePacer.sleep() is unbounded

**Status:** investigated; stopped for the developer's policy decision. No code
written yet, no branch re-cut, no PR.

## What the hazard actually is

`SimulationTimePacer.sleep()` (`giskardpy/src/giskardpy/executor.py`) polls
`simulation_clock()` every 0.2 ms until simulated time reaches the next cycle,
with no bound. `Executor.tick_until_end` calls it inside its tick loop, so the
loop's only bound - a tick count - is never reached while `sleep()` blocks, and
its `finally` cleanup never runs.

Introduced by **#256** (`montessori_monitor_and_recording`, open draft, based on
#244 `sdt_segmind_krrood_from_fast_monitor`), not by #169 - #169 inherited it and
lists it under Outstanding. It is not on `main`.

## Facts that decide the policy

- The clock is `MultiSim.simulator.current_simulation_time`, advanced by the
  simulator's own thread only while `SimulatorState.RUNNING`.
- `SortingRunControl._pause()` calls `pause_simulation()` immediately when the
  console asks, not at a checkpoint, so **the clock freezes mid-motion** while
  the sorting thread is inside `tick_until_end`. A paused run is supposed to
  block here.
- `STOPPED` is terminal: `stop()`, viewer close (`VIEWER_IS_CLOSED`), a
  constraint (`MAX_REAL_TIME` / `MAX_SIMULATION_TIME` / `MAX_NUMBER_OF_STEPS`),
  or an exception on the sim thread. After it the clock never advances again.
- So a wall-clock deadline alone **cannot tell a deliberate pause from a dead
  simulation**; both look like "time stopped".

## Next

1. Developer picks the policy (raise / wall-clock fallback / warn-and-continue,
   or the clock-state option that distinguishes pause from death).
2. Developer picks the base branch to cut
   `claude/simulation-time-pacer-sleep-bound-epxi2s` from - it currently
   descends from `integration`, which is not a legal PR base.
3. Failing test first in `test/giskardpy_test/test_executor/test_pacer.py`
   (no `SimulationTimePacer` test exists today), then the fix.

Explicitly out of scope: `_execute_real` having no budget at all, and the
0.2 ms poll interval's busy-wait.
