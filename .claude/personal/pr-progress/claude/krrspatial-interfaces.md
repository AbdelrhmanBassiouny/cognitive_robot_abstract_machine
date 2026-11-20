Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq
- Resolve 2026-11-20 (owner's answers): remove SymbolicAxisCoordinates by a CoordinateRepresentation hook giving the constructor arguments that place a value in a coordinate system, overridden once by SymbolicSpatialValue. Remove CrossProductVector: CartesianFrame3Dimensional.cross_product computes it from coordinates like CartesianFrame.inner_product, AffineFrame raises FrameHasNoCrossProductError, Vector.cross asks its frame kind like Vector.dot, MotionVectorPair binds Vector. homogeneous_weight stays int (reply only).

Done
- ec8ffb34: how a change moves a value lives in the abstract layer; SpecialEuclideanGroupAction/HomogeneousCoordinates removed; cross keyword-only.
- 6d20eaa1 merges cram2 main 82707c74. 9fa919d7: to_coordinate_change is the only pose/orientation accessor; HTM3D.dot keyword-only.
- Read at 9fa919d7: merge probe vs cram2 main clean; fork CI fails only small_packages (krrood check); upstream also fails coraplex_garmi_clean_up_demo; cram2#1019 has 22 unresolved threads, 16 outdated and done.

Next
- Implement the two removals test-first; re-run spatial-math, krrood pattern and SemDT spatial tests.
- Redraft the replies for cram2#1019 (the earlier draft was in a lost scratchpad) for the owner to post.
