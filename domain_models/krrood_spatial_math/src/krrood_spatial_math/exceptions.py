from __future__ import annotations

from dataclasses import dataclass

from krrood.exceptions import DataclassException

# %% spatial types


@dataclass
class SpatialTypesError(DataclassException):
    """
    A spatial type was used in a way it does not support.
    """


# %% serialized Cartesian frames


@dataclass
class MissingCartesianFrame3DResolver(SpatialTypesError):
    """
    Raised when a serialized coordinate representation refers to a three-dimensional
    Cartesian frame, but nothing was given to deserialize it with that finds the frame.
    """

    frame_id_key: str
    """
    Where the identifier of the frame sits in the serialized coordinate representation.
    """

    def error_message(self) -> str:
        return (
            f"The serialized coordinate representation refers to a frame by "
            f"'{self.frame_id_key}', but the keyword arguments of from_json carry no "
            f"CartesianFrame3DResolver."
        )

    def suggest_correction(self) -> str:
        return (
            "pass the keyword arguments of a CartesianFrame3DResolver that knows the "
            "frame, e.g. **resolver.create_kwargs(), to from_json."
        )
