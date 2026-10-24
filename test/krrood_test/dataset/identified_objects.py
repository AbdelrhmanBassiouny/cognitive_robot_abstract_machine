from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from typing_extensions import Any, Dict

from krrood.adapters.deserialized_object_tracker import DeserializedObjectTracker
from krrood.adapters.json_serializer import from_json
from krrood.adapters.object_reference import IdentifiedObject, ObjectReference

# %% objects referred to by identifier


@dataclass
class Landmark(IdentifiedObject):
    """
    An object that documents refer to instead of containing it.
    """

    name: str
    """
    What the landmark is called.
    """

    id: UUID = field(default_factory=uuid4)
    """
    The identifier documents refer to the landmark with.
    """


@dataclass
class LandmarkTracker(DeserializedObjectTracker[UUID, Landmark]):
    """
    The landmarks the reader of a document already has.
    """


@dataclass
class LandmarkReference(ObjectReference):
    """
    How a document points at a :class:`Landmark`.
    """

    def resolve(self, data: Dict[str, Any], **kwargs) -> Landmark:
        return LandmarkTracker.from_kwargs(kwargs).get(from_json(data[self.id_key]))
