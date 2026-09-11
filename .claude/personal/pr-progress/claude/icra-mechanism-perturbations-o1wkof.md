# icra-mechanism / perturbations — PR #311

Replaces #305 (closed unmerged: duplicate wrong tooling fix, no perturbation code).
Branch `claude/icra-mechanism-perturbations-o1wkof`, cut fresh off #265
(`claude/icra-experiments-simulation-pipeline-w4ep7n`). Carries no `.claude/` tooling
change — that was the whole reason #305 was closed.

## Plan

Design was settled on 2026-09-09 and is not being re-derived. Four `Perturbation[World]`
subclasses plus the look step that makes two of them reachable:

1. `Perturbation.instruction_for_a_person()` on the shared base in
   `experiments/scenarios/scenario.py`; existing `LightingChanged` implements it too.
2. `TargetHoleMoved`, `PieceShoved` — act on the world directly, via the placement-as-state
   mechanism `SortingScene.stand_the_piece_at` already uses.
3. `LookAtTheScene` step — captures a frame through `SimulatedCamera` and reads it with
   `MontessoriPerceptionPipeline`. No Montessori step takes a real look today
   (`SortingStep.ANSWER` reads `InsideOf` off ground truth), so this is what the two
   perception perturbations need.
4. `PerceivedPoseOffset`, `DetectionRelabelled` — register a marker on the world that
   `LookAtTheScene` reads and clears after distorting its look.

Tests first, one per perturbation, asserting the change it names against the twin's state
or the returned `MontessoriScene` rather than rendered text.

## Done

- Branch re-cut off #265 (its predecessor descended from `integration`, not a valid base).
- Cherry-picked `b673ec883` from #305 — `simulated_setup.py` builders take `World` rather
  than the `MontessoriWorld` builder, which the look step needs.
- Draft PR #311 opened; `plan.yaml` recorded (`in_progress`, branch, PR, session) and the
  roadmap section appended; stale blockers replaced.

## Next

- Write the failing tests, then the implementation, in the order above.
- Run the `experiments` scenario tests; they need a MuJoCo-capable env (#301's session
  built a Python 3.12 venv with `uv sync --extra dev` plus `libegl1`/`libegl-mesa0` — this
  container starts without it).

## Outstanding / known

- Needs restacking onto `tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands.
- #302 (the correct `plan_item_bootstrap.py` indent fix) is still open. Not blocking: the
  plan tooling here is run from a detached worktree pinned at the clone's starting commit,
  whose script already derives the indent. Nothing tooling-related goes on this branch.
