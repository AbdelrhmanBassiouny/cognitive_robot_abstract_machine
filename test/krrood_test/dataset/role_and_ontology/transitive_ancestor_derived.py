from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from krrood.entity_query_language.factories import variable_from
from krrood.patterns.role.role import Role

from test.krrood_test.dataset.role_and_ontology.transitive_ancestor_base import (
    AncestorBase,
)
from krrood.patterns.role import HasRoles
from test.krrood_test.dataset.role_and_ontology.role_mixins.transitive_ancestor_derived_role_mixins import (
    RoleForDerivedClass,
)


@dataclass
class DerivedClass(AncestorBase, HasRoles):
    def derived_only_method(self) -> str: ...


TDerivedClass = TypeVar("TDerivedClass", bound=DerivedClass)


@dataclass
class DerivedRole(Role[TDerivedClass], RoleForDerivedClass):
    taker: TDerivedClass = field(kw_only=True)

    @classmethod
    def role_taker_attribute(cls) -> TDerivedClass:
        return variable_from(cls).taker
