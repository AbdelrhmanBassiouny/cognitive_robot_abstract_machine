from dataclasses import dataclass, field
from typing import TypeVar
from krrood.patterns.role.role import Role
from krrood.entity_query_language.factories import variable_from
from test.krrood_test.dataset.role_and_ontology.base_taker import BaseTaker
from krrood.patterns.role import HasRoles
from test.krrood_test.dataset.role_and_ontology.role_mixins.reproduction_module_role_mixins import (
    RoleForTaker,
)


@dataclass
class Taker(BaseTaker, HasRoles):
    """
    A role taker that inherits from BaseTaker.
    BaseTaker has a method that uses ExternalType, but ExternalType is not imported here.
    """

    pass


TTaker = TypeVar("TTaker", bound=Taker)


@dataclass
class MyRole(Role[TTaker], RoleForTaker):
    """
    A role for Taker.
    """

    taker: TTaker = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TTaker:
        return variable_from(cls).taker
