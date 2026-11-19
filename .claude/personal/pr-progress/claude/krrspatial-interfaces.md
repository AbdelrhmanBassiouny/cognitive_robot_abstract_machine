Plan
- Resolve 2026-11-19: merge main, then answer cram2#1019's changes-requested review.
- Owner chose: two frames' x-y planes are one EmbeddedPlane when coplanar in one world (the 23 Oct plan decision); the SE(2) constructor refuses frames on different or mirrored planes.
- Upstream replies are drafted here for the owner to post, not posted.

Done
- Merged main b691f5af (c9ac60d8): Displacement/Twist split and keyword-only create_with_dofs kept in the Dimensional names; merge probe clean at c9ac60d8.

Next
- Tests first, then: XYPlaneRelation + CartesianFrame3Dimensional.compare_xy_plane, EmbeddedPlane equality, SE(2) constructor check (answers threads 3624 and 3665).
- Draft replies for cram2#1019's 5 threads and the review.
- #524 (krrood_image) conflicts with main in its own files (ci.yml, pyproject files, conftest, version test): needs its own resolve.
