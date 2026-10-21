from __future__ import annotations

from dataclasses import dataclass

from krrood.exceptions import DataclassException

from krrspatial.spatial_types import SpatialType

# %% combining spatial objects


@dataclass
class DifferentReferenceFrames(DataclassException):
    """
    Raised when two spatial objects are combined although they are expressed in
    different reference frames.
    """

    first: SpatialType
    """
    The object on the left of the operation.
    """

    second: SpatialType
    """
    The object on the right of the operation.
    """

    def error_message(self) -> str:
        return (
            f"{self.first} is expressed in {self.first.reference_frame}, but "
            f"{self.second} in {self.second.reference_frame}."
        )

    def suggest_correction(self) -> str:
        return "express both in the same reference frame before combining them."
