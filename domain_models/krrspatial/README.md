# krrspatial

Points in the spaces they are given in: metric reference frames, such as the bodies of a
robot, and images, in pixels.

- `krrspatial.space`: `Space`, whatever coordinates are given in, and `ImageSpace`, the
  pixel coordinate system of an image.
- `krrspatial.reference_frame`: `ReferenceFrame`, the metric space that positions and
  directions are expressed in, and how serialized values refer to one.
- `krrspatial.planar_point`: `PlanarPoint`, a point given by two coordinates in a space.
  Each implementation binds the kind of space and what its coordinates are stored as.
- `krrspatial.spatial_types`, with the extra `krrspatial[casadi]`: `Point2`, `Point3`,
  `Vector3`, `RotationMatrix`, `Quaternion`, `AxisAngle`,
  `HomogeneousTransformationMatrix`, `Pose` and `Pose2D`, as symbolic expressions that
  can also hold plain numbers.

```python
from krrspatial.spatial_types import HomogeneousTransformationMatrix, Point3

table_T_cup = HomogeneousTransformationMatrix.from_xyz_rpy(x=1.0, yaw=0.5)
cup_in_table = table_T_cup @ Point3(0.1, 0.0, 0.2)
```
