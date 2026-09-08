# icra-foundation / montessori-scenarios — PR #296 (draft)

Branch `claude/plan-item-kickoff-icra-montessori-3roc2d`, based on
`montessori_perception_on_main` (#202) with `claude/icra-experiments-scenario-domain-n7zwpr`
(#261) merged in. Started and implemented 2026-09-08, kickoff in `auto` mode.

## Why not #265

The item's `depends_on` names #265, but #265's merge base with `main` is 74 commits
behind the `main` both #261 and #202 sit on, so merging #261 into #265 advances the whole
convergence branch. #202 + #261 merges clean and carries everything these scenarios need.
Asked again in review whether #265 was needed for the physics: measured no — #265 drives
no MuJoCo simulation anywhere in `experiments/` either. `depends_on` deliberately left as
recorded; #252 asks about it.

## Done

- Branch cut, #261 merged (clean), pushed; draft PR #296 opened, description kept
  matching the branch. The developer merged `montessori_perception_on_main` in himself
  (`c9520c908`), which this session fast-forwarded onto before working.
- Manifest: `branch`, `pull_request_number`, `session`, `status: in_progress`; roadmap
  sections written; dashboard republished.
- `experiments/montessori/scenarios.py`: `LayoutArea`, `PiecePlacement`, `PieceLayout`,
  `SortingScene`, `SimulatedScene`, the steps, the four goals, `LightingChanged`, the four
  scripts and their `Tracy…` bindings.
- Review round 1 (`c6a00274a`): `Goal` is a krrood `Predicate` — `is_reached` became
  `__call__`, every goal states its own `_verbalization_fragment_`, the world it judges
  became one of its operands, and `Scenario.goal` moved from a field to a method.
  `Condition` renamed `ScenarioCondition`. Rename thread resolved; `Goal` thread answered
  and left open, asking whether it should have landed on #261.
- Review round 2 (`66eefdbb9`): the runs are carried in MuJoCo (`SimulatedScene`) and
  `hang` is gone — settling is gravity, the push is a real pusher on a rail, the insertion
  is the fall. Goals read `InsideOf` against the hole's landing region (segmind's own
  threshold) and `robot_holds_body`. Picking up drives the gripper to the piece by IK.
  New `SyntheticGraspingRobot` mimic (gantry arm, two-fingered pincer) in the test
  dataset. 37 tests in the module, five mutation-checked; `test/experiments_test`
  380 passed. Containment thread replied to and resolved; physics thread replied to and
  left open on the actuation question.

## Next

- Two open threads, both waiting on the developer: whether the `Goal` change belongs on
  #261, and where robot actuation in MuJoCo should live (nothing actuates the Montessori
  robot today, and `MujocoSimulator` has no `set_actuator_value`).
- CI is the authority for `control_loop_experiments`, which needs ROS to import.
- If the developer wants `depends_on` repointed at `montessori-perception-on-main`, that
  is a one-line manifest change, waiting on his answer on #252.

## Known hazards

- The `.claude/` tooling on this branch is the pre-fix copy: `plan_item_bootstrap.py`
  here still has `ITEM_FIELD_INDENT = "    "`, so bootstrap must be run from a worktree
  of `origin/integration`. Not this branch's to fix.
- A session container runs the whole suite, `pytest` included — see the roadmap section
  for the exact environment. Python 3.12 is required (coraplex uses `type X[T] = ...`).

