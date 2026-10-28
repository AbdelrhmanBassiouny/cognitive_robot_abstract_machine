# domain-models — standing rules

- A domain model depends on `krrood`, on other domain models and on libraries outside this repository.
- Never duplicate a class to drop a dependency, and never keep two implementations of one concept (no numeric copy of the symbolic spatial types).
- krrspatial is the one home of spatial types: base krrspatial holds the casadi-free interfaces (Space, EuclideanSpace, CoordinateSystem, ReferenceFrame, CoordinateRepresentation, CoordinateChange, AffineCoordinateChange, RigidCoordinateChange, PlanarPoint); points, vectors, rotations and transforms sit behind krrspatial[casadi]. Image spaces (ImagePlane, ImageCoordinateSystem) are krrimage's.
- A space is a point set (EuclideanSpace, ImagePlane); values are CoordinateRepresentations of a CoordinateSystem on it, never of the space. A change within one space implements the CoordinateChange kind naming what it keeps, bound to its coordinate-system kind (rigid for ReferenceFrame, affine for image crops and resizes); a map between spaces is a Projection.
- Every 2D point implements PlanarPoint[CoordinateSystemT, CoordinateT], binding both parameters exactly once; ImagePoint is krrimage's PlanarPoint[ImageCoordinateSystem, float], Pixel stays a grid cell. Mapping an image point to a metric point is a projection behind an optional extra.
- Every map between 2D and 3D (orthogonal projection, camera model) implements krrspatial's Projection: project, projection_line, unproject. An image reaches a ReferenceFrame only through a Projection, never by being one.
- Dimension belongs to a space, not to its values or changes. A world is the space its bodies chart, one space per world; a frame not in a world has no space. A 2D value is given in a plane's coordinate system, which a 3D frame induces.
- One image plane per sensor, shared by every image it takes; an image is pixels in an ImageCoordinateSystem on it. Where and when an image was taken is a Capture role on the image, never fields of the image.
- Perception adopts these types only after cram2#761 and #795 land, never by asking an open upstream PR to depend on an unmerged domain model. #761's CameraModel and CameraObservation are moved and retyped (Projection, Capture), never rewritten beside them.
- Moved classes stay importable from their old module, so old imports and JSON type names keep resolving.
- Package names (krrspatial, krrimage, krrollywood) are open to change in review.
