PR #527 (draft, base main): krrood_spatial_math's casadi-free base (was krrspatial). Plan: domain-models, item planar-point-interface. Decisions: https://claude.ai/artifact/SCiXWvLcV7mequpATSTrsS

Plan (resolve, 2026-10-29)
- Merge main: drop cramera (now cramph) from pyproject.toml and ci.yml; main's dir= fix turns the krrood job green.
- Rename krrspatial to krrood_spatial_math: directory, package, tests, CI lib, workspace pyproject.
- AffineFrame and CartesianFrame under CoordinateSystem; AffineCoordinateChange[AffineFrameT], RigidCoordinateChange[CartesianFrameT].
- ReferenceFrame to CartesianFrame3D, with CartesianFrame3DResolver, CartesianFrame3DReference, MissingCartesianFrame3DResolver, and the test mimics.
- PlanarPoint to AffinePoint2D, bound to AffineFrame; CoordinateT kept with the design doc's docstring.
- Docstrings from the doc's #527 table ("serialized coordinate representations"); reply on and resolve the four threads.
- Carry into #526 and #524.

Done
- Review: ImagePlane and ImageCoordinateSystem moved to krrimage (5af267fe). IdentifiedObject keeps public id and name (owner's call).
