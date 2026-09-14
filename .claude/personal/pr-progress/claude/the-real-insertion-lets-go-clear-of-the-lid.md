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
- [ ] user reruns framework_demo real --record; not done: narrowing as DB rows
- still open elsewhere: #379 pickup rerun; framework figure frames/cards after a good run;
  cube-evidence feature follow-on (worktree ~/bass/cram-board-by-the-cube)
