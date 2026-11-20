Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.

Done
- f4179d91 merges cram2 main 38804f6f; probe clean at d03875ba.
- ecf34a48/eb339524: derived generic parameters; Point[vector], Line[point], LineSegment[line]; AxisCoordinate fields; metric on frames; one SymbolicSpatialValue; one SE interface.
- aaadf0e6: RotationMatrix is a HomogeneousTransformationMatrix3Dimensional (SO(3) subgroup); SpecialOrthogonalGroupAction gone; no x/y/z setters; planar transform refuses other planes (ValueOnEmbeddedPlane); RotationMatrixMapping derives the transform mapping.
- d03875ba: planar graph of boxes projects points onto its search plane explicitly.

Next
- Owner: post replies (scratchpad cram2-1019-replies.md covers threads up to eb339524; threads :478, :494 are answered by aaadf0e6; :1720, :1999, 2D :53/:178 need frame kinds to name their value types - not started). No reply to LucaKro, per owner.
- Read CI on d03875ba (cram2 failed small_packages and garmi demo at eb339524, logs unread).
- krrood check: planar transform override stays positional (owner's choice).
