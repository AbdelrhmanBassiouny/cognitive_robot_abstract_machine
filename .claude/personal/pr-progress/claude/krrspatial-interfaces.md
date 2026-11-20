Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- Every code ask of the owner's cram2#1019 review is in the branch up to 7c0b1bda. test/krrood_spatial_math_test: 733 passed at 7c0b1bda.
- f2f740c9c0: World.rebind_world_entities rebinds the frames of a spatial value or change (its deep copy shares them), so a trial's rebuilt nodes are given in the copy's frames. Cause of cram2#1019's coraplex_garmi_clean_up_demo failure: ReferenceFrameMismatchError naming one frame twice, from DistanceMonitor's tip point. Tests fail without it, pass with it; test_world.py: 173 passed, 15 errors/failures from missing robot description packages. The demo itself was not run (no ROS here).

Read 2026-11-20
- Merge probe vs cram2 main 82707c74 at 7c0b1bda: clean. Fork CI at 7c0b1bda: 45 of 46, small_packages (krrood check) set aside. Upstream CI at 7c0b1bda: that and the garmi demo failed.

Next
- Read the CI of f2f740c9c0 on both PRs, the garmi demo above all.
- Owner: post the replies in .claude/personal/review-replies/cram2-1019.md (notes branch).
- #524 needs its own resolve.
