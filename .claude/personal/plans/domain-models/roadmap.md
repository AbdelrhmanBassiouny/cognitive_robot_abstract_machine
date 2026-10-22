# domain-models — standing rules

- A domain model depends on `krrood`, on other domain models and on libraries outside this repository.
- Never duplicate a class to drop a dependency, and never keep two implementations of one concept (no numeric copy of the symbolic spatial types).
- krrspatial is the one home of points, vectors, rotations and transforms (casadi). A package that needs none of them does not depend on it.
- Pixels and image coordinates are krrimage's own types, not spatial types; turning one into a spatial point is an explicit step behind an optional extra.
- Every map between 2D and 3D (orthogonal projection, camera model) implements krrspatial's Projection: project, preimage, embed.
- Moved classes stay importable from their old module, so old imports and JSON type names keep resolving.
- Package names (krrspatial, krrimage, krrollywood) are open to change in review.
