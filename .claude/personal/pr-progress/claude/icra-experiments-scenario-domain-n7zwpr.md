# icra-experiments / scenario-domain-model - PR #261 (draft, off main)

## Plan
1. `ConfidenceInterval` in `experiment_definitions`, beside `MeanAndStandardDeviation`.
2. New `experiments.scenarios` package: `ExecutionKind`, `StepName`, `ScenarioStep`,
   `Goal`, `Scenario`, `Condition`, `Perturbation`, `Trial` + typed log entries,
   `Metric`, `Report`, `ScenarioRunner`.
3. Tests first, against a trivial scenario over an in-test world that needs no simulator.
4. Migrate `control_loop_experiments` onto the model.
5. Keep the new modules out of the experiments ORM generation.

## Done
- All five steps, committed as cf877f711 and pushed; PR #261 description rewritten to
  match. 46 tests pass locally (the new scenario tests plus experiment_definitions').

## Next
- Nothing on this branch unless review asks for it. CI was still running when this
  session finished; the control-loop half is only import-and-collect covered there.

## Watch out
- This container cannot import the robot half of semantic_digital_twin (published
  probabilistic_model disagrees with the installed random_events, and the chain ends at
  ROS's `xacro`), and `test/conftest.py` pulls it in - so the new tests were run here
  from a scratch copy with PYTHONPATH set at experiments/krrood/semantic_digital_twin
  src. CI runs them properly.
- The control-loop tests that drive a runner are `@pytest.mark.slow` and CI skips them.
  Worth one manual benchmark run before that half is trusted.
- Next item in the lane, `episodes-recorded-through-ormatic`, decides which of
  `Trial`/`TrialLog` becomes a mapped record; the ORM ignore list here is deliberate.
