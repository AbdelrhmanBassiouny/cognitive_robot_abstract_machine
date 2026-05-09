from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import List, TYPE_CHECKING

if TYPE_CHECKING:
    from test.krrood_test.dataset.role_and_ontology.university_ontology_like_classes_without_descriptors import (
        HasName,
        RecognizedGroup,
        TPersonInRoleAndOntology,
        TSubclassOfARoleTaker,
        TCEOAsFirstRole,
        TRepresentativeAsSecondRole,
    )


@dataclass(eq=False)
class DelegatorForHasName(ABC):

    @property
    @abstractmethod
    def delegatee(self) -> HasName: ...

    @property
    def name(self) -> str:
        return self.delegatee.name

    @name.setter
    def name(self, value: str):
        self.delegatee.name = value

    @property
    def default_name(self) -> str:
        return self.delegatee.default_name

    @default_name.setter
    def default_name(self, value: str):
        self.delegatee.default_name = value

    def __eq__(self, other):
        return self.delegatee.__eq__(other)

    def __hash__(self):
        return self.delegatee.__hash__()


@dataclass(eq=False)
class DelegatorForPersonInRoleAndOntology(DelegatorForHasName, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> TPersonInRoleAndOntology: ...

    @property
    def works_for(self) -> RecognizedGroup:
        return self.delegatee.works_for

    @works_for.setter
    def works_for(self, value: RecognizedGroup):
        self.delegatee.works_for = value

    @property
    def member_of(self) -> List[RecognizedGroup]:
        return self.delegatee.member_of

    @member_of.setter
    def member_of(self, value: List[RecognizedGroup]):
        self.delegatee.member_of = value

    def method_in_person(self) -> RecognizedGroup:
        return self.delegatee.method_in_person()

    def method_2_in_person(self) -> List[RecognizedGroup]:
        return self.delegatee.method_2_in_person()


@dataclass(eq=False)
class DelegatorForSubclassOfARoleTaker(DelegatorForPersonInRoleAndOntology, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> TSubclassOfARoleTaker: ...

    @property
    def introduced_attribute(self) -> str:
        return self.delegatee.introduced_attribute

    @introduced_attribute.setter
    def introduced_attribute(self, value: str):
        self.delegatee.introduced_attribute = value


@dataclass(eq=False)
class DelegatorForCEOAsFirstRole(DelegatorForPersonInRoleAndOntology, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> TCEOAsFirstRole: ...

    @property
    def person(self) -> TPersonInRoleAndOntology:
        return self.delegatee.person

    @person.setter
    def person(self, value: TPersonInRoleAndOntology):
        self.delegatee.person = value

    @property
    def head_of(self) -> RecognizedGroup:
        return self.delegatee.head_of

    @head_of.setter
    def head_of(self, value: RecognizedGroup):
        self.delegatee.head_of = value


@dataclass(eq=False)
class DelegatorForRepresentativeAsSecondRole(DelegatorForCEOAsFirstRole, ABC):

    @property
    @abstractmethod
    def delegatee(self) -> TRepresentativeAsSecondRole: ...

    @property
    def ceo(self) -> TCEOAsFirstRole:
        return self.delegatee.ceo

    @ceo.setter
    def ceo(self, value: TCEOAsFirstRole):
        self.delegatee.ceo = value

    @property
    def representative_of(self) -> RecognizedGroup:
        return self.delegatee.representative_of

    @representative_of.setter
    def representative_of(self, value: RecognizedGroup):
        self.delegatee.representative_of = value
