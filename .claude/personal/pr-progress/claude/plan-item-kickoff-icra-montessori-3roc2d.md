# icra-foundation / montessori-scenarios — PR #296 (draft)

Branch `claude/plan-item-kickoff-icra-montessori-3roc2d`, based on
`montessori_perception_on_main` (#202) with `claude/icra-experiments-scenario-domain-n7zwpr`
(#261) merged in. Started 2026-09-08, kickoff in `auto` mode.

## Why not #265

The item's `depends_on` names #265, but #265's merge base with `main` is 74 commits
behind the `main` both #261 and #202 sit on, so merging #261 into #265 advances the whole
convergence branch (4 conflicting files it hand-resolved, plus `memoize` having moved out
of `krrood.utils` while #265's `world.py` still imports it). #202 + #261 merges clean and
carries everything these scenarios need. Full reasoning is in the plan's `roadmap.md`
section and in the PR description; raised on tracking issue #252 for confirmation, and
`depends_on` deliberately left as recorded.

## Plan

1. `experiments/src/experiments/montessori/scenarios.py`
   - `PiecePlacement` / `PieceLayout` (`randomized`, `partial`, `nearly_ambiguous`).
   - `MontessoriSortingScenario[RobotType]` — builds `MontessoriWorld`, applies the
     layout, mounts `self.robot_type`, returns the twin's `World`.
   - Steps and goals; the four scripted scenarios (static, robot pick-and-place, external
     push while idle, piece held at query time).
   - `LightingChanged(Perturbation)` using `MujocoLight`.
2. `experiments/scripts/generate_orm.py` — append these classes to `ignored_classes`, the
   reason #261 gave for its own.
3. `test/experiments_test/test_montessori_scenarios.py` — each scenario built headless,
   asserting its own precondition; tests bind `SyntheticFixedArmRobot`.

Tests first, per TDD.

## Done

- Branch cut, #261 merged (clean), pushed; draft PR #296 opened.
- Manifest: `branch`, `pull_request_number`, `session`, `status: in_progress` recorded;
  roadmap section written.
- Local environment established well enough to run these tests here (see roadmap section):
  `MontessoriWorld()` builds against stubs for `xacro` and `giskardpy_bullet_bindings`.

## Next

- Write the failing tests, then the module.
- Keep the PR description matching what the branch actually does.

## Known hazards

- The `.claude/` tooling on this branch is the pre-fix copy: `plan_item_bootstrap.py`
  here still has `ITEM_FIELD_INDENT = "    "`, so bootstrap must be run from a worktree of
  `origin/integration`. Not this branch's to fix.
- CI is the authority for anything touching the collision checker or the generated ORM
  interface; the container stubs the compiled Bullet bindings.
