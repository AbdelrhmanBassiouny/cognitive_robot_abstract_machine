# domain-models — standing rules

- A domain model depends on `krrood`, on other domain models and on libraries outside this repository.
- Never duplicate a class to drop a dependency, and never keep two implementations of one concept (no numeric copy of the symbolic spatial types).
- krrspatial is the one home of spatial types: base krrspatial holds the casadi-free interfaces (Space, CoordinateSystem, ReferenceFrame, ImageCoordinateSystem, CoordinateChange, AffineCoordinateChange, RigidCoordinateChange, PlanarPoint); points, vectors, rotations and transforms sit behind krrspatial[casadi].
- A space is a point set (EuclideanSpace, ImagePlane); points refer to a CoordinateSystem on it, never to the space. A change within one space implements the CoordinateChange kind naming what it keeps, bound to its coordinate-system kind (RigidCoordinateChange for ReferenceFrame, AffineCoordinateChange for image crops and resizes); a map between spaces is a Projection.
- Every 2D point implements PlanarPoint[CoordinateSystemT, CoordinateT], binding both parameters exactly once; ImagePoint is krrimage's PlanarPoint[ImageCoordinateSystem, float], Pixel stays a grid cell. Mapping an image point to a metric point is a projection behind an optional extra.
- Every map between 2D and 3D (orthogonal projection, camera model) implements krrspatial's Projection: project, projection_line, unproject. An image reaches a ReferenceFrame only through a Projection, never by being one.
- Moved classes stay importable from their old module, so old imports and JSON type names keep resolving.
- Package names (krrspatial, krrimage, krrollywood) are open to change in review.
