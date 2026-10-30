PR #527 (draft, base main): krrood_spatial_math's casadi-free base (was krrspatial). Plan: domain-models, item planar-point-interface. Decisions: https://claude.ai/artifact/SCiXWvLcV7mequpATSTrsS

Plan
- Space > EuclideanSpace (dimension classproperty) > EuclideanSpace2D, EuclideanSpace3D; CoordinateSystem[SpaceT] > AffineFrame > CartesianFrame > CartesianFrame3D; CoordinateRepresentation (AffinePoint2D is one); CoordinateChange with AffineCoordinateChange[AffineFrameT] and RigidCoordinateChange[CartesianFrameT]. Image spaces are krrimage's.

Done
- ImagePlane and ImageCoordinateSystem moved to krrimage (5af267fe). IdentifiedObject keeps public id and name (owner's call).
- Resolve 2026-10-29: merged main (fadbfe22; cramera is cramph now, main's dir= fix clears the krrood job). Renamed the package krrood_spatial_math (6583f4da). Frame types, CartesianFrame3D (+Resolver, Reference, MissingCartesianFrame3DResolver), AffinePoint2D, CoordinateT docstring (6c0cdb80). 34 tests pass. Answered and resolved Simon's four threads.
- Carried into #526 (fa112d44, e6dae425): express, ReferenceFrameMismatchError and spatial types on the renamed modules; SemDT readers renamed. 59 krrood_spatial_math and 355 SemDT spatial-type tests pass locally.
- Review 2: EuclideanSpace3D under CartesianFrame3D, EuclideanSpace and README/pyproject wording, krrood_image (c3b514c7; 36 pass); six threads resolved; merged into #526 (4dee7cdb, 61 + 355 pass).
- Review 3: dimension classproperty and EuclideanSpace2D (10b3b7b2, 40 pass), with main's Docker import fix merged; into #526 (85b67b09, 65 pass).
- StoredFrames test mixin, so each mimic names one change kind (81241f19); into #526 (3eccd14c).
- Not carried into #524: its merge hits main's HSV Color in geometry.py, which #524 has to re-move first.

Next
- CI waits on the fixed CI image (#536). Owner resolves the IdentifiedObject thread. Promote before #526/#524.
