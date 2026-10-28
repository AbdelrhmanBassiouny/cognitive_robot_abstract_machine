# krrspatial

Points in the spaces they belong to, and the coordinate systems their coordinates are
given in.

- `krrspatial.space`: `Space`, a set of points with a geometry, and `EuclideanSpace`,
  physical space in metres.
- `krrspatial.coordinate_system`: `CoordinateSystem`, what coordinates on one space are
  given in; `CoordinateRepresentation`, a point, direction or orientation given by its
  coordinates in a coordinate system;
  `CoordinateChange`, between two coordinate systems of the same space, which can be
  inverted and composed; `AffineCoordinateChange`, one that keeps straight lines; and
  `RigidCoordinateChange`, an affine one that also keeps distances and angles.
- `krrspatial.reference_frame`: `ReferenceFrame`, the coordinate system of physical
  space that positions and directions are expressed in, and how serialized values refer
  to one.
- `krrspatial.planar_point`: `PlanarPoint`, a coordinate representation of a point by
  two coordinates. Each implementation binds the kind of coordinate system and what
  its coordinates are stored as.
- `krrspatial.spatial_types`, with the extra `krrspatial[casadi]`: `Point2`, `Point3`,
  `Vector3`, `RotationMatrix`, `Quaternion`, `AxisAngle`,
  `HomogeneousTransformationMatrix`, `Pose` and `Pose2D`, as symbolic expressions that
  can also hold plain numbers.

| Space | Coordinate system | Coordinate change | Kept by the change |
|---|---|---|---|
| `EuclideanSpace` | `ReferenceFrame`, metres | `RigidCoordinateChange` | distances, angles |

Other domain models add their own spaces on these interfaces; `krrimage`, for example,
adds image planes, whose coordinate systems are related by affine changes.

Points of two spaces, such as a body and an image of it, relate only through a map
between the spaces, such as a camera, never through a coordinate change.

```python
from krrspatial.spatial_types import HomogeneousTransformationMatrix, Point3

table_T_cup = HomogeneousTransformationMatrix.from_xyz_rpy(x=1.0, yaw=0.5)
cup_in_table = table_T_cup @ Point3(0.1, 0.0, 0.2)
```
