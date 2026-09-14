Branch claude/the-real-reach-is-handed-the-piece-not-its-body, stacked on #379
(claude/results-tables-gain-the-schemas-new-columns). Bug-fix draft PR #380, label bug. Found
on the robot 2026-09-14: framework_demo --execution real --record failed as the pick-up's
reach expanded: AttributeError 'Body' object has no attribute 'root' (pick_up.py:109).

Plan: PickUpActionReal hands ReachAction the piece's annotation, as #265 (87f04b0bf3) requires.
- [x] cause: #265 made ReachAction/PickUpAction.object_designator a HasRootBody; the real
      carrier stored action.object_designator.root and handed the Body to the reach
- [x] test first: test_the_reach_is_handed_the_piece_the_plan_names_not_its_body (needed
      EndEffectorFacingAWay stand-in; fixed FingersThatRecord.move GripperState.CLOSED->CLOSE)
- [x] fix: object_designator holds the annotation; body read off .root; existing
      test_it_takes_hold_of_the_piece_the_plan_names follows the new contract
- [x] test_pick_and_place_action_real.py 11 passed; docstrings formatted
- [x] pushed, draft PR #380 with bug label
- [ ] user reruns framework_demo --execution real --record with this branch in ~/bass
- still open elsewhere: #379 pickup rerun; framework figure frames/cards after a good run;
  cube-evidence feature follow-on (worktree ~/bass/cram-board-by-the-cube)
