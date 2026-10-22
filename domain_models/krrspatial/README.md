# krrspatial

Points, vectors, rotations and transformations in reference frames, as symbolic
expressions that can also hold plain numbers.

- `krrspatial.reference_frame`: `ReferenceFrame`, the interface of whatever positions and
  directions are expressed in.
- `krrspatial.spatial_types`: `Point2`, `Point3`, `Vector3`, `RotationMatrix`,
  `Quaternion`, `AxisAngle`, `HomogeneousTransformationMatrix`, `Pose` and `Pose2D`.

```python
from krrspatial.spatial_types import HomogeneousTransformationMatrix, Point3

table_T_cup = HomogeneousTransformationMatrix.from_xyz_rpy(x=1.0, yaw=0.5)
cup_in_table = table_T_cup @ Point3(0.1, 0.0, 0.2)
```
