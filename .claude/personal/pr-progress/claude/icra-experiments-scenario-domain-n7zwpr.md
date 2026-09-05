# icra-experiments / scenario-domain-model - PR #261 (draft, off main)

## Plan
1. `ConfidenceInterval` in `experiment_definitions`, beside `MeanAndStandardDeviation`.
2. New `experiments.scenarios` package: `StepName`, `ScenarioStep`, `Goal`, `Scenario`,
   `Condition`, `Perturbation`, `Trial` + typed log entries, `Metric`, `Report`,
   `ScenarioRunner`.
3. Tests first, against a trivial scenario over an in-test world that needs no simulator.
4. Migrate `control_loop_experiments` onto the model.
5. Keep the new modules out of the experiments ORM generation.

## Done
- All five steps, committed as cf877f711.
- Review round 1 (four threads, all answered as asked, replied to and resolved),
  rebased onto the developer's own main merge and pushed as 05e982c2f:
  - `ExecutionKind` deleted for `coraplex.datastructures.enums.ExecutionType`; the
    field is `execution_type` on `Scenario`, `TrialStarted` and `Trial`.
  - `WorldType` bound to semdt `World`, `RobotType` to semdt `AbstractRobot`.
  - `TrialLog` owns the trial clock (`elapsed_seconds` off `time.monotonic`), which
    removes `perf_counter` and the four copies of the subtraction.
  - `ScenarioRunner` is now `Generic[ScenarioType, WorldType]` - the robot lives on
    the scenario's type, and a measuring runner can read the scenario it was handed
    without narrowing `perform_step`.
  - `BenchmarkScenario` builds the Giskard harness, holds it for the trial, and hands
    the runner `GiskardTester.world`.
- 46 tests pass locally (see below for how).

## Next
- Nothing on this branch unless review asks for it. CI not yet checked after 05e982c2f.

## Watch out
- The tests now import semdt `World` and `AbstractRobot`, which this container cannot
  import as-is. They run here from a scratch copy with PYTHONPATH over
  experiments/krrood/semantic_digital_twin/coraplex/giskardpy src *plus* two stub
  modules (`xacro`, `giskardpy_bullet_bindings`) in
  `<scratchpad>/stubs`. CI runs them properly.
- The control-loop tests that drive a runner are `@pytest.mark.slow` and CI skips them.
  Worth one manual benchmark run before that half is trusted - more so now that
  `build_world` returns the harness's world rather than the harness.
- Next item in the lane, `episodes-recorded-through-ormatic`, decides which of
  `Trial`/`TrialLog` becomes a mapped record; the ORM ignore list here is deliberate.
