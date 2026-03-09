from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Set, List

from krrood.entity_query_language.predicate import Symbol

@dataclass(eq=False)
class RecognizedGroup(Symbol):
    name: str

    members: Set[Person] = field(default_factory=set)
    sub_organization_of: List[RecognizedGroup] = field(default_factory=list)

    def __hash__(self):
        return hash(self.name)

@dataclass(eq=False)
class Company(RecognizedGroup): ...

@dataclass(eq=False)
class Country(RecognizedGroup): ...

@dataclass(unsafe_hash=True)
class Course(Symbol):
    name: str

@dataclass(eq=False)
class Person(Symbol):
    name: str = field(kw_only=True, default=None)
    works_for: RecognizedGroup = field(kw_only=True, default=None)
    member_of: List[RecognizedGroup] = field(kw_only=True, default=None)
    head_of: RecognizedGroup = field(kw_only=True, default=None)
    representative_of: RecognizedGroup = field(kw_only=True, default=None)
    delegate_of: RecognizedGroup = field(kw_only=True, default=None)
    teacher_of: List[Course] = field(kw_only=True, default=None)

@dataclass(eq=False)
class CEOAsFirstRole(Person):
    person: Person
    # Original Owner of the head_of field
    head_of: RecognizedGroup = field(kw_only=True, default=None)

@dataclass(eq=False)
class ProfessorAsFirstRole(Person):
    person: Person
    # Original Owner of the teacher_of field
    teacher_of: List[Course] = field(default_factory=list, kw_only=True)

@dataclass(eq=False)
class RepresentativeAsSecondRole(CEOAsFirstRole):
    ceo: CEOAsFirstRole
    person: Person = field(init=False)
    # Original Owner of the representative_of field
    representative_of: RecognizedGroup = field(kw_only=True, default=None)

@dataclass(eq=False)
class DelegateAsThirdRole(RepresentativeAsSecondRole):
    representative: RepresentativeAsSecondRole
    ceo: CEOAsFirstRole = field(init=False)
    # Original Owner of the delegate_of field
    delegate_of: RecognizedGroup = field(kw_only=True, default=None)
