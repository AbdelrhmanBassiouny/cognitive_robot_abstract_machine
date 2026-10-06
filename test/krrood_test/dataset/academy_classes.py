"""
A small university domain whose relations are collection-valued, as the object properties
of an ontology compiled by Ontomatic are. It is used to test the translation of EQL queries
over collection-valued attributes to SQL.

The class names are prefixed with ``Academy`` because the class diagram resolves string
annotations by class name, so a same-named class of another test module could otherwise take
the place of one of these.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Optional, Set

from krrood.patterns.role import Role
from krrood.symbol_graph.symbol_graph import Symbol


@dataclass(eq=False)
class AcademyDiscipline(Symbol):
    name: str


@dataclass(eq=False)
class AcademyCourse(Symbol):
    name: str


@dataclass(eq=False)
class AcademyOrganization(Symbol):
    name: str
    is_part_of: Set[AcademyOrganization] = field(default_factory=set)
    has_dean: Set[AcademyMember] = field(default_factory=set)


@dataclass(eq=False)
class AcademyCollege(AcademyOrganization):
    """
    Only colleges have disciplines, so a query that reads the disciplines of an
    organization ranges over the colleges among the organizations.
    """

    has_discipline: Set[AcademyDiscipline] = field(default_factory=set)


@dataclass(eq=False)
class AcademyMember(Symbol):
    name: str
    age: Optional[int] = None
    nickname: Optional[str] = None
    is_member_of: Set[AcademyOrganization] = field(default_factory=set)
    is_head_of: Set[AcademyOrganization] = field(default_factory=set)
    teaches_course: Set[AcademyCourse] = field(default_factory=set)


@dataclass(eq=False)
class AcademyStudent(Role[AcademyMember]):
    takes_course: Set[AcademyCourse] = field(default_factory=set)
    is_student_of: Set[AcademyOrganization] = field(default_factory=set)
