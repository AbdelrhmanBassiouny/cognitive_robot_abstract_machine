Branch claude/the-real-insertion-lets-go-clear-of-the-lid, stacked on #380
(claude/the-real-reach-is-handed-the-piece-not-its-body). Bug-fix draft PR #381, label bug.
Found on the robot 2026-09-14: framework_demo real with the cube on the lid reached too low,
and the insertion hit the board (protective stop). pickup_demo_real does neither.

Plan:
- [x] cause 1 (proven): InsertionActionReal let the centre go DEFAULT_HOVER_HEIGHT (2 cm)
      above the hole origin, which is the lid minus half the marker, so the underside was at
      the lid. pickup lets the underside go PLACE_HOVER (4 cm) above the lid.
- [x] cause 2 (likely, not reproduced in render): the grasp aimed at the stood centre =
      plane + measured/2; a short depth reading on the lid stands it too low
- [x] fix: release = hole frame + marker/2 + PLACE_HOVER + half the model height; grasp =
      surface_height + half the model height + offset; carriers hold DetectedMontessoriShape
- [x] tests: 12 carrier tests + test_framework_demo pass; pushed; draft PR #381
- [x] recording crash on the robot (ReachActionDAO.object_designator can't hold
      DetectedMontessoriShapeDAO): reach now gets object_designator.role_taker; DB test added;
      #380's reach test now asserts role_taker; commit 258fb6ae35 pushed, PR body updated
- [ ] user reruns on the robot; if the hole's sideways error is still large, look at the
      board before the cube goes on the lid
- [x] new ask (2026-09-14): record perception's narrowing to the cyan cube from the real camera
      frame during framework_demo real, and use it in the framework figure. Done on stacked
      branch claude/the-framework-figure-shows-the-real-narrowing, in worktree
      ~/bass/cram-framework-narrowing (user wants this checkout left on the fix branch).
      Run tests there with PYTHONPATH="$WT:$WT/*/src:$PYTHONPATH" (editable installs point here).
      Frame = look.wait_for_frame() after perceive; GroundedPlan.narrowing_over -> trial
      narrowing/ pictures; bag_frames --narrowing copies to figure; panel 1 reads them.
      Stand-in pictures from shipped tracy_pickup_demo (cube + cylinder on lid). 57 tests pass.
      Draft PR #382 (base: this branch). *.png is gitignored: the 4 panel pictures are add -f.
- [x] merged #382 into this branch (worktree removed); bag_frames now narrows the bag's first
      frame (ROBOT_TABLE_PIECES = SMALLER_PIECES; full-size set found no cube offline).
      Panel 1 + framework.pdf rebuilt from tracy_framework_demo_20260914_211651. 60 tests pass.
- [x] figure layout (ec803047f3): panel 1 is a 2x2 grid, names above tiles (current view, cyan,
      on the lid, cube), panel 1 taller at the other panels' cost (figure height unchanged);
      robot row stacks tracy_picking_up.png above tracy_inserting.png. last_hold gives the
      pick-up; SHORTEST_OPENING (0.2 s) ignores the one open misreading at 36.81 s in the bag.
      12 bag-frame tests pass.
- [x] 4851615aad: panel 1 uses only rectified pictures (0/1/2_rectified + answer; the camera
      pictures are untracked now); the acting pictures' space is 7.2x4.3 cm (figure +0.8 cm tall)
- [ ] user reruns framework_demo real --record; not done: narrowing as DB rows
- still open elsewhere: #379 pickup rerun; framework figure frames/cards after a good run;
  cube-evidence feature follow-on (worktree ~/bass/cram-board-by-the-cube)
