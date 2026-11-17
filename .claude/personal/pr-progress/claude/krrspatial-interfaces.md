## Plan
- Merge cram2 main 34c9f204 into #527 (34 conflicting files: renames vs main's keyword-only refactors).
- Fix CI: giskardpy test_constraint_collection took an angle across two frames (owner: express in one frame).
- Answer the 2026-11-17 review: foot_point -> embed_planar_point (owner's choice), type variables moved next to their interfaces, ambient_space and the Generic parameters explained.
- Keep #527 ready (owner said so); refresh description; upstream description and class map for cram2.

## Done
- Merge resolved; old names in main's new code renamed; NoFreeSpaceError typed MetricPoint; space.py imports classproperty from krrood.patterns.
- RoboKudo axes_pose no longer calls the removed translation_matrix (test added; needs ROS, CI only).
- Locally: krrood_spatial_math_test + SemDT test_spatial_types 611 passed.

## Next
- Read CI on the pushed merge commit; giskardpy, robokudo and coraplex need ROS, so only CI runs them.
- Promote to cram2 with the upstream description once CI is green.
