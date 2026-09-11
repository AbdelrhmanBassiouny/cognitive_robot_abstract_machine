# icra-mechanism / perturbations — PR #311

Replaces #305 (closed unmerged: duplicate wrong tooling fix, no perturbation code).
Branch `claude/icra-mechanism-perturbations-o1wkof`, cut fresh off #265
(`claude/icra-experiments-simulation-pipeline-w4ep7n`). Carries no `.claude/` tooling
change — that was the whole reason #305 was closed.

## Plan

Design settled 2026-09-09 in roadmap.md; not re-derived. Four `Perturbation[World]`
subclasses plus the look step that makes two of them reachable.

## Done

- Branch re-cut off #265 (its predecessor descended from `integration`, not a valid base).
- Cherry-picked `b673ec883` from #305 — `simulated_setup.py` builders take `World`.
- Draft PR #311 opened; `plan.yaml` recorded (`in_progress`, branch, PR, session), roadmap
  section appended, stale blockers replaced; dashboard republished (version 10).
- `Perturbation.instruction_for_a_person()` on the shared base in
  `experiments/scenarios/scenario.py`; `LightingChanged` and the test suite's own
  `PiecePushedAway` implement it.
- `TargetHoleMoved`, `PieceShoved` — act on the world.
- `PerturbationOfWhatIsSeen` + `PerturbationOfTheNextLook` (the world-registered marker)
  + `PerceivedPoseOffset`, `DetectionRelabelled` — act on what a look reports.
- `LookAtTheScene` step: captures a frame through `SimulatedCamera`, reads it with
  `MontessoriPerceptionPipeline`, applies every waiting perturbation and clears it.
  New `SortingStep.LOOK`.
- 12 tests added to `test_montessori_scenarios.py`, reusing the existing
  `montessori_scene_fixtures.scene` fixture for the two perception perturbations.
- Docstrings formatted with `scripts/format_docstrings.py`.

## Next

- Get the new tests green. Environment is the hard part, see below.
- Re-read the whole diff adversarially before pushing.

## Environment

This container has no ROS, and `test/experiments_test/conftest.py` regenerates the ORM
interfaces at import time, which needs real ROS types — so `test_montessori_scenarios.py`
does not collect here. **Confirmed pre-existing**: the same failure reproduces on the
unmodified tree (`git stash`, collect, identical `CouldNotResolveType:
DebugExpressionPublisher`). CI runs these in a ROS image.

Built locally to get as far as possible, none of it committed:
- Python 3.12 venv via `uv sync --extra dev`. The `uv` on PATH (0.8.17) cannot parse this
  repo's `pyproject.toml`; downloaded uv 0.12.13 from PyPI and used that.
- `scratchpad/stub_rclpy.py` — a meta-path finder fabricating the ROS packages
  (`rclpy`, `geometry_msgs`, `tf2_ros`, …).
- `scratchpad/sitehack/sitecustomize.py` — installs those at interpreter startup and
  binds `DebugExpressionPublisher` onto `giskardpy.ros_executor`, which the ORM generator
  resolves at runtime but which is a `TYPE_CHECKING`-only import there.

## Outstanding / known

- Needs restacking onto `tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands.
- `PerceivedPoseOffset.instruction_for_a_person()` — a person cannot offset perception,
  so it asks them to move the piece after the look, which produces the same gap between
  belief and reality. That reading is mine, not stated in the item; flag it for review.
- #302 still open. Not blocking: the plan tooling was run from a detached worktree pinned
  at the clone's starting commit, whose script already derives the indent.
