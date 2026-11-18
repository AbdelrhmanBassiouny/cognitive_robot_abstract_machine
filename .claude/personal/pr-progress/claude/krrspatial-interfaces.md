## Plan
- Keep #527 ready (owner said so, again 2026-11-18); promote to cram2 once CI is green and the open threads are settled.

## Done
- 2026-11-18 review in 6f2bd2c4: HomogeneousTransformationMatrix3Dimensional, SymbolicSpatialValue3Dimensional/2Dimensional; World is the space (world-as-euclidean-space folded in); FloorPlan.project_onto_plane; behavioural point tests. 7 threads resolved; figures at https://claude.ai/artifact/KFoP351gxm32fr8S6ahSda.

## Next
- Read CI on 6f2bd2c4 (running when pushed; giskardpy, robokudo, coraplex need ROS: CI only).
- Owner decides two open threads: frameless values in transformations (recommended: keep), renaming the flatten test.
- #524 conflicts with this branch and must adopt the new names and transform_into_own_frame: /plan-item-resolve 524.
