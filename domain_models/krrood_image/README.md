# krrood_image

Images, the planes they lie on, and the positions, boxes and colours on them, free of any
robot or world model. It depends only on `krrood`, the casadi-free base of
`krrood_spatial_math`, `numpy` and `opencv-python`, so a package that renders, records or
perceives images can use it without the semantic digital twin, ROS, casadi or a physics
simulator.

- `krrood_image.coordinates`: `ImagePlane`, the plane every image a camera takes lies
  on; `ImageCoordinateSystem`, pixels on it from one image's top left corner; and
  `Resolution`, `ImagePoint`, `ImageVector`, `ImageBox`, `Pixel` and `PixelBox`, given in
  such a coordinate system.
- `krrood_image.image`: `ColorImage`, red, green and blue bytes, with drawing that
  returns a new image.
- `krrood_image.color`: `Color`, which the semantic digital twin also uses for its
  shapes.

```python
from krrood_image.color import Color
from krrood_image.coordinates import ImageBox, Resolution
from krrood_image.image import ColorImage

image = ColorImage.uniform(
    resolution=Resolution(width=640, height=480), color=Color.BLACK()
)
image = image.framed(
    around=ImageBox.from_corner_and_size(left=100, top=80, width=200, height=120),
    color=Color.RED(),
)
```
