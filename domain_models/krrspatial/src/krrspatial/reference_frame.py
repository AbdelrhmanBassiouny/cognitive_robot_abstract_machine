from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from uuid import UUID

from typing_extensions import Any, Dict

from krrood.adapters.json_serializer import from_json
from krrood.adapters.object_reference import ObjectReference
from krrood.patterns.interface import Interface
from krrspatial.coordinate_system import CoordinateSystem
from krrspatial.exceptions import MissingReferenceFrameResolver
from krrspatial.space import EuclideanSpace

# %% frames that positions and directions are expressed in


class ReferenceFrame(CoordinateSystem[EuclideanSpace], Interface):
    """
    A frame that positions and directions are expressed in, in metres, such as a body of
    a robot.
    """


class ReferenceFrameResolver(Interface):
    """
    Finds the reference frames serialized spatial types refer to, while one JSON
    document is deserialized.

    It travels through nested ``from_json`` calls in their keyword arguments.
    """

    @abstractmethod
    def get(self, key: UUID, name: Any = None) -> ReferenceFrame:
        """
        :param key: The identifier the document refers to the frame with.
        :param name: The name the reference to the frame went by, which says which frame
            was meant when it cannot be found.
        :return: The frame with that identifier.
        """


# %% referring to a frame in a serialized spatial type


@dataclass
class ReferenceFrameReference(ObjectReference):
    """
    How a serialized spatial type points at a :class:`ReferenceFrame`.
    """

    def resolve(self, data: Dict[str, Any], **kwargs) -> ReferenceFrame:
        """
        :raises MissingReferenceFrameResolver: If the kwargs carry no
            :class:`ReferenceFrameResolver`.
        """
        resolvers = [
            value
            for value in kwargs.values()
            if isinstance(value, ReferenceFrameResolver)
        ]
        if not resolvers:
            raise MissingReferenceFrameResolver(frame_id_key=self.id_key)
        return resolvers[0].get(
            from_json(data[self.id_key]), name=from_json(data.get(self.name_key))
        )
