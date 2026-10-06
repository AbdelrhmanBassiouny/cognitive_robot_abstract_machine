"""
Tests of the translation of EQL queries over collection-valued attributes to SQL.

Every relation of :mod:`academy_classes` is a set, as the object properties of an ontology
compiled by Ontomatic are. The expected answers are written out, and where the in-memory
evaluation of EQL is correct for a query, the SQL answers are also compared with it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from typing_extensions import Any, Iterable, List, Set, Tuple

from krrood.entity_query_language.factories import (
    an,
    and_,
    contains,
    entity,
    exists,
    flat_variable,
    inference,
    not_,
    or_,
    set_of,
    variable,
)
from krrood.ormatic.data_access_objects.helper import to_dao
from krrood.ormatic.data_access_objects.to_dao import ToDataAccessObjectState
from krrood.ormatic.eql_interface import (
    UnsupportedTranslationError,
    eql_to_sql,
)
from ..dataset.academy_classes import (
    AcademyCollege,
    AcademyCourse,
    AcademyDiscipline,
    AcademyMember,
    AcademyOrganization,
    AcademyStudent,
)

# %% Fixtures


@dataclass
class Academy:
    """
    A university with two colleges, their departments, a dean, a lecturer and three
    students; see :func:`build_academy`.
    """

    organizations: List[AcademyOrganization]
    members: List[AcademyMember]
    students: List[AcademyStudent]
    logic: AcademyCourse


def build_academy() -> Academy:
    """
    :return: An academy in which the Dean heads the EngineeringCollege and teaches Logic,
        the Lecturer (age 0) teaches AI and Painting, Alice (22) and Carol (31) study at
        the RoboticsDepartment of the EngineeringCollege, and Bob (no age, no nickname)
        studies at the PaintingDepartment of the ArtsCollege.
    """
    engineering = AcademyDiscipline("Engineering")
    arts = AcademyDiscipline("Arts")
    university = AcademyOrganization("University")
    engineering_college = AcademyCollege(
        "EngineeringCollege", is_part_of={university}, has_discipline={engineering}
    )
    arts_college = AcademyCollege(
        "ArtsCollege", is_part_of={university}, has_discipline={arts}
    )
    robotics = AcademyOrganization(
        "RoboticsDepartment", is_part_of={engineering_college}
    )
    painting_department = AcademyOrganization(
        "PaintingDepartment", is_part_of={arts_college}
    )
    logic, ai, painting = (
        AcademyCourse("Logic"),
        AcademyCourse("AI"),
        AcademyCourse("Painting"),
    )
    dean = AcademyMember(
        "Dean",
        age=60,
        teaches_course={logic},
        is_head_of={engineering_college},
        is_member_of={engineering_college},
    )
    lecturer = AcademyMember(
        "Lecturer",
        age=0,
        nickname="lec",
        teaches_course={ai, painting},
        is_member_of={arts_college, engineering_college},
    )
    engineering_college.has_dean = {dean}
    alice = AcademyMember("Alice", age=22, nickname="ali", is_member_of={robotics})
    bob = AcademyMember("Bob")
    carol = AcademyMember("Carol", age=31)
    students = [
        AcademyStudent(
            role_taker=alice, takes_course={logic, ai}, is_student_of={robotics}
        ),
        AcademyStudent(
            role_taker=bob, takes_course={painting}, is_student_of={painting_department}
        ),
        AcademyStudent(role_taker=carol, takes_course={ai}, is_student_of={robotics}),
    ]
    organizations = [
        university,
        engineering_college,
        arts_college,
        robotics,
        painting_department,
    ]
    return Academy(organizations, [dean, lecturer, alice, bob, carol], students, logic)


@pytest.fixture
def academy(session, database) -> Academy:
    """
    :return: The academy of :func:`build_academy`, also stored in the database.
    """
    built = build_academy()
    state = ToDataAccessObjectState()
    session.add_all(
        to_dao(entity_, state)
        for entity_ in built.organizations + built.members + built.students
    )
    session.commit()
    return built


def name_of(value: Any) -> str:
    """
    :param value: A domain object or a data access object of the academy.
    :return: Its name, read from the role taker for a student.
    """
    return value.role_taker.name if hasattr(value, "role_taker") else value.name


def names(values: Iterable[Any]) -> List[str]:
    """
    :return: The sorted names of the values.
    """
    return sorted(name_of(value) for value in values)


def pairs(rows: Iterable[Any], first: Any, second: Any) -> Set[Tuple[str, str]]:
    """
    :return: The pairs of names of the values bound to ``first`` and ``second``.
    """
    return {(name_of(row[first]), name_of(row[second])) for row in rows}


# %% Selecting the elements of collections


def test_pairs_of_an_owner_and_the_elements_of_its_collection(session, academy):
    """
    ``set_of(m, flat_variable(m.is_member_of))`` lists every member with every
    organization it is a member of, like the triple pattern ``?m isMemberOf ?o``.
    """
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    query = an(set_of(m, o))
    expected = {
        ("Alice", "RoboticsDepartment"),
        ("Dean", "EngineeringCollege"),
        ("Lecturer", "ArtsCollege"),
        ("Lecturer", "EngineeringCollege"),
    }
    assert pairs(query.evaluate(), m, o) == expected
    assert pairs(eql_to_sql(query, session).evaluate(), m, o) == expected


def test_elements_of_nested_collections_with_membership(session, academy):
    """
    Students who take a course taught by the dean of an organization (OWL2Bench Q22).
    """
    s = variable(AcademyStudent, domain=academy.students)
    o = variable(AcademyOrganization, domain=academy.organizations)
    dean = flat_variable(o.has_dean)
    c = flat_variable(dean.teaches_course)
    query = an(set_of(s, c).where(contains(s.takes_course, c)))
    expected = {("Alice", "Logic")}
    assert pairs(query.evaluate(), s, c) == expected
    assert pairs(eql_to_sql(query, session).evaluate(), s, c) == expected


def test_entity_of_an_element(session, academy):
    """
    ``entity(flat_variable(o.is_part_of))`` returns the organizations that something is
    part of, once per owner.
    """
    o = variable(AcademyOrganization, domain=academy.organizations)
    whole = flat_variable(o.is_part_of)
    query = an(entity(whole))
    expected = ["ArtsCollege", "EngineeringCollege", "University", "University"]
    assert names(query.evaluate()) == expected
    assert names(eql_to_sql(query, session).evaluate()) == expected


def test_attribute_of_an_element(session, academy):
    """
    The attribute of an element is read from the element, not from its owner
    (OWL2Bench Q9 shape). Only colleges have disciplines, so the query ranges over them.
    """
    o = variable(AcademyOrganization, domain=academy.organizations)
    discipline = flat_variable(o.has_discipline)
    query = an(entity(o).where(discipline.name == "Engineering"))
    assert names(query.evaluate()) == ["EngineeringCollege"]
    assert names(eql_to_sql(query, session).evaluate()) == ["EngineeringCollege"]


# %% Quantifying over the elements of collections


def test_exists_over_nested_collections_is_correlated(session, academy):
    """
    Students of an organization that is part of an engineering organization (OWL2Bench
    Q21 shape): the existential quantifier ranges over the elements reached from the
    outer binding of ``so``, and over the colleges among them, which have disciplines.
    """
    s = variable(AcademyStudent, domain=academy.students)
    so = flat_variable(s.is_student_of)
    whole = flat_variable(so.is_part_of)
    discipline = flat_variable(whole.has_discipline)
    query = an(
        set_of(s, so).where(exists(discipline, discipline.name == "Engineering"))
    )
    expected = {("Alice", "RoboticsDepartment"), ("Carol", "RoboticsDepartment")}
    assert pairs(query.evaluate(), s, so) == expected
    assert pairs(eql_to_sql(query, session).evaluate(), s, so) == expected


def test_membership_of_a_variable_in_a_collection(session, academy):
    """
    ``contains(s.takes_course, c)`` holds when ``c`` is one of the courses of ``s``.
    """
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse, domain=[academy.logic])
    query = an(entity(s).where(contains(s.takes_course, c), c.name == "Logic"))
    assert names(query.evaluate()) == ["Alice"]
    assert names(eql_to_sql(query, session).evaluate()) == ["Alice"]


def test_collection_as_a_condition_means_non_empty(session, academy):
    """
    A collection used as a condition holds when it has an element (OWL2Bench Q15 shape).
    """
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(m).where(m.is_head_of))
    assert names(query.evaluate()) == ["Dean"]
    assert names(eql_to_sql(query, session).evaluate()) == ["Dean"]


def test_negated_collection_condition_means_empty(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(m).where(not_(m.is_head_of)))
    expected = ["Alice", "Bob", "Carol", "Lecturer"]
    assert names(query.evaluate()) == expected
    assert names(eql_to_sql(query, session).evaluate()) == expected


# %% Values that are missing or false


def test_value_as_a_condition_uses_its_truth_value(session, academy):
    """
    A value used as a condition holds when Python considers it true, so a missing age and
    an age of 0 do not hold.
    """
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(m).where(m.age))
    assert names(query.evaluate()) == ["Alice", "Carol", "Dean"]
    assert names(eql_to_sql(query, session).evaluate()) == ["Alice", "Carol", "Dean"]


def test_not_equal_holds_for_a_missing_value(session, academy):
    """
    As in Python, a missing nickname is different from ``"lec"``.
    """
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(m).where(m.nickname != "lec"))
    expected = ["Alice", "Bob", "Carol", "Dean"]
    assert names(query.evaluate()) == expected
    assert names(eql_to_sql(query, session).evaluate()) == expected


def test_negation_holds_when_a_comparison_with_a_missing_value_is_not_true(
    session, academy
):
    """
    Negation as failure: ``not_(m.age > 30)`` holds when ``m.age > 30`` is not true,
    including when the age is missing.
    """
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(m).where(not_(m.age > 30)))
    expected = ["Alice", "Bob", "Lecturer"]
    assert names(eql_to_sql(query, session).evaluate()) == expected


# %% Roles


def test_attribute_of_a_role_is_read_from_its_role_taker(session, academy):
    """
    A role delegates the attributes it does not declare to its role taker. (In memory,
    comparing Bob's missing age with 25 raises a TypeError, so only SQL is checked.)
    """
    s = variable(AcademyStudent, domain=academy.students)
    query = an(entity(s).where(s.age > 25))
    assert names(eql_to_sql(query, session).evaluate()) == ["Carol"]


# %% Constructs that are rejected instead of answered wrongly


def test_inference_rule_is_rejected(session, academy):
    """
    A rule derives new objects, which a database query cannot do.
    """
    m = variable(AcademyMember, domain=academy.members)
    student = inference(AcademyStudent)(role_taker=m)
    query = an(entity(student).where(m.age > 25))
    with pytest.raises(UnsupportedTranslationError):
        eql_to_sql(query, session)


def test_membership_of_a_domain_object_is_rejected(session, academy):
    """
    A domain object has no identity in the database, so its membership cannot be tested.
    """
    s = variable(AcademyStudent, domain=academy.students)
    query = an(entity(s).where(contains(s.takes_course, academy.logic)))
    with pytest.raises(UnsupportedTranslationError):
        eql_to_sql(query, session)


def test_join_inside_an_existential_over_an_element_is_rejected(session, academy):
    """
    Inside an existential quantifier over an element, a condition may only read the
    columns of the elements, not follow references to other tables.
    """
    s = variable(AcademyStudent, domain=academy.students)
    c = flat_variable(s.takes_course)
    query = an(entity(s).where(exists(c, c.name == s.role_taker.name)))
    with pytest.raises(UnsupportedTranslationError):
        eql_to_sql(query, session)


# %% One FROM element per variable


def test_variable_used_before_and_in_a_membership_test(session, academy):
    """
    A variable read before it is tested for membership still refers to the same rows.
    """
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse, domain=[academy.logic])
    query = an(entity(s).where(c.name == "Logic", contains(s.takes_course, c)))
    assert names(query.evaluate()) == ["Alice"]
    assert names(eql_to_sql(query, session).evaluate()) == ["Alice"]


def test_equality_of_an_element_with_a_variable(session, academy):
    """
    The members who are a dean of some organization, by an equality between a variable and
    the element of a collection.
    """
    o = variable(AcademyOrganization, domain=academy.organizations)
    dean = flat_variable(o.has_dean)
    m = variable(AcademyMember, domain=academy.members)
    query = an(set_of(m, o).where(m == dean))
    expected = {("Dean", "EngineeringCollege")}
    assert pairs(query.evaluate(), m, o) == expected
    assert pairs(eql_to_sql(query, session).evaluate(), m, o) == expected


@pytest.mark.xfail(
    strict=True,
    reason="Without a collection, the translator gives all variables of one class the "
    "same table unless an equality relates them (existing behavior, which "
    "test_plan_like_query pins), so a value comparison compares a row with itself.",
)
def test_variables_of_one_type_compared_by_value(session, academy):
    older = variable(AcademyMember, domain=academy.members)
    younger = variable(AcademyMember, domain=academy.members)
    query = an(
        set_of(older, younger).where(older.age > younger.age, younger.name == "Alice")
    )
    expected = {("Carol", "Alice"), ("Dean", "Alice")}
    assert pairs(eql_to_sql(query, session).evaluate(), older, younger) == expected


def test_variables_of_one_type_with_a_collection_are_independent(session, academy):
    """
    With a collection in the query, each variable has a FROM element of its own.
    """
    older = variable(AcademyMember, domain=academy.members)
    younger = variable(AcademyMember, domain=academy.members)
    organization = flat_variable(younger.is_member_of)
    query = an(
        set_of(older, younger).where(
            older.age > younger.age, organization.name == "RoboticsDepartment"
        )
    )
    expected = {("Carol", "Alice"), ("Dean", "Alice")}
    assert pairs(eql_to_sql(query, session).evaluate(), older, younger) == expected


# %% Existential quantifiers over variables that are also used outside them


def test_exists_over_a_variable_used_outside_is_correlated(session, academy):
    """
    A quantified variable that is also used outside the quantifier is bound by the outer
    query, so the quantifier only checks its condition for that binding.
    """
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse)
    query = an(
        entity(s).where(
            contains(s.takes_course, c), exists(c, c.name == "AI"), c.name == "Logic"
        )
    )
    assert names(query.evaluate()) == []
    assert names(eql_to_sql(query, session).evaluate()) == []


def test_exists_over_a_selected_element_is_correlated(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    query = an(set_of(m, o).where(exists(o, o.name == "ArtsCollege")))
    expected = {("Lecturer", "ArtsCollege")}
    assert pairs(query.evaluate(), m, o) == expected
    assert pairs(eql_to_sql(query, session).evaluate(), m, o) == expected


# %% Disjunction and negation


def test_join_inside_a_disjunction_is_rejected(session, academy):
    """
    Joining a collection inside one alternative of or_ would drop the rows that satisfy
    another alternative but have an empty collection.
    """
    m = variable(AcademyMember, domain=academy.members)
    organization = flat_variable(m.is_member_of)
    query = an(
        entity(m).where(or_(m.name == "Bob", organization.name == "ArtsCollege"))
    )
    with pytest.raises(UnsupportedTranslationError):
        eql_to_sql(query, session)


def test_equality_of_a_reference_inside_a_disjunction(session, academy):
    """
    The equality of a reference inside or_ is a condition of its alternative, not a join
    of the whole query: every student satisfies the second alternative with the Dean.
    """
    s = variable(AcademyStudent, domain=academy.students)
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(s).where(or_(s.role_taker == m, m.name == "Dean")))
    expected = {"Alice", "Bob", "Carol"}
    assert set(names(query.evaluate())) == expected
    assert set(names(eql_to_sql(query, session).evaluate())) == expected


def test_equality_of_a_reference_inside_a_negation(session, academy):
    """
    The equality of a reference inside not_ is negated with the rest of the condition:
    every student has some member who is not both its role taker and named Carol.
    """
    s = variable(AcademyStudent, domain=academy.students)
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(s).where(not_(and_(s.role_taker == m, m.name == "Carol"))))
    expected = {"Alice", "Bob", "Carol"}
    assert set(names(query.evaluate())) == expected
    assert set(names(eql_to_sql(query, session).evaluate())) == expected


# %% Values that cannot be translated faithfully


def test_reference_as_a_condition_means_it_is_set(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    query = an(entity(s).where(s.role_taker))
    assert names(eql_to_sql(query, session).evaluate()) == ["Alice", "Bob", "Carol"]


def test_attribute_declared_by_several_subclasses_is_rejected(session, academy):
    """
    Two sibling subclasses declare a motto, so narrowing to one of them would drop the
    instances of the other.
    """
    o = variable(AcademyOrganization, domain=academy.organizations)
    query = an(entity(o).where(o.motto == "Learn"))
    with pytest.raises(UnsupportedTranslationError):
        eql_to_sql(query, session)


def test_membership_of_an_unrelated_type_is_rejected(session, academy):
    """
    The deans are members, not students, so comparing their database ids with those of
    students would compare unrelated rows.
    """
    o = variable(AcademyOrganization, domain=academy.organizations)
    s = variable(AcademyStudent, domain=academy.students)
    query = an(set_of(o, s).where(contains(o.has_dean, s)))
    with pytest.raises(UnsupportedTranslationError):
        eql_to_sql(query, session)
