## Plan
- Keep #527 ready (owner said so); promote to cram2 once CI on ca5d6c6d is green.

## Done
- Merged cram2 main 34c9f204 (ca5d6c6d); old names in main's code renamed; giskardpy test_constraint_collection expresses both vectors in one frame; RoboKudo axes_pose off the removed translation_matrix.
- 2026-11-17 review: foot_point -> embed_planar_point and type variables moved (resolved); ambient_space and Point's Generic answered, left open for the owner.
- Upstream description and class map (https://claude.ai/artifact/HYQM9QjMLU5nDrWcCytaPS) written.

## Next
- Read CI on ca5d6c6d (giskardpy, robokudo, coraplex need ROS: CI only).
- #524 conflicts with this branch on ci.yml, pyproject, ORM and geometry: needs /plan-item-resolve 524.
