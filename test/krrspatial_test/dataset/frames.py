from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from typing_extensions import Any

from krrood.adapters.deserialized_object_tracker import DeserializedObjectTracker
from krrspatial.reference_frame import ReferenceFrame, ReferenceFrameResolver

# %% frames told apart by name


@dataclass(eq=False)
class NamedFrame(ReferenceFrame):
    """
    A reference frame that only has a name.
    """

    name: str
    """
    What the frame is called.
    """

    id: UUID = field(default_factory=uuid4)
    """
    The identifier serialized spatial types refer to the frame with.
    """


# %% finding frames while deserializing


@dataclass
class KnownFrames(DeserializedObjectTracker[UUID, NamedFrame], ReferenceFrameResolver):
    """
    The frames the reader of a document already has.
    """

    def get(self, key: UUID, name: Any = None) -> NamedFrame:
        return super().get(key)
