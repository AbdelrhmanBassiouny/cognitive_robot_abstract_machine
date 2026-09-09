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
- Review round 4 (`429e335d4`): a run can be filmed while it is performed, with
  `MujocoVideoRecorder` — `SceneRecording` films it in takes, `SimulatedScene` lets go of
  what carries it whenever the world's model changes (a sibling `ModelChangeCallback`
  rather than each step remembering to), and the film is made from the simulation
  carrying the run, so a filmed run leaves the piece exactly where an unfilmed one does.
  Videos land in `$MONTESSORI_SCENARIO_VIDEO_DIRECTORY`. `PlaceAction` gained the
  optional `grasp_description` the third round asked about, at the developer's "do (1)",
  with two tests in `test_graph_parsing.py`. The mimic pincer gained visual geometry and
  the `experiments` CI job exports `MUJOCO_GL=egl`. 48 tests in the module, eight
  mutation-checked; `test/experiments_test` 391 passed. One thread resolved (the place's
  grasp), one answered and left open (where the demo's actuation lives), and the video
  review — a review body rather than a thread, which is why round three missed it —
  answered as a conversation comment.
- Review round 3 (`db746a949`): the robot is commanded by coraplex — `PickUpAction` and
  `PlaceAction` under `simulated_robot`, giskard ticking the statechart, headless and
  with no ROS — and every hand-written gripper method is gone. `SimulatedScene` builds
  its MuJoCo mirror on demand and `stop()` drops it, since a grasp re-parents what it
  holds and a compiled model cannot follow that. Each hole's landing region is measured
  as the free space under it with a graph of convex sets, the two hand-chosen margins are
  deleted, and `ShapeSortingHole` carries its own region. `NoSuchPieceError` and
  `HoleHasNoLandingRegionError` replace the bare `KeyError`s. The mimic pincer gains a
  three-axis wrist and a grasp frame between its fingertips. 43 tests in the module, six
  mutation-checked; `test/experiments_test` 386 passed. Three threads resolved (the
  exception, the free space, the coraplex question); two left open.

## Next

- Three open threads, all waiting on the developer: whether the `Goal` change belongs on
  #261; whether `InsideOf`'s `minimum_containment_ratio` (on #265, not on this base)
  should be ported here now and meet #265 as a conflict; and where the demo's actuation
  should live, which is now one thread rather than two — the answer to it also decides
  whether `MontessoriSortingScenario` should be handed the world it is built on.
- CI is the authority for `control_loop_experiments`, which needs ROS to import, and for
  the two `PlaceAction` tests in `test_graph_parsing.py`, which need a robot description.
- Two defects reported and not taken, each belonging in a bug pull request of its own:
  `StateChangeCallback.stop` removes by equality, and every `Callback` of one class shares
  an id, so two simulators of one world unregister each other; and `ReAttachNode` keeps a
  grasped body's free connection, which no MuJoCo model can be compiled from.
- If the developer wants `depends_on` repointed at `montessori-perception-on-main`, that
  is a one-line manifest change, waiting on his answer on #252.

## Known hazards

- The `.claude/` tooling on this branch is the pre-fix copy: `plan_item_bootstrap.py`
  here still has `ITEM_FIELD_INDENT = "    "`, so bootstrap must be run from a worktree
  of `origin/integration`. Not this branch's to fix.
- A session container runs the whole suite, `pytest` included — see the roadmap section
  for the exact environment. Python 3.12 is required (coraplex uses `type X[T] = ...`).

