# krrimage

Images and the positions, boxes and colours on them, free of any robot or world model.
It depends only on `krrood`, `numpy` and `opencv-python`, so a package that renders,
records or perceives images can use it without the semantic digital twin, ROS or a
physics simulator.

- `krrimage.coordinates`: `ImagePlane`, the plane an image shows, which crops and
  resizes of it share; `ImageCoordinateSystem`, pixels on it from an image's top left
  corner; and `Resolution`, `ImagePoint`, `ImageBox`, `Pixel` and `PixelBox`, given in
  such a coordinate system.
- `krrimage.image`: `ColorImage`, red, green and blue bytes, with drawing that returns a
  new image.
- `krrimage.color`: `Color`, which the semantic digital twin also uses for its shapes.

```python
from krrimage.color import Color
from krrimage.coordinates import ImageBox, Resolution
from krrimage.image import ColorImage

image = ColorImage.of_color(Resolution(width=640, height=480), Color.BLACK())
image = image.framed(ImageBox.from_corner_and_size(100, 80, 200, 120), Color.RED())
```
