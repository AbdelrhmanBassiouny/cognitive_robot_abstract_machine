## Plan
- Answer the reviews on #527 and cram2#1019; owner posts the remaining cram2 drafts and shares the 2D-spaces doc with Simon.

## Done
- 6f4216e1, 65dbd601, e575d846, 1d6570c2, 4b111fba answer ichumuh's second review (see PR description).
- c29194728e: Connection keeps copies of its offsets (fixes the PR2 grasp CI failure); coraplex test_follow_tcp_path_multi offset given in the milk's frame (owner approved the test edit); vector docstring; README no longer names SemDT. #527 threads on these two resolved; inner-product and SymbolicSpatialVector-bases threads answered, left open for owner.
- cram2 drafts in review-replies/cram2-1019-2026-11-23-second.md: still to post benchmark, both cross-product threads, embedded planes.

## Next
- Read CI at c29194728e (PR2 and coraplex tests need ROS, not run locally).
- small_packages `krrood check --since HEAD^1`: 864 findings (mostly missing docstrings) in 219 PR files; owner to decide.
- Owner decides: keep EuclideanSpace.inner_product as reference; SymbolicSpatialVector bases; MetricPoint naming thread (open since 11-18).
- Resolve #524 (conflicts in 20 files). Later PR: image space; general 2D Cartesian frame.
