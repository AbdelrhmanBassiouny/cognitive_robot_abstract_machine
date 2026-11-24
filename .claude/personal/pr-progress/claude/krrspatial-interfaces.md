## Plan
- Answer ichumuh's second cram2#1019 review (done at 4b111fba); owner posts the drafted replies and shares the 2D-spaces doc with Simon.

## Done
- 6f4216e1 one-product re-expression (T @ point 120 -> 25 us, main 23); 65dbd601 inner product on EuclideanSpace, cross only on Vector3Dimensional, MotionVectorPair folded into VectorPair; e575d846 planes by structure and identity (planar change 210 -> 9.5 us); 1d6570c2 ROS-free spatial benchmark; 4b111fba Gram matrix removed (lengths only in Cartesian frames).
- PR description current; replies drafted in review-replies/cram2-1019-2026-11-23-second.md; doc https://claude.ai/artifact/3FGKqU3Ktp6qtzw1xrqm6W.

## Next
- Read CI on 4b111fba, incl. the ROS jobs (Giskard, coraplex, RoboKudo were not run locally).
- Resolve #524, which conflicts with this branch in 20 files.
- Later PR: image space as its own 2D Euclidean space; general 2D Cartesian frame with the embedded-plane frame as subclass.
