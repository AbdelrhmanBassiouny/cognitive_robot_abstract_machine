Plan:
- PR #519 (draft): drop Pose2D z/roll/pitch; Pose2D.from_pose transforms into reference_frame
- Stacked on upstream cram2#746 (merged in at 803c67b6); follow-up to #518

Done:
- Implemented, tests pass locally, draft PR opened

Next:
- After cram2#746 lands: merge main, check diff shrinks to ddb8eb385
