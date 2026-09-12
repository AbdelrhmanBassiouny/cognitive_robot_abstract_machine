# PR #345 - ground truth from the scenario, not the twin

Branch `claude/ground-truth-from-scenario-f9lgaa`, based on
`claude/icra-experiments-simulation-pipeline-w4ep7n` (#265). Draft PR #345, description
current.

## Done

1. Failing cases in `test/experiments_test/test_working_memory_ground_truth.py`, verified
   to have scored right under the old twin-read ground truth.
2. `SceneAsSetUp` / `PlacedObject` / `TrueAnswer` (`BodiesNamed`, `PlacesPutAt`) in
   `questions/question.py`; `QuestionedThings` carries the account; `values_agree`
   dispatches to a true answer that judges itself.
3. Grounded: ObjectsSeen, ObjectPlaces, SupportingSurfaces, SideOfAnotherObject,
   HeldInTheHand. Twin-read with a docstring saying why: ObjectColours, PlaceOfOwnBody,
   NumberOfOwnParts.
4. `WatchedSortingRun.scene_as_set_up` at `trial_started`; on the robot the pieces come
   from the person (`Person.answer`, `NobodyIsThereToAsk`).
5. `RecordedTrial.instructions_carried_out`; `ask_episode.py
   --rescore-working-memory`.
6. Updated `test_questions.py`, `test_tracy_montessori_scene_builder.py` and the two
   tracy pickup demos.

## Next

- Full `test/experiments_test` sweep is running locally; fix anything it turns up.
- Watch CI on #345 only if asked - this session does not subscribe to PRs.

## Notes

- Local env: `uv sync --extra dev` with a newer uv (`/tmp/uvnew/bin/uv`); a `_ros_stub`
  in `.venv/lib/python3.12/site-packages` stands in for the ROS python packages the CI
  image has. Run `scripts/regenerate_all_orm.py` once, then
  `xvfb-run -a .venv/bin/python -m pytest ... --orm-build=never`.
- Open question for the developer: `HOW_FAR_A_PLACE_MAY_DIFFER = 0.01` m is my number,
  and `HeldInTheHand` now scores a failed grasp wrong because the script says the piece
  is held.
