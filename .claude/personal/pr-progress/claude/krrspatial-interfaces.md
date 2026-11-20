Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.

Done
- da13cf2b merges cram2 main 9b8526c8 (krrood split into distributions); probe clean at da13cf2b.
- ecf34a48/eb339524/ba90e001: derived generic parameters, Point[vector], Line[point], LineSegment[line], conflict error, AGENTS rule, docs page.
- aaadf0e6/d03875ba/72d1d766: RotationMatrix is an SO(3) transformation; planar values stay on their plane.
- 80066fb8: values bind SymbolicSpatialValue[change type]; one transform via from_transformation; ValueOnEmbeddedPlane removed; derived params of all bases apply; giskard uses T.rotation_matrix @ R.

Next
- Owner: post replies from scratchpad cram2-1019-replies.md (all threads drafted, incl. 2D :1/:50/:87 and giskard :674). No reply to LucaKro.
- Read CI on da13cf2b. Upstream garmi demo failed on b94baaf4; log unreadable here (needs cram2 API access). small_packages krrood check findings: owner leaves them.
- Optional: VectorPair adjoint action, then SE interface on SymbolicSpatialValue.
