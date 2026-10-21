# krrspatial

Points and vectors in reference frames, free of any robot or world model. It depends only
on `krrood`, so a package that needs positions and directions can use it without the
semantic digital twin or casadi.

- `krrspatial.reference_frame`: `ReferenceFrame`, the interface of whatever positions and
  directions are expressed in.
- `krrspatial.spatial_types`: `Point2` and `Vector2`, the interfaces every implementation
  provides, generic over the type of their coordinates.
- `krrspatial.numeric`: implementations with plain numbers as coordinates.
  `FloatPoint2` and `FloatVector2` hold any number, `IntegerPoint2` and
  `IntegerVector2` whole numbers, such as pixels.

```python
from krrspatial.numeric import FloatPoint2, IntegerPoint2

start = FloatPoint2(1.0, 2.0)
end = FloatPoint2(4.0, 6.0)
length = (end - start).norm()
pixel = IntegerPoint2.nearest(end)
```
