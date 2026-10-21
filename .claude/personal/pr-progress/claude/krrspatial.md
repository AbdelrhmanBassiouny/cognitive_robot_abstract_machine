PR #526 (draft, stacked on #512): domain_models/krrspatial, numeric planar points and vectors. Plan: domain-models.

Plan
- ReferenceFrame; Point2/Vector2 generic over coordinate type; Float/Integer numeric types.

Done
- Package, wiring (workspace, CI, version test), 19 tests pushed.

Next
- Review; then restack #524 onto this branch and replace ImagePoint/Pixel.
- Later: 3D, transforms, krrspatial[symbolic] (SemDT casadi types).
