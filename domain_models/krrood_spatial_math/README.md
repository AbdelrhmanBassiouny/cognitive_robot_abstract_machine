# krrood_spatial_math

The spatial mathematics that robot and image packages share. It models a space, such as
the physical space a robot moves in or the plane an image lies on, separately from the
coordinate systems on it, so that a value always says which coordinate system its
coordinates are given in, and coordinates are only combined after changing them into one
coordinate system. Its base depends on `krrood` alone.

- `krrood_spatial_math.space`: `Space`, a set of points with a geometry;
  `EuclideanSpace`, one with distances and angles, whose `dimension` each subclass
  fixes; `EuclideanSpace2D`, such as the floor a robot drives on; and
  `EuclideanSpace3D`, such as the physical space a robot's bodies are in.
- `krrood_spatial_math.coordinate_system`: `CoordinateSystem`, what coordinates on one
  space are given in; `AffineFrame`, one with an origin and straight axes, and
  `CartesianFrame`, an affine frame whose axes are perpendicular and of unit length;
  `CoordinateRepresentation`, a point, direction or orientation given by its
  coordinates in a coordinate system;
  `CoordinateChange`, between two coordinate systems of the same space, which can be
  inverted and composed; `AffineCoordinateChange`, between affine frames, which keeps
  straight lines; and `RigidCoordinateChange`, between Cartesian frames, which also
  keeps distances and angles.
- `krrood_spatial_math.cartesian_frame_3d`: `CartesianFrame3D`, the right-handed
  Cartesian frame of physical space that positions and directions are expressed in,
  and how serialized values refer to one.
- `krrood_spatial_math.cartesian_frame_2d`: `CartesianFrame2D`, the right-handed
  Cartesian frame that values on a plane, such as the x-y plane of a
  `CartesianFrame3D`, are given in.
- `krrood_spatial_math.affine_point`: `AffinePoint`, a point given by its coordinates in
  an affine frame, and `CartesianPoint`, one given in a Cartesian frame. Each
  implementation binds the kind of frame, what its coordinates are stored as and the
  kind of vector that moves it; the frame's space fixes how many coordinates it has.
- `krrood_spatial_math.affine_vector`: `AffineVector`, a translation of an affine space,
  and `CartesianVector`, one with a length. The difference of two points is a vector,
  and a point moved by a vector is a point.
- `krrood_spatial_math.affine_line`: `AffineLine`, the straight line through a point
  along a vector.
- `krrood_spatial_math.space_map`: `SpaceMap`, a map from the points of one space to
  those of another, such as a camera, and `OrthogonalProjection`, one onto a plane along
  its normal.
- `krrood_spatial_math.spatial_types`, with the extra `krrood_spatial_math[casadi]`:
  `CartesianPoint2D`, `CartesianPoint3D`, `Vector2D`, `Vector3D`, `Line3D`,
  `RotationMatrix`, `Quaternion`, `AxisAngle`, `HomogeneousTransformationMatrix`, `Pose3D`
  and `Pose2D`, as symbolic expressions that can also hold plain numbers. The 2D values
  lie on the x-y plane of their reference frame, a `FramePlane`, and are given in its
  `PlanarFrame`; `HomogeneousTransformationMatrix2D` is the rigid change between two
  frames on one plane, and `FramePlaneProjection` the orthogonal projection onto a
  frame's plane.

| Space | Frame | Coordinate change | Kept by the change |
|---|---|---|---|
| `EuclideanSpace3D` | `CartesianFrame3D`, metres | `RigidCoordinateChange` | distances, angles |
| `EuclideanSpace2D` | `CartesianFrame2D`, metres | `RigidCoordinateChange` | distances, angles |

Other domain models add their own spaces on these interfaces; `krrood_image`, for
example, adds image planes, whose pixel frames are affine and related by affine changes.

Points of two spaces, such as a body and an image of it, relate only through a map
between the spaces, such as a camera, never through a coordinate change.
