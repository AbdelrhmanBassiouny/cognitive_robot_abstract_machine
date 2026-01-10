from __future__ import annotations

from dataclasses import dataclass, field, Field, fields

from typing_extensions import Set, List, Type

from krrood.entity_query_language.predicate import Symbol
from krrood.ontomatic.property_descriptor.mixins import (
    HasInverseProperty,
    TransitiveProperty,
)
from krrood.ontomatic.property_descriptor.property_descriptor import (
    PropertyDescriptor,
)
from krrood.class_diagrams.utils import Role


@dataclass(eq=False)
class Company(Symbol):
    name: str
    members: Set[Person] = field(default_factory=set)
    sub_organization_of: List[Company] = field(default_factory=list)

    def __hash__(self):
        return hash(self.name)


@dataclass(eq=False)
class CompanyWithEmployees(Role[Company], Symbol):
    company: Company
    employees: List[Person] = field(default_factory=list)

    @classmethod
    def role_taker_field(cls) -> Field:
        return [f for f in fields(cls) if f.name == "company"][0]


@dataclass(eq=False)
class Person(Symbol):
    name: str
    works_for: Company = None
    member_of: List[Company] = field(default_factory=list)

    def __hash__(self):
        return hash(self.name)


@dataclass(eq=False)
class CEO(Role[Person], Symbol):
    person: Person
    head_of: Company = None

    @classmethod
    def role_taker_field(cls) -> Field:
        return [f for f in fields(cls) if f.name == "person"][0]


@dataclass(eq=False)
class PeopleWithHoppy(Role[Person], Symbol):
    """
    Relevant for testing role graph
    """

    person: Person
    likes: List[Symbol] = field(default_factory=list)

    @classmethod
    def role_taker_field(cls) -> Field:
        return [f for f in fields(cls) if f.name == "person"][0]


@dataclass(eq=False)
class Interest(Symbol):
    name: str


@dataclass(eq=False)
class Sports(Interest):
    pass


@dataclass(eq=False)
class BasketBall(Sports):
    pass


@dataclass(eq=False)
class Gaming(Interest):
    pass


@dataclass(eq=False)
class VideoGames(Gaming):
    pass


@dataclass(eq=False)
class SportsLover(PeopleWithHoppy):
    loves: List[Sports] = field(default_factory=list)


@dataclass(eq=False)
class Gamer(PeopleWithHoppy):
    likes: List[Gaming] = field(default_factory=list)


@dataclass(eq=False)
class BasketBallLover(SportsLover):
    loves: List[BasketBall] = field(default_factory=list)


@dataclass(eq=False)
class Representative(Role[CEO], Symbol):
    ceo: CEO
    representative_of: Company = None

    @classmethod
    def role_taker_field(cls) -> Field:
        return [f for f in fields(cls) if f.name == "ceo"][0]


@dataclass(eq=False)
class ExperiencedCEO(Role[CEO], Symbol):
    """
    Relevant for testing role graph
    """

    ceo: CEO
    experiences: List[Company] = field(default_factory=list)

    @classmethod
    def role_taker_field(cls) -> Field:
        return [f for f in fields(cls) if f.name == "ceo"][0]


@dataclass
class Member(PropertyDescriptor, HasInverseProperty):

    @classmethod
    def get_inverse(cls) -> Type[MemberOf]:
        return MemberOf


@dataclass
class HasEmployees(Member):
    """
    An inverse of `MemberOf` that lies in a Role context (CompanyWithEmployees), relevant for testing role graph.
    """

    ...


@dataclass
class MemberOf(PropertyDescriptor, HasInverseProperty):
    @classmethod
    def get_inverse(cls) -> Type[Member]:
        return Member


@dataclass
class WorksFor(MemberOf):
    pass


@dataclass
class HeadOf(WorksFor):
    pass


@dataclass
class RepresentativeOf(WorksFor):
    pass


@dataclass
class SubOrganizationOf(PropertyDescriptor, TransitiveProperty): ...


@dataclass
class HasExperiences(PropertyDescriptor): ...


@dataclass
class Likes(PropertyDescriptor): ...


@dataclass
class Loves(Likes): ...


# Person fields' descriptors
Person.works_for = WorksFor(Person, "works_for")
Person.member_of = MemberOf(Person, "member_of")

# CEO fields' descriptors
CEO.head_of = HeadOf(CEO, "head_of")

# Representative fields' descriptors
Representative.representative_of = RepresentativeOf(Representative, "representative_of")

# Company fields' descriptors
Company.members = Member(Company, "members")
Company.sub_organization_of = SubOrganizationOf(Company, "sub_organization_of")
CompanyWithEmployees.employees = HasEmployees(CompanyWithEmployees, "employees")

# ExperiencedCEO fields' descriptors
ExperiencedCEO.experiences = HasExperiences(ExperiencedCEO, "experiences")

# PeopleWithHoppy fields' descriptors
PeopleWithHoppy.likes = Likes(PeopleWithHoppy, "likes")
SportsLover.loves = Loves(SportsLover, "loves")
Gamer.likes = Likes(Gamer, "likes")
BasketBallLover.loves = Loves(BasketBallLover, "loves")
