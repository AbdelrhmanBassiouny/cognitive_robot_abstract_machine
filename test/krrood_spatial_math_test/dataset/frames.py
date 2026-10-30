from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from typing_extensions import Any

from krrood.adapters.deserialized_object_tracker import DeserializedObjectTracker
from krrood.patterns.identifier_and_name import HasID, HasName
from krrood_spatial_math.cartesian_frame_3d import (
    CartesianFrame3D,
    CartesianFrame3DResolver,
    ValueT,
)
from krrood_spatial_math.exceptions import ReferenceFrameMismatchError
from krrood_spatial_math.space import EuclideanSpace3D

# %% frames told apart by name


@dataclass(eq=False)
class NamedFrame(CartesianFrame3D):
    """
    A Cartesian frame that only has a name, so it knows no change to any other frame and
    expresses only values already given in it.
    """

    name: str
    """
    What the frame is called.
    """

    space: EuclideanSpace3D | None = None
    """
    The space the frame charts.
    """

    id: UUID = field(default_factory=uuid4)
    """
    The identifier serialized coordinate representations refer to the frame with.
    """

    def express(self, value: ValueT) -> ValueT:
        if value.reference_frame is not self:
            raise ReferenceFrameMismatchError(
                expected_frame=self, actual_frame=value.reference_frame
            )
        return value


# %% finding frames while deserializing


@dataclass
class KnownFrames(
    DeserializedObjectTracker[UUID, NamedFrame], CartesianFrame3DResolver
):
    """
    The frames the reader of a document already has.
    """

    def get(self, key: UUID, name: Any = None) -> NamedFrame:
        return super().get(key)


# %% frames that extend objects named before they are identified


@dataclass(eq=False)
class NamedThing(HasName):
    """
    An object that is named whether or not it has an identifier.
    """

    name: str
    """
    What the object is called.
    """


@dataclass(eq=False)
class IdentifiedNamedThing(NamedThing, HasID):
    """
    A named object that also has an identifier, given after its name.
    """

    id: UUID = field(default_factory=uuid4)
    """
    The identifier given after the name.
    """


@dataclass(eq=False)
class ThingFrame(IdentifiedNamedThing, CartesianFrame3D):
    """
    A Cartesian frame that extends an object named before it is identified.
    """

    space: EuclideanSpace3D | None = None
    """
    The space the frame charts.
    """
