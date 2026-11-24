## Plan
- Answer ichumuh's second cram2#1019 review (code done at 4b111fba); owner posts the remaining drafted replies and shares the 2D-spaces doc with Simon.

## Done
- 6f4216e1 one-product re-expression (T @ point 120 -> 25 us, main 23); 65dbd601 inner product on EuclideanSpace, cross only on Vector3Dimensional, MotionVectorPair folded into VectorPair; e575d846 planes by structure and identity (planar change 210 -> 9.5 us); 1d6570c2 ROS-free spatial benchmark; 4b111fba Gram matrix removed.
- Replies in review-replies/cram2-1019-2026-11-23-second.md, checked at 4b111fba; owner posted 3 (inner product, MotionVectorPair, naming); benchmark, both cross-product threads and embedded planes still to post. Doc https://claude.ai/artifact/3FGKqU3Ktp6qtzw1xrqm6W.

## Next
- CI red at 4b111fba (same 3 jobs at 1d6570c2), owner to prompt: SemDT test_end_effector_grasps::test_the_grasp_on_a_body_not_below_the_tool_frame_is_read_the_same and coraplex test_follow_tcp_path_multi[hsrb,garmi] raise ReferenceFrameMismatchError from ensure_acts_on's `is not` frame check (a connection stamps its frames onto the shared HELD_BODY_OFFSET, so a later world's test sees an old frame); small_packages fails `krrood check --since HEAD^1` with 864 findings, mostly missing docstrings in 219 files the PR touches.
- Resolve #524, which conflicts with this branch in 20 files.
- Later PR: image space as its own 2D Euclidean space; general 2D Cartesian frame with the embedded-plane frame as subclass.
