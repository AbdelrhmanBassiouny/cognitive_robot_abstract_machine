Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- ec8ffb34: how a change moves a value lives in the abstract layer; SpecialEuclideanGroupAction/HomogeneousCoordinates removed; cross keyword-only.
- 6d20eaa1 merges cram2 main 82707c74. 9fa919d7: to_coordinate_change is the only pose/orientation accessor; HTM3D.dot keyword-only.
- 387b26e3 (owner's choices, 2026-11-20 resolve): cross product on the frame kind (CartesianFrame3Dimensional.cross_product; AffineFrame raises FrameHasNoCrossProductError; Vector.cross asks it like dot; MotionVectorPair binds Vector); CrossProductVector, GenericCrossProductVector and SymbolicAxisCoordinates removed; from_coordinates is generic through coordinate_names and CoordinateRepresentation.coordinate_system_arguments, overridden once by SymbolicSpatialValue. Vector3Dimensional.cross now refuses vectors of two frames. homogeneous_weight stays int.
- Verified at 387b26e3: test/krrood_spatial_math_test 722 passed; pre-commit (format, krrood check) clean on the change. SemDT, giskard, coraplex not run locally (need ROS); callers of cross all use one frame.
- At 9fa919d7: merge probe vs cram2 main clean; fork CI failed only small_packages; upstream also coraplex_garmi_clean_up_demo.

Next
- Owner: post the replies in .claude/personal/review-replies/cram2-1019.md (notes branch), one per open thread of cram2#1019, and resolve the ones it marks.
- Read CI on 387b26e3 (fork and upstream).
- #524 (stacked) conflicts with main in 19 of its own files; resolve it on its own.
