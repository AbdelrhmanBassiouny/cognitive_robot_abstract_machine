from dataclasses import dataclass, field
from typing import TypeVar
from krrood.patterns.role.role import Role
from krrood.entity_query_language.factories import variable_from
from .base_taker import BaseTaker


@dataclass
class Taker(BaseTaker):
    """
    A role taker that inherits from BaseTaker.
    BaseTaker has a method that uses ExternalType, but ExternalType is not imported here.
    """

    pass


TTaker = TypeVar("TTaker", bound=Taker)


@dataclass
class MyRole(Role[TTaker]):
    """
    A role for Taker.
    """

    taker: TTaker = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTaker:
        return variable_from(cls).taker
