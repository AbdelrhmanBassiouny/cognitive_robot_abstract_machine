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
- [ ] user reruns on the robot; if the hole's sideways error is still large, look at the
      board before the cube goes on the lid
- still open elsewhere: #379 pickup rerun; framework figure frames/cards after a good run;
  cube-evidence feature follow-on (worktree ~/bass/cram-board-by-the-cube)
