# krrspatial

Points in the spaces they belong to, and the coordinate systems their coordinates are
given in.

- `krrspatial.space`: `Space`, a set of points with a geometry; `EuclideanSpace`, physical
  space in metres; and `ImagePlane`, the plane an image shows.
- `krrspatial.coordinate_system`: `CoordinateSystem`, what coordinates on one space are
  given in; `ImageCoordinateSystem`, pixels from an image's top left corner; and
  `CoordinateChange`, between two coordinate systems of the same space.
- `krrspatial.reference_frame`: `ReferenceFrame`, the coordinate system of physical
  space that positions and directions are expressed in, and how serialized values refer
  to one.
- `krrspatial.planar_point`: `PlanarPoint`, a point given by two coordinates in a
  coordinate system. Each implementation binds the kind of coordinate system and what
  its coordinates are stored as.
- `krrspatial.spatial_types`, with the extra `krrspatial[casadi]`: `Point2`, `Point3`,
  `Vector3`, `RotationMatrix`, `Quaternion`, `AxisAngle`,
  `HomogeneousTransformationMatrix`, `Pose` and `Pose2D`, as symbolic expressions that
  can also hold plain numbers.

| Space | Coordinate system | Coordinate change | Kept by the change |
|---|---|---|---|
| `EuclideanSpace` | `ReferenceFrame`, metres | rigid transform | distances, angles |
| `ImagePlane` | `ImageCoordinateSystem`, pixels | scaling and shifting each axis (crop, resize) | ratios along an axis |

Points of two spaces, such as a body and an image of it, relate only through a map
between the spaces, such as a camera, never through a coordinate change.

```python
from krrspatial.spatial_types import HomogeneousTransformationMatrix, Point3

table_T_cup = HomogeneousTransformationMatrix.from_xyz_rpy(x=1.0, yaw=0.5)
cup_in_table = table_T_cup @ Point3(0.1, 0.0, 0.2)
```