- [x] 2026-09-15 paper figures of the real corpus (reproduction package in ~/Downloads), three
      draft PRs stacked on this branch, each in its own worktree ~/Projects_2/cram-<branch>:
      #388 (bug) card's before frame starts at MovedBySomeoneElse.moment (stand-still PieceShoved
      frames were identical); #389 (bug) PlaceOfOwnBody marked ScoredAgainstWhereTheJointsStood,
      --rescore-working-memory re-asks it at the joint trace's moment (3 l_gripper rows stored
      wrong by the pre-60bd6c165e np.allclose); #390 LaTeX tables (LatexRenderer, <name>.tex).
      Also on main: #386 (buffer_zone_distance), #387 (typst nested table).
      Then (user ask): applying row in the Bloom table = GoalReached over trials with plans
      (real: 3 sorting runs + framework demo); branch claude/bloom-table-reports-applying.
      Draft PR #391 (applying row). Draft PR #393 (bug, branch claude/joints-counted-once-per-episode):
      NumberOfDegreesOfFreedomInTheRecordedWorld counted the world once per trial (42 not 14
      for the 3-trial stand-still episodes) - the last wrong answers (Remembering 0.96,
      self-model 0.93). Before/after card of 0a793ded checked: frames now differ (5.5 s / 22.7 s).
- [ ] pipeline run 1 (without the control question): scratch worktree ~/Projects_2/cram-paper-pipeline
      (branch local/paper-pipeline = this branch + #386..#391 + #393 cherry-picked);
      generate_paper_artifacts.py re-scores, asks the long-term set (object per episode),
      copies .tex/.json/.png into krrood-icra-2027/paper/figures/real. DONE 2026-09-15 with #393:
      0 wrong answers; Remembering 70/1.0, Understanding 143/1.0, Applying 4/1.0; every bucket
      1.0; 140 files (8 tex, 8 json, 124 png) in paper/figures/real, PDFs gone.
      Run 2 DONE: #394 cherry-picked (test-file conflict with #393 resolved, keep both), 0 wrong;
      Remembering 74/1.0, Control bucket 4/1.0 (the 4 plan-performing episodes); 144 files in
      paper/figures/real_with_control_program incl. 4 motions_requested plan-timeline cards.
- [ ] run 2 (user ask 2026-09-15): a question querying the constraints the motions put on the
      controller, kept apart so the paper can use either run. User chose the recorded motion
      requests (MoveToolCenterPointMotion / MoveJointsMotion of the plans' MotionNodes); the
      giskard statechart nodes are not persisted (MotionStatechartDAO holds only an id).
      Branch claude/the-long-term-set-asks-what-the-motions-requested (worktree
      ~/Projects_2/cram-the-long-term-set-asks-what-the-motions-requested), base this branch.
      Probe on the real DB: query trial.plans -> plan.nodes -> MotionNode.designator gives 29
      rows = 29 walked for 25f5161d. Design: MotionsRequestedInTheEpisode, bucket CONTROL,
      RequiredFact.PERFORMED_PLANS, answers MotionRequest (JointRequest/ToolCenterPointRequest,
      frozen); QuestionSet.over_long_term_memory(asking_the_control_program=False);
      ask_episode --ask-the-control-program; MotionsRequestedCard (plan timeline).
      Draft PR #394 (105 + 24 tests pass). Reproduction script has --ask-the-control-program
      (corpus real_with_control_program, own DB + paper dir).
      Next: once run 1 finishes, cherry-pick #394 into local/paper-pipeline, regenerate ORM,
      run generate_paper_artifacts.py --ask-the-control-program --skip-database-setup.
- [x] 2026-09-16 reviewer page (user ask): branch real-experiments-tracy-icra-2026 (for the
      anonymous repo; no PR, pushed directly; worktree ~/Projects_2/cram-real-experiments-tracy-icra-2026)
      = this branch + local/paper-pipeline (ff) + #396 merged. README.md is now the reproduction
      guide (A: tables from the dump, B: simulation, C: real robot, kept-episode table);
      old README -> MONOREPO.md. generate_paper_artifacts.py + export_filtered_corpus.py moved
      to experiments/reproduction (--reproduction-package required, --figures-directory
      replaces --paper-repository). Pushed 2d6c356b54. Leftover bubble-removal in the
      framework figure committed on claude/the-framework-figure-names-the-working-memory,
      draft PR #396 (base this branch).
- [ ] README has a TODO placeholder for the anonymised data link (user to host the package)
