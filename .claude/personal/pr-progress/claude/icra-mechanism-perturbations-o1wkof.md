# icra-mechanism / perturbations — PR #311 (pushed, draft, green)

Replaces #305. Branch `claude/icra-mechanism-perturbations-o1wkof` off #265. Carries no
`.claude/` tooling change — the reason #305 was closed.

## Done

- Branch re-cut off #265; cherry-picked `b673ec883` (`simulated_setup.py` takes `World`).
- Draft PR #311 opened, description updated to match the built code; manifest recorded
  (`in_progress`, branch, PR, session); two roadmap sections appended; dashboard at v10.
- `Perturbation.instruction_for_a_person()` on the shared base; `LightingChanged` and the
  test suite's `PiecePushedAway` implement it.
- `TargetHoleMoved`, `PieceShoved` (world); `PerturbationOfWhatIsSeen` +
  `PerturbationOfTheNextLook` marker + `PerceivedPoseOffset`, `DetectionRelabelled`
  (what a look reports); `LookAtTheScene` + `SortingStep.LOOK`.
- 25 new tests. **96 passed, 0 failed** across `test_montessori_scenarios.py` and
  `test_scenarios.py`, real MuJoCo under EGL. Pushed only after that.

## For the developer to rule on

- **`TargetHoleMoved` moves the board, not one hole.** Departs from the mechanism the
  2026-09-09 roadmap entry settled, because holes and the board are on `FixedConnection`s
  and a hole is cut into the lid. Contract preserved; mechanism changed. On #311.
- **`PerceivedPoseOffset`'s person-instruction is my reading**, not stated anywhere.

## Departures from AGENTS.md to own

- Tests were written after the implementation, not TDD. Recorded in roadmap.md.

## Outstanding

- Needs restacking onto `tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands.
- #302 still open; not blocking (plan tooling run from a worktree pinned at the clone's
  starting commit, whose script already derives the indent).

## Environment (local only, nothing committed)

`uv` on PATH is too old for this `pyproject.toml` — fetched uv 0.12.13 from PyPI.
`libglfw3`/`libegl1` missing made `glfw` spawn ~160 subprocesses hung on stdin.
`scratchpad/stub_rclpy.py` + `scratchpad/sitehack/sitecustomize.py` stand ROS in and bind
`DebugExpressionPublisher` onto `giskardpy.ros_executor`. Run with `MUJOCO_GL=egl`.
Earlier claim that these tests need a ROS image to run at all was wrong.
