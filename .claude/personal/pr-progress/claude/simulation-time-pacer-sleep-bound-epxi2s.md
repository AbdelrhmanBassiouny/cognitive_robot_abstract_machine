## Outstanding for whoever takes it further
- **Branches above #256 need a one-line change.** `franka_montessori_demo.py` and the two
  smoke tests set `context.simulation_clock = lambda: multi_sim.simulator.current_simulation_time`;
  that lambda has no `.time`. It becomes a `SimulationClock` over the simulator, whose
  `state` already tells `PAUSED` from `STOPPED`. Nothing on #256 sets the field, so #256
  itself is unaffected.
- **#169's description still lists this under Outstanding.** Its base now fixes it.
- Explicitly out of scope, unchanged: `_execute_real` has no budget at all, and the
  0.2 ms poll interval is still a busy-wait.
