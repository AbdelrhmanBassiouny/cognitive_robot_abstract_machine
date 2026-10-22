PR #527 (draft, base main): krrspatial's casadi-free base, the PR #526 and #524 stack on. Plan: domain-models, item planar-point-interface.

Plan
- Space/ImageSpace/ReferenceFrame, PlanarPoint[SpaceT, CoordinateT], frame serialization, krrood ObjectReference; deps krrood only.

Done
- Pushed 08010edf00; 15 tests pass locally; #526 and #524 merged it and retargeted onto it.

Next
- Read CI. Promote before #526/#524; Projection/FrameTransformer stay with their own items.
