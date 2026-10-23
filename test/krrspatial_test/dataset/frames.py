from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from typing_extensions import Any

from krrood.adapters.deserialized_object_tracker import DeserializedObjectTracker
from krrspatial.exceptions import ReferenceFrameMismatchError
from krrspatial.reference_frame import (
    CoordinateRepresentationT,
    ReferenceFrame,
    ReferenceFrameResolver,
)
from krrspatial.space import EuclideanSpace

# %% frames told apart by name


@dataclass(eq=False)
class NamedFrame(ReferenceFrame):
    """
    A reference frame that only has a name, so it knows no change to any other frame and
    expresses only values already given in it.
    """

    name: str
    """
    What the frame is called.
    """

    space: EuclideanSpace | None = None
    """
    The space the frame charts.
    """

    id: UUID = field(default_factory=uuid4)
    """
    The identifier serialized spatial types refer to the frame with.
    """

    def express(self, value: CoordinateRepresentationT) -> CoordinateRepresentationT:
        if value.coordinate_system is not self:
            raise ReferenceFrameMismatchError(
                expected_frame=self, actual_frame=value.coordinate_system
            )
        return value


# %% finding frames while deserializing


@dataclass
class KnownFrames(DeserializedObjectTracker[UUID, NamedFrame], ReferenceFrameResolver):
    """
    The frames the reader of a document already has.
    """

    def get(self, key: UUID, name: Any = None) -> NamedFrame:
        return super().get(key)
