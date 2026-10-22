# krrspatial

Points in the spaces they are given in: metric reference frames, such as the bodies of a
robot, and images, in pixels.

- `krrspatial.space`: `Space`, whatever coordinates are given in, and `ImageSpace`, the
  pixel coordinate system of an image.
- `krrspatial.reference_frame`: `ReferenceFrame`, the metric space that positions and
  directions are expressed in, and how serialized values refer to one.
- `krrspatial.planar_point`: `PlanarPoint`, a point given by two coordinates in a space.
  Each implementation binds the kind of space and what its coordinates are stored as.

```python
from dataclasses import dataclass

from krrspatial.planar_point import PlanarPoint
from krrspatial.space import ImageSpace


@dataclass
class PositionOnImage(PlanarPoint[ImageSpace, float]):
    x: float
    y: float
    space: ImageSpace
```
