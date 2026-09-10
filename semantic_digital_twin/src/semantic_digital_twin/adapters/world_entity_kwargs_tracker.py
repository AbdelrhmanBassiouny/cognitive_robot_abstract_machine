from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from typing_extensions import Optional, TYPE_CHECKING, Self

from krrood.adapters.deserialized_object_tracker import DeserializedObjectTracker
from semantic_digital_twin.exceptions import (
    MissingWorldError,
    WorldEntityWithIDNotInKwargs,
)

if TYPE_CHECKING:
    from semantic_digital_twin.world import World
    from semantic_digital_twin.world_description.world_entity import WorldEntityWithID


@dataclass
class WorldEntityWithIDKwargsTracker(
    # A string, because world_entity imports this module and cannot be imported back.
    DeserializedObjectTracker[UUID, "WorldEntityWithID"]
):
    """
    The world entities deserialized from one JSON document, by their id.

    An entity the document does not contain is looked up in the world the tracker was
    created with through :meth:`from_world`.
    """

    _world: Optional[World] = field(init=False, default=None)
    """
    The world to look up the entities in that were not deserialized from the document.
    """

    @classmethod
    def from_world(cls, world: World) -> Self:
        """
        Create a new tracker from a world.

        :param world: A world instance that will be used as a backup to look for world
            entities.
        """
        if world is None:
            raise MissingWorldError()
        tracker = cls()
        tracker._world = world
        return tracker

    def _has_untracked(self, key: UUID) -> bool:
        if self._world is None:
            return False
        return self._world.find_world_entity_with_id(key) is not None

    def _get_untracked(self, key: UUID) -> WorldEntityWithID:
        """
        :raises MissingWorldError: If the tracker has no world to look the entity up in.
        :raises WorldEntityWithIDNotInKwargs: If the world holds no entity with the id.
        """
        if self._world is None:
            raise MissingWorldError()
        entity = self._world.find_world_entity_with_id(key)
        if entity is None:
            raise WorldEntityWithIDNotInKwargs(key=key)
        return entity
