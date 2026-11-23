Plan
- Keep the branch mergeable with cram2 main, and answer cram2#1019's reviews; the owner decides the open design threads.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- 9f5540e0 merges cram2 main 44e1f109 (#795 RoboKudo world synchronization, #1043 spatial math docs). RoboKudo takes main's side, with HomogeneousTransformationMatrix, Point3 and Point2 renamed in every file main changed; the branch's edits there were renames only. The docs pages use the new names and a Frame on the CartesianFrame3Dimensional interface; both pages execute. README keeps this branch's text plus main's docs link.
- test/krrood_spatial_math_test at 9f5540e0: 737 passed (README example and mypy static checks included). RoboKudo tests not run (need ROS); its changed files compile.

Read 2026-11-23
- Merge probe vs cram2 main 44e1f109 at 9f5540e0: clean.
- CI at 0e5450d6: fork 45/46 and upstream 56/58, small_packages failing on both (krrood check, set aside by the owner). CI on 9f5540e0 not read yet.
- cram2#1019: ichumuh requested changes again on 2026-11-23, 12 open threads; the owner replied to most the same day.

Next
- Read the CI of 9f5540e0 on both PRs.
- Owner: decide the open cram2#1019 threads (metric and cross product on frame kinds, EmbeddedPlaneRelation, has_position and "weight" wording, operator module, Vector3 returns).
- #524 conflicts with this branch in 20 files; it needs its own resolve.
