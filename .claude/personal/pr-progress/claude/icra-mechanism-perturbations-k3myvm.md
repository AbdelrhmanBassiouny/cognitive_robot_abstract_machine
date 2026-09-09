PR #305, base `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265) — per the
developer, cut off #265 directly rather than off `main`/#296, since #265 already
carries the scenario domain model, montessori scenarios, and simulated-camera
perception setup this item needs even though none of #261/#296/#298 are literal
ancestors of it (#265's own convergence pass folded them in by hand).

## Plan

Four `Perturbation[World]` instances (`experiments/montessori/perturbations.py`, new):
- `TargetHoleMoved` — world-state perturbation, same mechanism as
  `SortingScene.stand_the_piece_at`.
- `PieceShoved` — world-state perturbation, reuses the existing `PushThePiece` pusher.
- `PerceivedPoseOffset` / `DetectionRelabelled` — perception-result perturbations. No
  Montessori scenario step takes an actual look today (`ANSWER` reads `InsideOf`
  ground truth directly), so this item adds a `LookAtTheScene` step built on #265's
  own `simulated_setup.py` (`camera_over_the_table`/`perception_pipeline`, confirmed
  already live-capture-capable — `simulated-camera-feeds-perception` is further along
  than the manifest's `not_started` suggests). The two perception perturbations write a
  small world-registered distortion marker `LookAtTheScene` reads and clears, since
  `apply(world)` has no other channel to reach whatever backend a later step uses.
- Every `Perturbation` gains `instruction_for_a_person() -> str` on the shared base in
  `experiments/scenarios/scenario.py` (`LightingChanged` implements it too), per the
  item's own notes about the real-robot protocol.
- `simulated_setup.py`'s `table_surface`/`lid_surface`/`camera_over_the_table`/
  `perception_pipeline` move from taking `montessori_world: MontessoriWorld` to
  `world: World` (no caller outside their own test; nothing in their bodies needs more
  than `get_semantic_annotations_by_type`), so the look step can call them from
  `apply`/`perform`'s raw `World`.

## Done so far

- Fixed an unrelated tooling bug hit while recording this item
  (`plan_item_bootstrap.py`'s indentation constants). The developer reviewed #305 and
  correctly called out that this didn't belong there (own-PR/bug-label convention) —
  **split into its own PR, #306, based on `main`, labeled `bug`**. Reverted the fix
  commit off `claude/icra-mechanism-perturbations-k3myvm` (a "Revert ..." commit, not a
  history rewrite, since the branch was already pushed/public). Replied to and resolved
  the review thread; replied to the "no perturbation code yet" comment. #306 is draft,
  untouched since.
- Bootstrapped the branch, opened PR #305, recorded `plan.yaml` (in_progress,
  branch/PR/session) and the roadmap section above.
- Done: `simulated_setup.py`'s four functions now take `world: World`
  (`beff1237a`..`b673ec883`, pushed); `test_montessori_simulated_camera.py`'s ~10 call
  sites updated to pass `.world` through. **Not run against the real MuJoCo pipeline
  yet** — this container's system Python has no numpy/mujoco/casadi etc.; the montessori
  perception suite needs the same from-scratch Python 3.12 venv `snapshot-working-memory`
  (#301) built (mujoco, casadi~=3.7.0, opencv, scikit-image, piqp, transforms3d, trimesh,
  rustworkx, random_events/probabilistic_model from local wheels, xacro/
  giskardpy_bullet_bindings stubs, libegl-mesa0, `MUJOCO_GL=egl`). Only `py_compile`
  syntax-checked so far.

## Next

- Build (or reuse, if still on disk) that scoped venv before writing anything that needs
  to actually run — this signature change alone is UNVERIFIED beyond syntax.
- Implement `TargetHoleMoved`, `PieceShoved` (world perturbations) with tests, TDD.
- Build `LookAtTheScene` step + the world-registered distortion marker; implement
  `PerceivedPoseOffset`/`DetectionRelabelled` with tests.
- Add `instruction_for_a_person()` to `Perturbation` + `LightingChanged`.
- Run the full montessori/scenarios/perception test suite, format docstrings, push.
