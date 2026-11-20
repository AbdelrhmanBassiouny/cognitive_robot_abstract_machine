Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.
- Design doc (agreed, not implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- 80066fb8: values bind their change type; one transform on SymbolicSpatialType; ValueOnEmbeddedPlane gone; giskard T.rotation_matrix @ R. da13cf2b merges cram2 main 9b8526c8; probe clean.
- aaadf0e6: planar transform onto another plane (parallel too) raises; answers Luca's height thread.

Next
- Implement the doc: Point derives GenericCoordinateChange (moved to coordinate_system.py); apply_transformation (name kept) lives in the abstract layer for Vector/Point (homogeneous weight), Pose, Orientation, VectorPair (adjoint); drop SpecialEuclideanGroupAction and HomogeneousCoordinates. Open: cross keyword-only (32 callers).
- Draft replies for :1767, :317, :1378, cartesian_monitors :140; earlier drafts in scratchpad cram2-1019-replies.md. No reply to LucaKro.
- Upstream CI: garmi demo and small_packages fail (logs show only exit 1).
