from __future__ import annotations

from dataclasses import dataclass

from krrood.exceptions import DataclassException

# %% spatial types


@dataclass
class SpatialTypesError(DataclassException):
    """
    A spatial type was used in a way it does not support.
    """


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
