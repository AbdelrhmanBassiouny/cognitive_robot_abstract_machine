"""
Common Analysis Structure (CAS) for RoboKudo.

This module provides the core data structure used throughout RoboKudo for storing
and managing data during pipeline execution. The CAS (Common Analysis Structure)
holds sensor data, annotations, and other information that is shared between
annotators.

The module provides:

* Standard view definitions for common data types
* Methods for storing and retrieving data
* Support for annotations and filtering
* Timestamp management
"""

from __future__ import annotations
import copy
from datetime import datetime
import time
from dataclasses import dataclass, field
from typing import TypeVar

from typing_extensions import TYPE_CHECKING, Any, Tuple, Dict, List, Type

if TYPE_CHECKING:
    from .types.core import Annotation


class CASViews:
    """Standard view definitions for the Common Analysis Structure.

    This class defines the standard keys used to store and access different types
    of data in the CAS. These keys ensure consistent access to common data types
    like images, point clouds, and camera information.
    """

    COLOR_IMAGE: str = "color_image"
    """RGB image data"""

    DEPTH_IMAGE: str = "depth_image"
    """Depth image data"""

    COLOR2DEPTH_RATIO: str = "color2depth_ratio"
    """Scale factor to scale the `COLOR_IMAGE` to the resolution of the `DEPTH_IMAGE` in x, y format.
    
    Example: 1280x960 RGB, 640x480 DEPTH -> 0.5 along X and Y
    """

    CAM_INFO: str = "cam_info"
    """ROS camera info message coming from ROS"""

    CAM_INTRINSIC: str = "cam_intrinsic"
    """Open3D pinhole camera intrinsic model for RGB to be set by the camera driver."""

    PC_CAM_INTRINSIC: str = "pc_cam_intrinsic"
    """Camera intrinsic that has been used for point cloud generation."""

    CLOUD: str = "cloud"
    """Point cloud data"""

    CLOUD_ORGANIZED: str = "cloud_organized"
    """Organized point cloud data"""

    TIMESTAMP: str = "timestamp"
    """CAS creation timestamp, for percept timestamp use `CAM_INFO`"""

    QUERY: str = "query"
    """Query information"""

    VIEWPOINT_CAM_TO_WORLD: str = "viewpoint_cam_to_world"
    """Camera to world transform"""

    VIEWPOINT_WORLD_TO_CAM: str = "viewpoint_world_to_cam"
    """World to camera transform"""

    OBJECT_IMAGE: str = "object_image"
    """Object image data"""

    OBJECT_COLOR_MAP: str = "object_color_map"
    """Object color mapping data"""


@dataclass
class CAS:
    """The main data representation in RoboKudo.

    This class provides the central data structure used by annotators to store and
    retrieve information. Each pipeline has its own CAS instance that maintains
    views (singular data like sensor readings) and annotations (multiple descriptors
    of the same data).
    """

    timestamp: float = field(default_factory=time.time)
    """Unix timestamp when this CAS was created."""

    timestamp_readable: str = field(init=False)
    """Human readable timestamp string."""

    views: Dict[str, Any] = field(default_factory=dict)
    """Dictionary storing view data, each view stores data that is typically singular for a single CAS.
    
    Example: Sensor data, cam info and cloud which are read from the sensors.
    """

    annotations: List[Annotation] = field(default_factory=list)
    """
    List of annotations, each annotation describes a certain part of the acquired sensor data. In contrast to views
    there can be multiple annotations for the same 'thing' in the data.
    """

    def __post_init__(self):
        dt_timestamp = datetime.fromtimestamp(self.timestamp)
        self.timestamp_readable = dt_timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def get(self, view_name: str) -> Any:
        """Get a view by name.

        :param view_name: Name of the view to retrieve
        :return: The view data
        :raises KeyError: If the view does not exist
        """
        return self.views[view_name]

    def contains(self, view_name: str) -> bool:
        """Check if a view exists.

        :param view_name: Name of the view to check
        :return: True if the view exists
        """
        return view_name in self.views

    def get_copy(self, view_name: str) -> Any:
        """Get a deep copy of a view.

        :param view_name: Name of the view to copy
        :return: Deep copy of the view data
        :raises KeyError: If the view does not exist
        """
        return copy.deepcopy(self.views[view_name])

    def set(self, view_name: str, value: Any) -> None:
        """Put data in the CAS index by a given view name. This method will make a deepcopy of value.

        :param view_name: The name of the view which should be selected from constants in the CASView class.
        :param value: The value that will be placed in the CAS under view_name by making a deepcopy of it.
        """
        self.views[view_name] = copy.deepcopy(value)

    def set_ref(self, view_name: str, value: Any) -> None:
        """Put data in the CAS index by a given view name. In contrast to set(), this will not make a copy but just
        does an assignment.

        :param view_name: The name of the view which should be selected from constants in the CASView class.
        :param value: The value that will be placed in the CAS under view_name by making assigning it.
        """
        self.views[view_name] = value

    T = TypeVar("T")

    @staticmethod
    def filter_by_type(type_to_include: Type[T], input_list: List[Any]) -> List[T]:
        """Filter a list to include only objects of a specific type.

        :param type_to_include: Type to filter for
        :param input_list: List to filter
        :return: Filtered list containing only objects of the specified type
        """
        return [
            element for element in input_list if isinstance(element, type_to_include)
        ]

    def filter_annotations_by_type(self, type_to_include: Type[T]) -> List[T]:
        """
        Filter annotations to include only those of a specific type.

        :param type_to_include: Type to filter for
        :return: A filtered list of annotations in CAS
        """
        return CAS.filter_by_type(type_to_include, self.annotations)

    @staticmethod
    def _filter_objects(
            objects: List[Any], criteria: Dict[str, Tuple[str, Any]]
    ) -> List[Any]:
        """
        Filters a list of objects based on specified criteria.

        :param objects: List of objects to be filtered.
        :param criteria: A dictionary where keys are attribute names and values are tuples containing
                         the comparison operator as a string ("==", ">", "<", ">=", "<=") and the value to compare against.
        :return: Filtered list of objects matching all criteria
        """

        def matches_criteria(obj):
            for attr, (op, value) in criteria.items():
                attr_value = getattr(obj, attr, None)
                if not compare(attr_value, op, value):
                    return False
            return True

        def compare(attr_value, op, value):
            if op == "==":
                return attr_value == value
            elif op == ">":
                return attr_value > value
            elif op == "<":
                return attr_value < value
            elif op == ">=":
                return attr_value >= value
            elif op == "<=":
                return attr_value <= value
            else:
                raise ValueError(f"Unsupported operator: {op}")

        return [obj for obj in objects if matches_criteria(obj)]

    def filter_by_type_and_criteria(
            self,
            type_to_include: Type,
            input_list: List[Any],
            criteria: Dict[str, Tuple[str, Any]],
    ) -> List[Any]:
        """Filters a list of objects based on specified criteria. Objects must be of type 'type_to_include'

        :param type_to_include: All the returned objects must be of this type.
        :param input_list: List of objects to be filtered.
        :param criteria: A dictionary where keys are attribute names and values are tuples containing
                         the comparison operator as a string ("==", ">", "<", ">=", "<=") and the value to compare against.
        :return: A list of objects of type 'type_to_include' that match all specified attribute values.
        """
        annotations = self.filter_by_type(type_to_include, input_list)
        return self._filter_objects(annotations, criteria)
