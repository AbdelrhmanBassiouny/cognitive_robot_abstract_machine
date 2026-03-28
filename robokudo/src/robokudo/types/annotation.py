"""Annotation types for robokudo.

This module provides various annotation types used for object classification,
semantic information, location data, geometric shapes, and pose information.
All annotation types inherit from the base Annotation class.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING, Optional, Any, List

import numpy as np

from robokudo.types.core import Annotation
from robokudo.types.cv import BoundingBox3D, Points3D
from robokudo.types.tf import (
    Position,
    Pose,
    StampedPose,
    StampedPosition,
    StampedTransform,
)

if TYPE_CHECKING:
    import numpy.typing as npt


@dataclass
class Classification(Annotation):
    """Classification annotation for objects.

    This class represents a classification result, including the type of classification
    (instance, class, or shape), the class name, confidence score, and class ID.
    """

    classification_type: str = ""
    """
    Type of classification (INSTANCE, CLASS, or SHAPE)
    """

    classname: str = ""
    """
    Name of the classified class
    """

    confidence: float = 0.0
    """
    Confidence score of the classification
    """

    class_id: int = 0
    """
    Numeric identifier for the class
    """


@dataclass
class SemanticColor(Annotation):
    """Semantic color annotation.

    This class represents semantic color information, including the color name
    and its ratio/proportion in the annotated object or region.
    """

    color: str = ""
    """
    Name of the color
    """

    ratio: float = 0.0
    """
    Proportion/ratio of this color in the object/region
    """


@dataclass
class LocationAnnotation(Annotation):
    """Location annotation for objects.

    This class represents a named location in the environment.
    """

    name: str = ""
    """
    Name of the location
    """


@dataclass
class Plane(Annotation):
    """Plane annotation for surface detection.

    This class represents a detected plane in 3D space, including its model
    parameters and inlier points.
    """

    model: List[float] = field(default_factory=list)
    """
    4-dimensional plane equation parameters [a, b, c, d] for ax + by + cz + d = 0
    """

    inliers: List[int] = field(default_factory=list)
    """
    List of pointcloud indices that belong to this plane
    """


@dataclass
class Shape(Annotation):
    """Base class for shape annotations.

    This class serves as a base for specific shape types like Cuboid and Sphere.
    """

    inliers: List[int] = field(default_factory=list)
    """
    List of pointcloud indices that belong to this shape
    """

    type: str = ""
    """
    Type of the shape (e.g., 'Cuboid', 'Sphere')
    """


@dataclass
class Cuboid(Shape):
    """Cuboid shape annotation.

    This class represents a cuboid shape defined by three plane equations.
    """

    model: List = field(default_factory=list)
    """
    Three plane equations defining the cuboid, shape (3,4)
    """


@dataclass
class Sphere(Shape):
    """Sphere shape annotation.

    This class represents a sphere shape defined by its center and radius.
    """

    radius: float = 0.0
    """
    Radius of the sphere
    """

    center: npt.NDArray[np.float32] = field(default_factory=lambda: np.zeros(3))
    """
    Center coordinates of the sphere in (x, y, z)
    """


@dataclass
class ColorHistogram(Annotation):
    """Color histogram annotation.

    This class usually represents a 2D color histogram, typically containing hue and
    saturation information.
    """

    hist: Optional[npt.NDArray] = None
    """
    2D histogram array
    """

    normalized: bool = False
    """
    Whether the histogram is normalized
    """


@dataclass
class PoseAnnotation(Pose, Annotation):
    """Pose annotation combining transform and annotation functionality.

    This class inherits from both Pose and Annotation to provide pose information
    as an annotation type.
    """

    ...


@dataclass
class PositionAnnotation(Position, Annotation):
    """Position annotation combining position and annotation functionality.

    This class inherits from both Position and Annotation to provide position
    information as an annotation type.
    """

    ...


@dataclass
class StampedPoseAnnotation(StampedPose, Annotation):
    """Timestamped pose annotation.

    This class combines timestamped pose information with annotation functionality.
    """

    ...


@dataclass
class StampedPositionAnnotation(StampedPosition, Annotation):
    """Timestamped position annotation.

    This class combines timestamped position information with annotation functionality.
    """

    ...


@dataclass
class StampedTransformAnnotation(StampedTransform, Annotation):
    """Timestamped transform annotation.

    This class combines timestamped transform information with annotation functionality.
    """

    ...


@dataclass
class Encoding(Annotation):
    """An abstract Encoding Type.

    This class represents various types of encodings such as feature vectors,
    latent space representations, or other variables.
    """

    encoding: Any = None
    """
    The encoded representation
    """


@dataclass
class BoundingBox3DAnnotation(BoundingBox3D, Annotation):
    """3D bounding box annotation.

    This class combines 3D bounding box functionality with annotation capabilities.
    """

    ...


@dataclass
class CloudAnnotation(Points3D, Annotation):
    """Point cloud annotation.

    This class combines 3D point cloud functionality with annotation capabilities.
    """

    ...


@dataclass
class SpatiallyNearestAnnotation(Annotation):
    """
    Annotation to describe the spatially nearest object to the camera.
    Supposed to be unique for an amount of objects or humans.
    """

    ...


@dataclass
class TextAnnotation(Annotation):
    """Text annotation."""

    text: str = ""
    """
    Text content of the annotation
    """
