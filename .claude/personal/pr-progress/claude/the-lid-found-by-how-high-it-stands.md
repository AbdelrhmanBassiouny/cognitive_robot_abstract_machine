Branch claude/the-lid-found-by-how-high-it-stands, stacked on #376
(claude/the-open-plan-runs-on-the-real-robot). Bug-fix draft PR #378, label bug. Found on the
robot 2026-09-14 19:08: framework_demo --execution real said "No board answering the
description is in view yet." for 30 looks.

Plan: find a lid whose colour the light washes out.
- [x] cause measured on a live capture (scratchpad/captures/cube_on_lid_now): lid's coloured
      part broke into <=0.0086 m2 pieces (minimum_lid_area 0.01) -> holes never searched; the
      cube on the lid was not the cause
- [x] test first: live frame shipped as capture washed_out_lid + CaptureTruth; 7 capture tests
      failed on it before the fix
- [x] fix: BoardDetector._perforations_in reads coloured surfaces first, then surfaces the
      camera measured standing as high as the lid (|h - lid| < lid_standing_height/2,
      FindTheBoard passes the described board's height). OR-ing both masks moved the
      stuck_cube_in_hole fit 0.7 mm and lost its marginal lid cube -> fallback instead
- [x] capture tests 115 passed 6 xfailed; other perception suites 162 passed
- [x] commit e24d6bc26b pushed, draft PR #378 with bug label
- [ ] user reruns the framework demo on the robot with this branch checked out in ~/bass
- follow-on (own feature PR, worktree ~/bass/cram-board-by-the-cube, branch
  claude/the-board-found-by-the-cube-on-its-lid): the board statement says a light-blue cube
  rests on its lid's back-left corner, and the look uses the cube as evidence for the board
