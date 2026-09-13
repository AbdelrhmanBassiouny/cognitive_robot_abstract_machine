# PR #345 - ground truth from the scenario, not the twin

Branch `claude/ground-truth-from-scenario-f9lgaa`, based on
`claude/icra-experiments-simulation-pipeline-w4ep7n` (#265). Draft PR #345, `bug`
labelled, description current, four commits.

## Done - the whole ask

1. Failing cases in `test/experiments_test/test_working_memory_ground_truth.py`,
   verified to have scored right under the old twin-read ground truth.
2. `SceneAsSetUp` / `PlacedObject` / `TrueAnswer` (`BodiesNamed`, `PlacesPutAt`) in
   `questions/question.py`; `QuestionedThings` carries the account; `values_agree`
   dispatches to a true answer that judges itself.
3. Grounded: ObjectsSeen, ObjectPlaces, SupportingSurfaces, SideOfAnotherObject,
   HeldInTheHand. Twin-read with a docstring saying why: ObjectColours, PlaceOfOwnBody,
   NumberOfOwnParts.
4. `WatchedSortingRun.scene_as_set_up` at `trial_started`; on the robot the pieces come
   from the person (`Person.answer`, `NobodyIsThereToAsk`, `UnknownPieceNamed`).
5. `RecordedTrial.instructions_carried_out`; `ask_episode.py --rescore-working-memory`.
6. Fallout fixed: `ObjectsSeenCard` reads the twin it draws; `test_questions.py`,
   `test_tracy_montessori_scene_builder.py`, `test_paper_robot_query_cards.py`, and the
   two tracy pickup demos.

## Outstanding when I stopped

- CI on #345 was still queued. Not watched (no PR subscriptions in this fork).
- Two open questions for the developer, both in the PR description:
  `HOW_FAR_A_PLACE_MAY_DIFFER = 0.01` m is my number, and `HeldInTheHand` now scores a
  failed grasp wrong because the script says the piece is held.
- Follow-up: the two tracy pickup demos still state their scene with
  `SceneAsSetUp.read_from`, which is a twin read.

## Notes

- Local env: `uv sync --extra dev` with a newer uv (`/tmp/uvnew/bin/uv`); a `_ros_stub`
  in `.venv/lib/python3.12/site-packages` stands in for the ROS python packages the CI
  image has. Run `scripts/regenerate_all_orm.py` once, then
  `xvfb-run -a .venv/bin/python -m pytest ... --orm-build=never`. Every sandbox failure
  outside this diff is that stub (`get_package_share_directory`).
