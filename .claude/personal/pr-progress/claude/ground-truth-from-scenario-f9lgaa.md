# PR #345 - ground truth from the scenario, not the twin

Branch `claude/ground-truth-from-scenario-f9lgaa`, based on
`claude/icra-experiments-simulation-pipeline-w4ep7n` (#265). Draft PR #345.

## Plan

1. [done] Failing cases in `test/experiments_test/test_working_memory_ground_truth.py`.
2. `SceneAsSetUp` / `PlacedObject` / `TrueAnswer` (`BodiesNamed`, `PlacesPutAt`) in
   `questions/question.py`; `QuestionedThings` carries the account; `values_agree`
   dispatches to a true answer that judges itself.
3. Grounded questions: ObjectsSeen, ObjectPlaces, SupportingSurfaces,
   SideOfAnotherObject, HeldInTheHand. Twin-read with a docstring saying so:
   ObjectColours, PlaceOfOwnBody, NumberOfOwnParts.
4. `WatchedSortingRun` builds the account at `trial_started` from `starting_layout` and
   the script; on the robot the pieces come from the person (`Person.answer`).
5. Record the instructions carried out on the trial; re-scoring path in
   `ask_episode.py`.
6. Update `test_questions.py`'s scene to state what it stood; update the two tracy
   pickup demos' question sets.

## Notes

- Local env: `uv sync --extra dev` with a newer uv (`/tmp/uvnew/bin/uv`); a `_ros_stub`
  in `.venv` stands in for the ROS python packages the CI image has. Run tests with
  `xvfb-run -a .venv/bin/python -m pytest ... --orm-build=never` after
  `scripts/regenerate_all_orm.py`.
