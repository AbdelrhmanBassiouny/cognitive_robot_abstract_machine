# Handover: RoboCasa experiments with the PR2 (written 2026-10-16)

Read this first. The previous session's transcript is
https://claude.ai/code/session_01WEy5o24LzuvULht7bb5n4Z

## Where things are
- Host `tom_sch@neem-4.informatik.uni-bremen.de`, container `tom-cram-robocasa-experiments`.
- Repo: `/raid/users/tom_sch/repos/cram-robocasa-experiments` on the host, which is
  `/opt/cram` in the container. Branch `robocasa-experiments`, at f9b79fcaf, pushed to the fork.
- **Worktrees:**
  - `.pr_worktree`: branch `pr2-mujoco-physics`, which is PR #752.
  - `.collision_wt`: a scratch copy of cram2 main used for PR #756. It can be deleted.
- **Environment:** activate it with
  `source /opt/ros/cram-env/bin/activate; source /opt/ros/overlay_ws/install/setup.bash; export MUJOCO_GL=egl; ulimit -v 120000000`
  Env scripts per worktree are in `/root/scripts/{main,pr,collision}_env.sh`.
- **Import order:** import a `semantic_digital_twin.adapters.robocasa_dataset` module *before*
  `robocasa`. The loader spoofs the MuJoCo and numpy versions; otherwise RoboCasa's version
  assertion fails.
- **Probe and recording scripts** are in the container's `/root/scripts`. They are also committed as
  `experiments/scripts/robocasa_session/`. These are unreviewed session scripts and do not
  follow AGENTS.md.

## Rules the user insists on
- **Git and GitHub:**
  - neem-4 has *no GitHub credentials*. Move commits to the local machine with a git bundle,
    or work in a local worktree, and push from there.
  - Push only to the fork `git@github.com:tomsch420/cognitive_robot_abstract_machine.git`,
    never to upstream cram2. Read the full `git remote -v` before pushing.
- **Commits:**
  - Commit as Tom Schierenbeck <tom_sch@uni-bremen.de>.
  - No AI co-author trailer and never name the model; "Made with AI assistance" is fine.
- **PRs:** drafts only. Bug PRs carry the `bug` label, are focused and based on main.
  Put the session link in the description. Never watch or babysit PRs.
- **Tests:**
  - pytest, TDD (failing test first). Never change a test to make it pass without asking.
  - Pass `--orm-build never`, cap memory with ulimit, run one directory at a time, and never
    run tests concurrently with video recordings.
- **Before committing:** run `scripts/format_docstrings.py` on modified files (in the container).
- **Generated noise:** test runs rewrite
  `test/krrood_test/test_eql/test_verbalization/verbalization_results.py`. Restore it with
  `git checkout`.
- Leave `test.srdf` alone.
- Follow AGENTS.md: dataclasses, no try/except, no module constants, no ClassVar,
  RST docstrings, ask before new dependencies.
- **Waits:** keep them short and bounded and check logs. The user dislikes long blind waits.

## State of the work
- **robocasa-experiments:**
  - PickPlaceCounterToSink with the PR2 under CRAM plans, full MuJoCo physics, friction
    grasping, an omni base drive, and a graph of convex sets path to place into the basin.
  - Module: `experiments/src/experiments/robocasa_task_execution/` (`counter_to_sink.py`,
    `placing_into_the_basin.py`).
  - **Tests:** 9 counter_to_sink tests pass. `test_the_pr2_puts_the_object_into_the_sink`
    fails because the pick with collision avoidance on hits CandidateLimitReached.
  - #728 (part splitting) is merged into this branch.
  - **Container only change:** RoboCasa `counter.py` line 813 uses
    `list(dict.fromkeys(valid_geoms))` instead of `list(set(...))` to fix an ordering
    nondeterminism.
- **PR #752** (draft) holds the fixes that let the PR2 work with Giskard and MuJoCo: servos
  and a drive with names like `pr2_omni_drive_x`. CI was fixed.
- **PR #756** (draft, bug): `is_in_collision` uses `<` instead of `<=`. It is done; its PR
  progress note in CLAUDE.local.md was not written.

## Open items, roughly by priority
1. **Last turn's survey: RoboCasa parts versus semantic annotations.** Details are in the
   transcript; the probes are `experiments/scripts/robocasa_session/part_survey*.py`. Proposed next steps, awaiting
   the user's go:
   1. Add `Knob`, `Button`, `Lever` and `Faucet` annotations, give `Sink`, `Cooktop`,
      `Microwave`, `Dishwasher`, `Toaster` and `CoffeeMachine` part fields, and map them in
      `loader._attach_sub_part_annotations` by body name. RoboCasa parts are already separate
      bodies with joints, so no VLM is needed.
   2. Add a part finder that splits by geom name. The fridge, microwave, dishwasher and oven
      door handles are named geoms inside the door body, so `Door.handle` stays empty.
   3. Add handle fields for `Pan`, `Kettle`, `Cup` and the lids; this is where the VLM matters.
      - RoboCasa objects have their own collision shapes, so splitting needs a `decomposer`.
        Default COACD gave 2853 hulls for the mug and took about 110 s, so it needs tuning.
      - No part finding server URL is set and torch isn't installed, so the VLM can't run here.
   - **Bugs found along the way:**
     - `load_object(PAN)` fails with DuplicateWorldEntityError (two unnamed bodies).
     - The fixed panel `stack_2_main_group_2_door_main` is annotated as a Door.
     - The fridge freezer drawer is not annotated.
     - `Cooktop` is not `HasDoors`, so the oven door of the range is not annotated.
2. **Small bug PR candidates on cram2 main** (one PR each, if the user asks):
   - `AllowCollisionForBodies` drops its bodies (`collision_rules.py`; `update` resets the set).
   - `MoveTCPWaypointsMotion` ignores `allow_gripper_collision` and `movement_type`
     (coraplex `motions/gripper.py`).
   - The MuJoCo `multiccd` option crashes on MuJoCo 3.11 (`mujoco_simulator.py`).
3. **The pick with collision avoidance on** still fails (CandidateLimitReached).
4. **Integrate the advanced grasp model from tomsch420 PR #32.** The patch is at
   `/raid/users/tom_sch/pr32_on_728_integration.patch` on the host.
5. **Undecided by the user:**
   - The RoboCasa ordering fix: carry it in `mujoco_compat` or in a RoboCasa fork?
   - Can `placement_pose` (used only in tests) be removed?
   - Should the base drift false success become its own PR? (Goals are bound to `robot.root`
     when the base is not full body controlled.)
6. **Smaller loose ends:** the costmap margin, the zero size
   array in placement_pose, and the PR2 base floor contact.
