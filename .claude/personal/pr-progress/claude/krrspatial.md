PR #526 (ready, user-approved; upstream link recorded): domain_models/krrspatial, numeric planar points and vectors. Plan: domain-models.

Plan
- ReferenceFrame; Point2/Vector2 generic over coordinate type; Float/Integer numeric types.

Done
- Package, wiring (workspace, CI, version test), 19 tests pushed.
- Review addressed; IntegerVector2 kept; Planar renamed Coordinates2 (76c649aac9).

Next
- User clicks Create upstream; maintenance pass reparents onto main. Restack #524 onto this branch and replace ImagePoint/Pixel.
- Later: 3D, transforms, krrspatial[symbolic] (SemDT casadi types).
