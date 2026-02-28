from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Set, List

from krrood.entity_query_language.predicate import Symbol

@dataclass(eq=False)
class Company(Symbol):
    name: str
    members: Set[Person] = None
    sub_organization_of: List[Company] = None

@dataclass(eq=False)
class Person(Symbol):
    name: str = field(kw_only=True, default=None)
    works_for: Company = field(kw_only=True, default=None)
    member_of: List[Company] = field(kw_only=True, default=None)
    head_of: Company = field(kw_only=True, default=None)
    representative_of: Company = field(kw_only=True, default=None)

@dataclass(eq=False)
class CEO(Person):
    person: Person

@dataclass(eq=False)
class Representative(CEO):
    ceo: CEO
