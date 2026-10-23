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

| Space | Coordinate system | Coordinate change | Kept by the change |
|---|---|---|---|
| `EuclideanSpace` | `ReferenceFrame`, metres | rigid transform | distances, angles |
| `ImagePlane` | `ImageCoordinateSystem`, pixels | scaling and shifting each axis (crop, resize) | ratios along an axis |

Points of two spaces, such as a body and an image of it, relate only through a map
between the spaces, such as a camera, never through a coordinate change.

```python
from dataclasses import dataclass

from krrspatial.coordinate_system import ImageCoordinateSystem
from krrspatial.planar_point import PlanarPoint


@dataclass
class PositionOnImage(PlanarPoint[ImageCoordinateSystem, float]):
    x: float
    y: float
    coordinate_system: ImageCoordinateSystem
```
