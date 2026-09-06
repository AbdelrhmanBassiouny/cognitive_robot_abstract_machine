# SimulationTimePacer.sleep() is unbounded

**Status:** done and pushed. Folded into **#256** (`montessori_monitor_and_recording`,
commit `9f3686d68`) rather than opened as its own PR - #256 is what introduces
`SimulationTimePacer`, and removing these edits leaves nothing that stands alone. No new
PR; #256's description was updated to match.

## What the hazard was

`SimulationTimePacer.sleep()` polled `simulation_clock()` until simulated time reached
the next cycle, with no bound. `Executor.tick_until_end` calls it inside its tick loop,
so the loop's only bound - a tick count - was never reached while `sleep()` blocked, and
its `finally` cleanup never ran.

## The policy the developer chose

Option D: distinguish a held simulation from a dead one, rather than any wall-clock
deadline. A deadline cannot tell them apart - `SortingRunControl._pause` freezes the same
clock mid-motion and blocking there is correct - so the pacer now takes a
`SimulationClock` reporting both the time and whether the simulation has stopped. A pause
is waited out; a stop raises `SimulationStoppedError`.

## What landed

- `giskardpy/src/giskardpy/simulation_clock.py` (new): the `SimulationClock` ABC.
- `giskardpy/data_types/exceptions.py`: `SimulationStoppedError`.
- `giskardpy/executor.py`: the pacer binds to `SimulationClock`; `_wait_for_the_next_cycle`
  reads `has_stopped` before `time`, so a cycle completed just before the stop still counts.
- `coraplex/datastructures/dataclasses.py`: `Context.simulation_clock` carries the type.
- `test/giskardpy_test/test_executor/test_pacer.py`: 5 new tests, 12 passed.

## Verification actually run

A partial workspace was assembled from PyPI under Python 3.12. The pacer tests run with
`--noconftest`, since without `rclpy` the ORM pre-flight in `giskardpy_test/conftest.py`
cannot walk `Ros2Executor`. The hang was reproduced first against the old pacer (`sleep()`
on a frozen clock still running when killed at 20 s); the same scenario now raises.

## Outstanding for whoever takes it further

- **Branches above #256 need a one-line change.** `franka_montessori_demo.py` and the two
  smoke tests set `context.simulation_clock = lambda: multi_sim.simulator.current_simulation_time`;
  that lambda has no `.time`. It becomes a `SimulationClock` over the simulator, whose
  `state` already tells `PAUSED` from `STOPPED`. Nothing on #256 sets the field, so #256
  itself is unaffected.
- **#169's description still lists this under Outstanding.** Its base now fixes it.
- Explicitly out of scope, unchanged: `_execute_real` has no budget at all, and the
  0.2 ms poll interval is still a busy-wait.
