# icra-experiments / scenario-domain-model - PR #261 (draft, off main)

## Plan
1. `ConfidenceInterval` in `experiment_definitions`, beside `MeanAndStandardDeviation`.
2. New `experiments.scenarios` package: `ExecutionKind`, `StepName`, `ScenarioStep`,
   `Goal`, `Scenario`, `Condition`, `Perturbation`, `Trial` + typed log entries,
   `Metric`, `Report`, `ScenarioRunner`.
3. Tests first, against a trivial scenario over an in-test world that needs no
   simulator: step order, conditions applied before the steps, a perturbation firing at
   its step, repetitions, the trial log, the report's numbers and its rendering.
4. Migrate `control_loop_experiments`: `BenchmarkScenario` becomes a `Scenario`; its
   runner becomes a subclass of the model's `ScenarioRunner`; `benchmark.py` and the
   benchmark test follow the move of plotter mode / target frequency onto the scenario.
5. Keep the new modules out of the experiments ORM generation (as the control-loop
   scenario modules already are).

## Done
- Branch cut from main, draft PR #261 opened, manifest + roadmap section recorded.

## Next
- Write the tests, then the model.

## Watch out
- This container cannot import the robot half of semantic_digital_twin (the published
  probabilistic_model wheel disagrees with the installed random_events), and
  `test/conftest.py` pulls it in, so the new tests are run here from a scratch copy with
  PYTHONPATH set; CI runs them properly.
- The control-loop tests that drive a runner are `@pytest.mark.slow` and CI skips them,
  so the benchmark migration is only import-and-collect covered. Say so on the PR.
