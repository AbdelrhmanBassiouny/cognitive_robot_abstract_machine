from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional, TYPE_CHECKING

from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from krrspatial.reference_frame import ReferenceFrame
    from krrspatial.spatial_types import Vector3

# %% spatial types


@dataclass
class SpatialTypesError(DataclassException):
    """
    A spatial type was used in a way it does not support.
    """


@dataclass
class InsufficientVectorsError(SpatialTypesError):
    """
    Raised when a rotation matrix is constructed from fewer than two vectors.
    """

    x: Optional[Vector3]
    """
    The vector given for the x axis.
    """

    y: Optional[Vector3]
    """
    The vector given for the y axis.
    """

    z: Optional[Vector3]
    """
    The vector given for the z axis.
    """

    def error_message(self) -> str:
        return (
            f"from_vectors requires at least two of the vectors x, y, z to be provided; "
            f"the third is computed via the cross product."
            f"X Vector was: {self.x}"
            f"Y Vector was: {self.y}"
            f"Z Vector was: {self.z}"
        )

    def suggest_correction(self) -> str:
        return ""


@dataclass
class ReferenceFrameMismatchError(SpatialTypesError):
    """
    Raised when a value is expressed in a different frame than an operation requires.
    """

    expected_frame: ReferenceFrame
    """
    The frame the operation requires.
    """

    actual_frame: ReferenceFrame
    """
    The frame that was found instead.
    """

    context: Optional[str] = None
    """
    Description of the value whose frame was checked, e.g. the argument name.
    """

    def error_message(self) -> str:
        checked_value = self.context or "the given value"
        return (
            f"Expected {checked_value} to be expressed in frame '{self.expected_frame.name}', "
            f"but it is expressed in frame '{self.actual_frame.name}'."
        )

    def suggest_correction(self) -> str:
        return (
            "transform it into the expected frame first, e.g. via "
            "world.transform(value, target_frame), or construct it with the expected frame."
        )


# %% serialized reference frames


@dataclass
class MissingReferenceFrameResolver(SpatialTypesError):
    """
    Raised when a serialized spatial type refers to a reference frame, but nothing was
    given to deserialize it with that finds the frame.
    """

    frame_id_key: str
    """
    Where the identifier of the frame sits in the serialized spatial type.
    """

    def error_message(self) -> str:
        return (
            f"The serialized spatial type refers to a frame by '{self.frame_id_key}', "
            f"but the keyword arguments of from_json carry no ReferenceFrameResolver."
        )

    def suggest_correction(self) -> str:
        return (
            "pass the keyword arguments of a ReferenceFrameResolver that knows the frame, "
            "e.g. **resolver.create_kwargs(), to from_json."
        )
