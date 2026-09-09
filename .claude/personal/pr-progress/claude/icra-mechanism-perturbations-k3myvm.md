**PR #305 is CLOSED (unmerged) — this session's job on it is done.** Closed by the
developer's direction. Do not reopen it or push further commits; a future session
starts fresh per "When your PR's job ends".

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

## What happened

- Fixed a tooling bug hit while recording this item (`plan_item_bootstrap.py`'s
  indentation constants) — but the fix was **wrong**: it hardcoded the flush-left
  convention (`icra-mechanism`/`icra-foundation`'s own) as universal, when at least
  seven other plans use the opposite convention (`/plan-create`'s own 2-space
  marker/4-space fields). Split it into its own PR (#306) per the developer's request,
  then the developer's session found **#302** already had the *correct* fix (derive the
  indent from the block being patched, correct for either convention) and closed both
  #305 (this item's PR — the wrong fix was still on it via a revert commit, plus no
  perturbation code had been written) and pointed at closing #306 too (done).
- `simulated_setup.py`'s `world: World` signature change (real prep, not itself wrong)
  is stranded on the now-closed #305. **Verified working** in a from-scratch venv built
  this session via `/usr/local/bin/uv sync --extra dev` (the older `uv` on `PATH`
  couldn't parse this repo's `pyproject.toml`) plus `apt-get install libegl1
  libegl-mesa0` for offscreen MuJoCo rendering — `test_montessori_simulated_camera.py`
  runs against the real pipeline in it. Building the ORM interfaces
  (`experiments`→`coraplex`→`giskardpy`) additionally needs `rclpy` (ROS2 Jazzy), which
  this container does not have and installing is a much larger undertaking than this
  session attempted — CI runs this in a full `ros:jazzy` Docker image
  (`.github/docker/Dockerfile`), which is the reproducible way to get it, not an ad-hoc
  apt install here.
- `plan.yaml`: `perturbations` set to `blocked` (on #302 merging), roadmap section
  added recording all of the above. Dashboard republished.

## Next (for whichever session picks this up)

- Wait for #302 to merge, or branch from its fix directly.
- Re-open work from `claude/icra-mechanism-perturbations-k3myvm` (still on the remote)
  or a fresh branch off #265 — **do not** reintroduce `beff1237a`/its revert.
- The design in roadmap.md's "`perturbations` cut off #265..." section still stands:
  four `Perturbation[World]` instances (`TargetHoleMoved`, `PieceShoved`,
  `PerceivedPoseOffset`, `DetectionRelabelled`), the `LookAtTheScene` step, a
  world-registered distortion marker, `instruction_for_a_person()` on the shared base.
  Only the implementation is outstanding — the design work does not need redoing.
- The `simulated_setup.py` `world: World` change is worth cherry-picking or redoing
  (it's small); it's verified working.
