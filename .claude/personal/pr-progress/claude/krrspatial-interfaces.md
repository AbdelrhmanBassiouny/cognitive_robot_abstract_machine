## Plan
- Answer the 2026-11-27 review (values vs changes): done in c72deb54; owner reviews it. Then the ORM break (#618) and the krrood check findings.

## Done
- 90b6955c: merged main 913a92c2 (108 conflicting files), pushed.
- c72deb54: RotationMatrix is an Orientation value; T.rotation_matrix is the orientation, T.rotation the rotation-only change rotating code applies; RigidCoordinateChange.rotation_matrix -> rotation; ORM stores axis-angle + reference frame. PR description updated.

## Next
- #618: SemDT ORM names AffineFrameDAO undefined after the merge (cram2#1042's ORMatic + this PR's generics); ORM CI jobs red until fixed.
- small_packages `krrood check --since HEAD^1` findings; owner to decide.
- Owner decides: EuclideanSpace.inner_product docstring as reference; Vector-change-type prototype dropped (mypy loses frame types).
- cram2#1019 review state not read on 2026-11-27 (fork Action got HTTP 404); cram2 drafts still to post.
- Resolve #524. Later PR: image space; general 2D Cartesian frame.
