from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from typing_extensions import Any

from krrood.adapters.json_serializer import to_json
from krrood.patterns.interface import Interface

# %% objects a serialized object refers to


class IdentifiedObject(Interface):
    """
    An object that serialized objects refer to by its identifier instead of holding a
    copy of it.
    """

    id: UUID
    """
    The identifier serialized objects refer to the object with.
    """

    name: Any
    """
    What the object is called, which says which object was meant where it cannot be
    found.
    """


@dataclass
class ObjectReference(ABC):
    """
    How a serialized object points at an :class:`IdentifiedObject`: by its identifier,
    and by the name it went by, which says which object was meant where it cannot be
    found.

    The name is never looked up with, so two objects sharing one name stay apart.
    """

    subject: str
    """
    What the referring object calls the object it refers to, for example ``parent``.
    """

    @property
    def id_key(self) -> str:
        """
        Where the identifier of the object sits in the serialized object.
        """
        return f"{self.subject}_id"

    @property
    def name_key(self) -> str:
        """
        Where the name of the object sits in the serialized object.
        """
        return f"{self.subject}_name"

    def write(self, data: dict[str, Any], identified_object: IdentifiedObject) -> None:
        """
        Put the reference to an object into a serialized object.

        :param data: The json of the object that refers to it.
        :param identified_object: The object it refers to.
        """
        data[self.id_key] = to_json(identified_object.id)
        data[self.name_key] = to_json(identified_object.name)

    @abstractmethod
    def resolve(self, data: dict[str, Any], **kwargs) -> IdentifiedObject:
        """
        The object a serialized object refers to.

        :param data: The json of the object that refers to it.
        :param kwargs: The kwargs of the ``_from_json`` that is reading it.
        """
