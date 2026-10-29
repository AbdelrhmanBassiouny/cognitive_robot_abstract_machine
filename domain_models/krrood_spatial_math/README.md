# krrood_spatial_math

Points in the spaces they belong to, and the coordinate systems their coordinates are
given in.

- `krrood_spatial_math.space`: `Space`, a set of points with a geometry, and
  `EuclideanSpace`, physical space in metres.
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
- `krrood_spatial_math.affine_point`: `AffinePoint2D`, a point given by its two
  coordinates in an affine frame. Each implementation binds the kind of frame and what
  its coordinates are stored as.
- `krrood_spatial_math.spatial_types`, with the extra `krrood_spatial_math[casadi]`:
  `Point2`, `Point3`, `Vector3`, `RotationMatrix`, `Quaternion`, `AxisAngle`,
  `HomogeneousTransformationMatrix`, `Pose` and `Pose2D`, as symbolic expressions that
  can also hold plain numbers.

| Space | Frame | Coordinate change | Kept by the change |
|---|---|---|---|
| `EuclideanSpace` | `CartesianFrame3D`, metres | `RigidCoordinateChange` | distances, angles |

Other domain models add their own spaces on these interfaces; `krrimage`, for example,
adds image planes, whose pixel frames are affine and related by affine changes.

Points of two spaces, such as a body and an image of it, relate only through a map
between the spaces, such as a camera, never through a coordinate change.

```python
from krrood_spatial_math.spatial_types import HomogeneousTransformationMatrix, Point3

table_T_cup = HomogeneousTransformationMatrix.from_xyz_rpy(x=1.0, yaw=0.5)
cup_in_table = table_T_cup @ Point3(0.1, 0.0, 0.2)
```
