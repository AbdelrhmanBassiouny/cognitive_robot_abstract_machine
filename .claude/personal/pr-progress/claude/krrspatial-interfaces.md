## Plan
- 2026-11-18 review (9 threads): rename HomogeneousTransformationMatrix -> HomogeneousTransformationMatrix3Dimensional, SymbolicSpatialValue -> SymbolicSpatialValue3Dimensional, SymbolicPlanarValue -> SymbolicSpatialValue2Dimensional (owner approved).
- Fold world-as-euclidean-space in: World implements EuclideanSpace3Dimensional, KinematicStructureEntity.space returns _world, CoordinateSystem.space abstract, express_in_own_frame checks spaces first.
- FloorPlan gives planar points, not arrays; point tests check behaviour; answer flatten/frameless threads, with a figure artifact.
- Keep #527 ready (owner said so, again 2026-11-18).

## Done
- Stack pass: main c6014b62 merged (d350bf25), merge probe clean. No cram2 PR yet.

## Next
- Implement the plan, run tests, push with maintenance push, reply on every thread.
- #524 conflicts with this branch: needs /plan-item-resolve 524.
