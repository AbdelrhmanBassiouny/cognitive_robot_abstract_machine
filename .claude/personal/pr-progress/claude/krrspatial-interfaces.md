Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- ec8ffb34: how a change moves a value lives in the abstract layer (Vector/Point homogeneous weight, Pose, Orientation, MotionVectorPair adjoint); Point derives GenericCoordinateChange; SpecialEuclideanGroupAction/HomogeneousCoordinates removed; cross keyword-only.
- 6d20eaa1 merges cram2 main 82707c74 (RigidMotionRate). 9fa919d7: to_coordinate_change is the only pose/orientation accessor (homogeneous_matrix, orientation rotation_matrix removed); HTM3D.dot keyword-only. Probe clean; 707 spatial-math tests pass.

Next
- Owner: post replies from scratchpad cram2-1019-replies.md (new: :1767, :317, :1378, cartesian_monitors :140; :691/:478/:494/2D :53 updated). No reply to LucaKro.
- krrood check on 9fa919d7: 25 pre-existing docstring findings in functions touched only by the rename (left, as with the earlier 973).
- CI on 9fa919d7 not read. Upstream garmi demo and small_packages failing (logs show only exit 1).
