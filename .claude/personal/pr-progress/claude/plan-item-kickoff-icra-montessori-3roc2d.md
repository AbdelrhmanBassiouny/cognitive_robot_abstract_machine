# icra-foundation / montessori-scenarios — PR #296 (draft)

Branch `claude/plan-item-kickoff-icra-montessori-3roc2d`, based on
`montessori_perception_on_main` (#202) with `claude/icra-experiments-scenario-domain-n7zwpr`
(#261) merged in. Started and implemented 2026-09-08, kickoff in `auto` mode.

## Why not #265

The item's `depends_on` names #265, but #265's merge base with `main` is 74 commits
behind the `main` both #261 and #202 sit on, so merging #261 into #265 advances the whole
convergence branch (4 conflicting files it hand-resolved, plus `memoize` having moved out
of `krrood.utils` while #265's `world.py` still imports it). #202 + #261 merges clean and
carries everything these scenarios need. Full reasoning in the plan's `roadmap.md`
section, the PR description, and tracking issue #252. `depends_on` deliberately left as
recorded — that edge is the plan's call, and #252 asks about it.

## Done

- Branch cut, #261 merged (clean), pushed; draft PR #296 opened and its description
  kept matching the branch.
- Manifest: `branch`, `pull_request_number`, `session`, `status: in_progress`; roadmap
  section written; dashboard republished.
- `experiments/src/experiments/montessori/scenarios.py` (~1,070 lines): `LayoutArea`,
  `PiecePlacement`, `PieceLayout` (`randomized` / `partial` / `nearly_ambiguous`),
  `SortingScene`, the steps, the four goals, `LightingChanged`, the four scripts and
  their `Tracy…` bindings.
- `test/experiments_test/test_montessori_scenarios.py`: 26 tests (29 items), all
  passing, each non-trivial one mutation-checked.
- `experiments/scripts/generate_orm.py`: these classes added to `ignored_classes`.
- Review round 1 (`c6a00274a`): `Goal` is a krrood `Predicate` — `is_reached` became
  `__call__`, every goal states its own `_verbalization_fragment_` (mandatory for free,
  the base method being abstract), the world it judges became one of its operands, and
  `Scenario.goal` therefore moved from a field to a method beside `steps(world)`.
  `Condition` renamed `ScenarioCondition` with every reader. Five new tests in
  `test_scenarios.py`, one parametrized verbalization test here; all mutation-checked.
  Description and inline replies posted; rename thread resolved.

## Next

- The `Goal` review thread is answered but deliberately left open: the reply asks
  whether that change should have landed on #261 (whose file it is) instead of here.
  Waiting on the developer.
- CI is the authority for the `generate_orm.py` change and for
  `control_loop_experiments`, which needs ROS to import; neither runs in this container.
- If the developer wants `depends_on` repointed at `montessori-perception-on-main`, that
  is a one-line manifest change, waiting on his answer on #252.

## Known hazards

- The `.claude/` tooling on this branch is the pre-fix copy: `plan_item_bootstrap.py`
  here still has `ITEM_FIELD_INDENT = "    "`, so bootstrap must be run from a worktree
  of `origin/integration`. Not this branch's to fix.
- A session container *can* run these tests (the roadmap note saying otherwise is now
  corrected in the roadmap section): Python 3.12, `random_events`/`probabilistic_model`
  from wheels, plus `mujoco`, `casadi~=3.7.0`, `daqp`, `manifold3d`, `plyfile`,
  `urdf_parser_py`, `rustworkx`, and stubs for `xacro` and `giskardpy_bullet_bindings`.
  The compiled Bullet bindings are the one thing that genuinely will not build.
