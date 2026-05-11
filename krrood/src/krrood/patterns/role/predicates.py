from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Type

from typing_extensions import Tuple

from krrood.entity_query_language import symbolic
from krrood.entity_query_language.predicate import Predicate, symbolic_function
from krrood.entity_query_language.utils import T
from krrood.patterns.role.role import Role


@symbolic_function
def has_role(entity: T, roles: Type[Role[T]] | Tuple[Type[Role[T]], ...]) -> bool:
    """
    :param entity: The entity to check.
    :param roles: The role type to check.
    :return: True if the given entity is a role_taker for any of the given role types, False otherwise.
    """
    return Role.has_role(entity, roles)


@symbolic_function
def isinstance_or_role(entity: T, types: Type | Tuple[Type, ...]) -> bool:
    """
    :param entity: The entity to check.
    :param types: The types to check for.
    :return: True if the given entity is an instance of a type in the given types
    or if it is a Role for a type in the given types, False otherwise.
    """
    return isinstance(entity, types) or (
        isinstance(entity, Role) and isinstance_or_role(entity.role_taker, types)
    )
