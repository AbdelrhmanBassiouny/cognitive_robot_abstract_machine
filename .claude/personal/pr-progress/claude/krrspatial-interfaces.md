Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.

Done
- f4179d91 merges cram2 main 38804f6f; probe clean at b94baaf4.
- ecf34a48/eb339524: derived generic parameters; Point[vector], Line[point], LineSegment[line]; AxisCoordinate; metric on frames; one SymbolicSpatialValue; one SE interface.
- aaadf0e6/d03875ba/72d1d766: RotationMatrix is a transformation (SO(3) subgroup); no SO interface or x/y/z setters; planar values stay on their plane; gcs and giskard project explicitly.
- ba90e001: DerivedGenericParameterConflictError, AGENTS rule, krrood docs page. b94baaf4: Point docstring as the affine definition.

Next
- Owner: post replies from scratchpad cram2-1019-replies.md (all threads drafted, incl. :478, :494, :1720, :1999, 2D :53/:178). No reply to LucaKro.
- Read CI on b94baaf4 (giskard fix 72d1d766 not run locally); small_packages fails only on krrood check --since HEAD^1 (set aside).
- Optional: VectorPair adjoint action, then SE interface on SymbolicSpatialValue.
