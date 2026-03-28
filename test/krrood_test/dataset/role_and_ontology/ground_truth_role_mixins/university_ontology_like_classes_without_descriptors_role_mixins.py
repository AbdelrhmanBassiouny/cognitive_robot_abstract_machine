from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Set, List, TYPE_CHECKING

from krrood.entity_query_language.predicate import Symbol
from krrood.patterns.role.role import Role

if TYPE_CHECKING:
    from ..university_ontology_like_classes_without_descriptors import (
        HasName,
        RecognizedGroup,
        Course,
        TPerson,
        PersonInRoleAndOntology,
    )


@dataclass(eq=False)
class PersonInRoleAndOntologyRoleAttributes:
    head_of: RecognizedGroup = field(init=False)
    delegate_of: RecognizedGroup = field(init=False)
    members: Set[PersonInRoleAndOntology] = field(init=False)
    sub_organization_of: List[RecognizedGroup] = field(init=False)
    teacher_of: List[Course] = field(init=False)
    representative_of: RecognizedGroup = field(init=False)


@dataclass(eq=False)
class PersonInRoleAndOntologyMixin(
    PersonInRoleAndOntologyRoleAttributes, HasName, Symbol
):
    name: str = field(init=False)
    default_name: str = field(init=False)
    works_for: RecognizedGroup = field(init=False)
    member_of: List[RecognizedGroup] = field(init=False)


@dataclass(eq=False)
class SubclassOfARoleTakerMixin(PersonInRoleAndOntologyMixin):
    introduced_attribute: str = field(init=False)


@dataclass(eq=False)
class CEOAsFirstRoleMixin(PersonInRoleAndOntologyMixin, Role[TPerson], Symbol):
    person: TPerson = field(init=False)
    head_of: RecognizedGroup = field(init=False)

    @classmethod
    def role_taker_attribute(cls) -> TPerson: ...
