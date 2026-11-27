## Plan
- Merge main 913a92c2 into the branch (108 conflicting files at c29194728e), resolving each by keeping main's change and the PR's renames/API; run the affected tests; push via maintenance push; carry it into #524.

## Done
- c29194728e: CI green except small_packages (krrood check). cram2 drafts still to post (review-replies/cram2-1019-2026-11-23-second.md): benchmark, both cross-product threads, embedded planes.

## Next
- small_packages `krrood check --since HEAD^1`: 864 findings in 219 PR files; owner to decide.
- Owner decides: EuclideanSpace.inner_product as reference; SymbolicSpatialVector bases; MetricPoint naming thread.
- cram2#1019 review state not read on 2026-11-27 (fork Action got HTTP 404).
- Resolve #524. Later PR: image space; general 2D Cartesian frame.
