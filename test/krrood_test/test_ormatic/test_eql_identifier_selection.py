"""
Tests of the translation of EQL queries to SQL that selects database identifiers
(``eql_to_sql(query, session, select_identifiers=True)``).

The queries are those of :mod:`test_eql_collections`, on the same academy. The answers are
database ids, which the tests map back to data access objects to compare them by name. The
shape of the SQL is checked where the translation avoids a join. With an identifying
attribute (``identifying_attribute="name"`` here, ``"uri"`` for the IRIs of OWL2Bench), the
answers are the names themselves, which must equal the database ids mapped to names.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from typing_extensions import Any, Dict, List, Set, Tuple

from krrood.entity_query_language.factories import (
    an,
    and_,
    case_when,
    contains,
    count,
    entity,
    exists,
    flat_variable,
    not_,
    or_,
    set_of,
    variable,
)
from krrood.entity_query_language.core.mapped_variable import Attribute
from krrood.ormatic.eql_interface import (
    IdentifierSelectingTranslator,
    MissingColumnError,
    UnsupportedTranslationError,
    eql_to_sql,
)
from .test_eql_collections import academy, name_of  # noqa: F401 (fixture)
from ..dataset.academy_classes import (
    AcademyCollege,
    AcademyCourse,
    AcademyMember,
    AcademyOrganization,
    AcademyStudent,
)
from ..dataset.ormatic_interface import SymbolDAO


def translate(query: Any, session: Any) -> IdentifierSelectingTranslator:
    """
    :return: The translator of the query that selects identifiers.
    """
    translator = eql_to_sql(query, session, select_identifiers=True)
    assert isinstance(translator, IdentifierSelectingTranslator)
    return translator


def sql_of(query: Any, session: Any) -> str:
    """
    :return: The SQL text of the translation of the query that selects identifiers.
    """
    return str(translate(query, session).sql_query)


def name_of_identifier(session: Any, identifier: int) -> str:
    """
    :return: The name of the symbol with the database id, read from the role taker for a
        student.
    """
    assert isinstance(identifier, int)
    return name_of(session.get(SymbolDAO, identifier))


def entity_names(query: Any, session: Any) -> List[str]:
    """
    :return: The sorted names of the answers of an ``entity`` query, with repetitions.
    """
    return sorted(
        name_of_identifier(session, identifier)
        for identifier in translate(query, session).evaluate()
    )


def pair_names(
    query: Any, session: Any, first: Any, second: Any
) -> Set[Tuple[str, str]]:
    """
    :return: The pairs of names of the identifiers bound to ``first`` and ``second``.
    """
    return {
        (
            name_of_identifier(session, row[first]),
            name_of_identifier(session, row[second]),
        )
        for row in translate(query, session).evaluate()
    }


def from_clause_of(sql: str) -> str:
    """
    :return: The part of the outer SELECT statement from FROM up to WHERE.
    """
    from_clause = sql.split("FROM", 1)[1]
    return from_clause.split("WHERE", 1)[0]


# %% Answers are the same as those of the translation that selects objects


def test_pairs_of_an_owner_and_the_elements_of_its_collection(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    query = an(set_of(m, o))
    assert pair_names(query, session, m, o) == {
        ("Alice", "RoboticsDepartment"),
        ("Dean", "EngineeringCollege"),
        ("Lecturer", "ArtsCollege"),
        ("Lecturer", "EngineeringCollege"),
    }


def test_pairs_of_a_collection_are_read_from_its_association_table_alone(
    session, academy
):
    """
    The owner is the source column and the element the target column of the association
    table, whose foreign keys already restrict them to their classes.
    """
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    sql = sql_of(an(set_of(m, o)), session)
    tables = from_clause_of(sql)
    assert "JOIN" not in tables
    assert "AcademyMemberDAO" not in tables
    assert "SymbolDAO" not in tables


def test_entity_of_an_element(session, academy):
    o = variable(AcademyOrganization, domain=academy.organizations)
    whole = flat_variable(o.is_part_of)
    assert entity_names(an(entity(whole)), session) == [
        "ArtsCollege",
        "EngineeringCollege",
        "University",
        "University",
    ]


def test_attribute_of_an_element(session, academy):
    o = variable(AcademyOrganization, domain=academy.organizations)
    discipline = flat_variable(o.has_discipline)
    query = an(entity(o).where(discipline.name == "Engineering"))
    assert entity_names(query, session) == ["EngineeringCollege"]


def test_column_is_read_from_the_table_that_declares_it(session, academy):
    """
    The name of a discipline is read by joining the table of the discipline class alone, not
    the tables of its base classes.
    """
    o = variable(AcademyOrganization, domain=academy.organizations)
    discipline = flat_variable(o.has_discipline)
    sql = sql_of(an(entity(o).where(discipline.name == "Engineering")), session)
    tables = from_clause_of(sql)
    assert "AcademyDisciplineDAO" in tables
    assert "SymbolDAO" not in tables


def test_variable_and_its_value_are_read_from_its_own_table(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    query = an(set_of(m, m.age).where(m.age))
    sql = sql_of(query, session)
    assert "SymbolDAO" not in sql
    rows = translate(query, session).evaluate()
    assert {(name_of_identifier(session, row[m]), row[m.age]) for row in rows} == {
        ("Alice", 22),
        ("Carol", 31),
        ("Dean", 60),
    }


def test_variable_of_a_subclass_is_restricted_by_its_own_table(session, academy):
    """
    ``is_part_of`` is declared by organizations, so its association table refers to
    organizations; a variable of the subclass college must be restricted to colleges by
    joining the college table.
    """
    c = variable(AcademyCollege, domain=[])
    whole = flat_variable(c.is_part_of)
    query = an(set_of(c, whole))
    assert pair_names(query, session, c, whole) == {
        ("ArtsCollege", "University"),
        ("EngineeringCollege", "University"),
    }
    assert "AcademyCollegeDAO" in from_clause_of(sql_of(query, session))


def test_elements_of_nested_collections_with_membership(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    o = variable(AcademyOrganization, domain=academy.organizations)
    dean = flat_variable(o.has_dean)
    c = flat_variable(dean.teaches_course)
    query = an(set_of(s, c).where(contains(s.takes_course, c)))
    assert pair_names(query, session, s, c) == {("Alice", "Logic")}
    assert "EXISTS" in sql_of(query, session)


def test_membership_in_a_distinct_query_is_a_join(session, academy):
    """
    In a query with distinct answers, the membership test of a variable that is not bound
    yet joins the association table and binds the variable to its source column (OWL2Bench
    Q22 shape).
    """
    s = variable(AcademyStudent, domain=academy.students)
    o = variable(AcademyOrganization, domain=academy.organizations)
    dean = flat_variable(o.has_dean)
    c = flat_variable(dean.teaches_course)
    query = an(set_of(s, c).where(contains(s.takes_course, c)).distinct())
    assert pair_names(query, session, s, c) == {("Alice", "Logic")}
    sql = sql_of(query, session)
    assert "EXISTS" not in sql
    assert "SymbolDAO" not in sql


def test_membership_in_a_conditional_value_is_not_a_join(session, academy):
    """
    A membership test that only decides a value of ``case_when`` does not hold for every
    answer, so it stays a condition instead of becoming a join.
    """
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse, domain=[academy.logic])
    query = an(
        set_of(s, c).where(case_when(contains(s.takes_course, c), False, True))
    ).distinct()
    assert pair_names(query, session, s, c) == {
        ("Alice", "Painting"),
        ("Bob", "AI"),
        ("Bob", "Logic"),
        ("Carol", "Logic"),
        ("Carol", "Painting"),
    }


def test_membership_of_a_bound_variable_in_a_distinct_query(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse, domain=[academy.logic])
    query = an(
        entity(s).where(s.age > 25, contains(s.takes_course, c), c.name == "AI")
    ).distinct()
    assert entity_names(query, session) == ["Carol"]


def test_exists_over_nested_collections_is_correlated(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    so = flat_variable(s.is_student_of)
    whole = flat_variable(so.is_part_of)
    discipline = flat_variable(whole.has_discipline)
    query = an(
        set_of(s, so).where(exists(discipline, discipline.name == "Engineering"))
    )
    assert pair_names(query, session, s, so) == {
        ("Alice", "RoboticsDepartment"),
        ("Carol", "RoboticsDepartment"),
    }


def test_exists_over_nested_collections_is_one_subquery(session, academy):
    """
    The quantified collections are joined in one EXISTS subquery. Only colleges have
    disciplines, and the discipline table refers to colleges, so joining it keeps the
    colleges among the organizations without joining the college table.
    """
    s = variable(AcademyStudent, domain=academy.students)
    so = flat_variable(s.is_student_of)
    whole = flat_variable(so.is_part_of)
    discipline = flat_variable(whole.has_discipline)
    query = an(
        set_of(s, so).where(exists(discipline, discipline.name == "Engineering"))
    )
    sql = sql_of(query, session)
    assert sql.count("EXISTS") == 1
    assert "AcademyCollegeDAO" not in sql


def test_membership_of_a_variable_in_a_collection(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse, domain=[academy.logic])
    query = an(entity(s).where(contains(s.takes_course, c), c.name == "Logic"))
    assert entity_names(query, session) == ["Alice"]


def test_collection_as_a_condition_means_non_empty(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    assert entity_names(an(entity(m).where(m.is_head_of)), session) == ["Dean"]


def test_negated_collection_condition_means_empty(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    assert entity_names(an(entity(m).where(not_(m.is_head_of))), session) == [
        "Alice",
        "Bob",
        "Carol",
        "Lecturer",
    ]


def test_value_as_a_condition_uses_its_truth_value(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    assert entity_names(an(entity(m).where(m.age)), session) == [
        "Alice",
        "Carol",
        "Dean",
    ]


def test_not_equal_holds_for_a_missing_value(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    assert entity_names(an(entity(m).where(m.nickname != "lec")), session) == [
        "Alice",
        "Bob",
        "Carol",
        "Dean",
    ]


def test_negation_holds_when_a_comparison_with_a_missing_value_is_not_true(
    session, academy
):
    m = variable(AcademyMember, domain=academy.members)
    assert entity_names(an(entity(m).where(not_(m.age > 30))), session) == [
        "Alice",
        "Bob",
        "Lecturer",
    ]


def test_attribute_of_a_role_is_read_from_its_role_taker(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    assert entity_names(an(entity(s).where(s.age > 25)), session) == ["Carol"]


def test_selected_reference_is_the_identifier_of_the_referenced_object(
    session, academy
):
    s = variable(AcademyStudent, domain=academy.students)
    assert entity_names(an(entity(s.role_taker)), session) == ["Alice", "Bob", "Carol"]


def test_variable_used_before_and_in_a_membership_test(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse, domain=[academy.logic])
    query = an(entity(s).where(c.name == "Logic", contains(s.takes_course, c)))
    assert entity_names(query, session) == ["Alice"]


def test_equality_of_an_element_with_a_variable(session, academy):
    o = variable(AcademyOrganization, domain=academy.organizations)
    dean = flat_variable(o.has_dean)
    m = variable(AcademyMember, domain=academy.members)
    query = an(set_of(m, o).where(m == dean))
    assert pair_names(query, session, m, o) == {("Dean", "EngineeringCollege")}


def test_variables_of_one_type_compared_by_value(session, academy):
    """
    Every variable ranges over its rows independently, also without a collection in the
    query (the translation that selects objects gives such variables one table).
    """
    older = variable(AcademyMember, domain=academy.members)
    younger = variable(AcademyMember, domain=academy.members)
    query = an(
        set_of(older, younger).where(older.age > younger.age, younger.name == "Alice")
    )
    assert pair_names(query, session, older, younger) == {
        ("Carol", "Alice"),
        ("Dean", "Alice"),
    }


def test_exists_over_a_variable_used_outside_is_correlated(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse)
    query = an(
        entity(s).where(
            contains(s.takes_course, c), exists(c, c.name == "AI"), c.name == "Logic"
        )
    )
    assert entity_names(query, session) == []


def test_exists_over_a_variable_used_only_inside(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    c = variable(AcademyCourse)
    query = an(
        entity(s).where(exists(c, and_(contains(s.takes_course, c), c.name == "AI")))
    )
    assert entity_names(query, session) == ["Alice", "Carol"]


def test_exists_over_a_selected_element_is_correlated(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    query = an(set_of(m, o).where(exists(o, o.name == "ArtsCollege")))
    assert pair_names(query, session, m, o) == {("Lecturer", "ArtsCollege")}


def test_equality_of_a_reference_inside_a_disjunction(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(s).where(or_(s.role_taker == m, m.name == "Dean")))
    assert set(entity_names(query, session)) == {"Alice", "Bob", "Carol"}


def test_equality_of_a_reference_inside_a_negation(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(s).where(not_(and_(s.role_taker == m, m.name == "Carol"))))
    assert set(entity_names(query, session)) == {"Alice", "Bob", "Carol"}


def test_reference_as_a_condition_means_it_is_set(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    assert entity_names(an(entity(s).where(s.role_taker)), session) == [
        "Alice",
        "Bob",
        "Carol",
    ]


def test_ordered_and_limited_query(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    query = an(entity(m).where(m.age).ordered_by(m.age, descending=True).limit(2))
    identifiers = translate(query, session).evaluate()
    assert [name_of_identifier(session, i) for i in identifiers] == ["Dean", "Carol"]


def test_common_table_expression_of_identifiers(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    expression = eql_to_sql(
        an(set_of(m, o)),
        session,
        as_common_table_expression="memberships",
        select_identifiers=True,
    )
    assert len(session.execute(select(expression)).all()) == 4


# %% Constructs that are rejected instead of answered wrongly


def test_join_inside_a_disjunction_is_rejected(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    organization = flat_variable(m.is_member_of)
    query = an(
        entity(m).where(or_(m.name == "Bob", organization.name == "ArtsCollege"))
    )
    with pytest.raises(UnsupportedTranslationError):
        translate(query, session)


def test_join_inside_an_existential_over_an_element_is_rejected(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    c = flat_variable(s.takes_course)
    query = an(entity(s).where(exists(c, c.name == s.role_taker.name)))
    with pytest.raises(UnsupportedTranslationError):
        translate(query, session)


def test_variable_used_as_a_condition_is_rejected(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    o = variable(AcademyOrganization, domain=academy.organizations)
    query = an(entity(m).where(o))
    with pytest.raises(UnsupportedTranslationError):
        translate(query, session)


def test_membership_of_a_domain_object_is_rejected(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    query = an(entity(s).where(contains(s.takes_course, academy.logic)))
    with pytest.raises(UnsupportedTranslationError):
        translate(query, session)


def test_attribute_declared_by_several_subclasses_is_rejected(session, academy):
    o = variable(AcademyOrganization, domain=academy.organizations)
    with pytest.raises(UnsupportedTranslationError):
        translate(an(entity(o).where(o.motto == "Learn")), session)


@pytest.mark.parametrize("distinct", [False, True])
def test_membership_of_an_unrelated_type_is_rejected(session, academy, distinct):
    o = variable(AcademyOrganization, domain=academy.organizations)
    s = variable(AcademyStudent, domain=academy.students)
    query = an(set_of(o, s).where(contains(o.has_dean, s)))
    if distinct:
        query = query.distinct()
    with pytest.raises(UnsupportedTranslationError):
        translate(query, session)


def test_selection_of_an_aggregate_is_rejected(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    with pytest.raises(UnsupportedTranslationError):
        translate(an(entity(count(m))), session)


def test_default_translation_selects_objects(session, academy):
    """
    Without ``select_identifiers``, the translation selects data access objects as before.
    """
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    rows = eql_to_sql(an(set_of(m, o)), session).evaluate()
    assert all(not isinstance(row[m], int) for row in rows)
    assert "SymbolDAO" in str(eql_to_sql(an(set_of(m, o)), session).sql_query)


# %% Selection of an identifying attribute instead of the database id


def translate_identifying(query: Any, session: Any) -> IdentifierSelectingTranslator:
    """
    :return: The translator of the query that selects the name of every selected variable
        and flattened collection instead of its database id.
    """
    translator = eql_to_sql(
        query, session, select_identifiers=True, identifying_attribute="name"
    )
    assert isinstance(translator, IdentifierSelectingTranslator)
    return translator


def answer_tuple(answer: Any, selected: List[Any]) -> Tuple[Any, ...]:
    """
    :param answer: An answer of a translation: a value for an ``entity`` query, else a
        mapping from the selected expressions to values.
    :param selected: The selected expressions.
    :return: The values of the answer in the order of ``selected``.
    """
    if len(selected) == 1 and not hasattr(answer, "keys"):
        return (answer,)
    return tuple(answer[expression] for expression in selected)


def answers_by_name(query: Any, session: Any, selected: List[Any]) -> List[Tuple]:
    """
    :return: The sorted answers of the translation that selects names, with repetitions.
    """
    return sorted(
        answer_tuple(answer, selected)
        for answer in translate_identifying(query, session).evaluate()
    )


def answers_by_identifier_mapped_to_names(
    query: Any, session: Any, selected: List[Any]
) -> List[Tuple]:
    """
    :return: The sorted answers of the translation that selects database ids, with the id
        of every variable and flattened collection mapped to its name, with repetitions.
    """
    return sorted(
        tuple(
            (
                value
                if isinstance(expression, Attribute)
                else name_of_identifier(session, value)
            )
            for expression, value in zip(selected, answer_tuple(answer, selected))
        )
        for answer in translate(query, session).evaluate()
    )


def assert_names_equal_mapped_identifiers(
    query: Any, session: Any, selected: List[Any]
) -> List[Tuple]:
    """
    Assert that selecting names returns the answers of selecting database ids, with the ids
    mapped to names.

    :return: The answers of the translation that selects names.
    """
    by_name = answers_by_name(query, session, selected)
    assert by_name == answers_by_identifier_mapped_to_names(query, session, selected)
    return by_name


def test_identifying_attribute_of_an_owner_and_its_elements(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    answers = assert_names_equal_mapped_identifiers(an(set_of(m, o)), session, [m, o])
    assert answers == [
        ("Alice", "RoboticsDepartment"),
        ("Dean", "EngineeringCollege"),
        ("Lecturer", "ArtsCollege"),
        ("Lecturer", "EngineeringCollege"),
    ]


def test_identifying_attribute_joins_only_the_table_that_declares_it(session, academy):
    """
    The name of a member and of an organization is read by joining, on the id, the table
    that declares it to the association table, one alias per variable, and no table of a
    base class.
    """
    m = variable(AcademyMember, domain=academy.members)
    o = flat_variable(m.is_member_of)
    tables = from_clause_of(
        str(translate_identifying(an(set_of(m, o)), session).sql_query)
    )
    assert tables.count("JOIN") == 2
    assert "AcademyMemberDAO" in tables
    assert "AcademyOrganizationDAO" in tables
    assert "SymbolDAO" not in tables


def test_identifying_attribute_of_a_subclass_is_read_from_its_superclass_table(
    session, academy
):
    """
    ``name`` is declared by organizations; a college variable is restricted by the college
    table and its name is read from the organization table.
    """
    c = variable(AcademyCollege, domain=[])
    whole = flat_variable(c.is_part_of)
    query = an(set_of(c, whole))
    assert assert_names_equal_mapped_identifiers(query, session, [c, whole]) == [
        ("ArtsCollege", "University"),
        ("EngineeringCollege", "University"),
    ]
    tables = from_clause_of(str(translate_identifying(query, session).sql_query))
    assert "AcademyCollegeDAO" in tables
    assert "AcademyOrganizationDAO" in tables
    assert "SymbolDAO" not in tables


def test_identifying_attribute_of_a_role_is_read_from_its_role_taker(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    query = an(entity(s))
    assert assert_names_equal_mapped_identifiers(query, session, [s]) == [
        ("Alice",),
        ("Bob",),
        ("Carol",),
    ]
    tables = from_clause_of(str(translate_identifying(query, session).sql_query))
    assert "AcademyStudentDAO" in tables
    assert "AcademyMemberDAO" in tables


def test_identifying_attribute_of_an_entity_with_a_condition(session, academy):
    o = variable(AcademyOrganization, domain=academy.organizations)
    discipline = flat_variable(o.has_discipline)
    query = an(entity(o).where(discipline.name == "Engineering"))
    assert assert_names_equal_mapped_identifiers(query, session, [o]) == [
        ("EngineeringCollege",)
    ]


def test_identifying_attribute_with_a_selected_value(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    query = an(set_of(m, m.age).where(m.age))
    assert assert_names_equal_mapped_identifiers(query, session, [m, m.age]) == [
        ("Alice", 22),
        ("Carol", 31),
        ("Dean", 60),
    ]


def test_identifying_attribute_with_membership_in_a_distinct_query(session, academy):
    """
    The membership test is still a join (OWL2Bench Q22 shape); the names of the student and
    of the course are read through their tables.
    """
    s = variable(AcademyStudent, domain=academy.students)
    o = variable(AcademyOrganization, domain=academy.organizations)
    dean = flat_variable(o.has_dean)
    c = flat_variable(dean.teaches_course)
    query = an(set_of(s, c).where(contains(s.takes_course, c)).distinct())
    assert assert_names_equal_mapped_identifiers(query, session, [s, c]) == [
        ("Alice", "Logic")
    ]
    sql = str(translate_identifying(query, session).sql_query)
    assert "EXISTS" not in sql
    assert "SymbolDAO" not in sql


def test_identifying_attribute_with_exists_over_nested_collections(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    so = flat_variable(s.is_student_of)
    whole = flat_variable(so.is_part_of)
    discipline = flat_variable(whole.has_discipline)
    query = an(
        set_of(s, so).where(exists(discipline, discipline.name == "Engineering"))
    )
    assert assert_names_equal_mapped_identifiers(query, session, [s, so]) == [
        ("Alice", "RoboticsDepartment"),
        ("Carol", "RoboticsDepartment"),
    ]
    assert str(translate_identifying(query, session).sql_query).count("EXISTS") == 1


def test_identifying_attribute_requires_selecting_identifiers(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    with pytest.raises(UnsupportedTranslationError):
        eql_to_sql(an(entity(m)), session, identifying_attribute="name")


def test_selected_reference_with_an_identifying_attribute_is_rejected(session, academy):
    s = variable(AcademyStudent, domain=academy.students)
    with pytest.raises(UnsupportedTranslationError):
        translate_identifying(an(entity(s.role_taker)), session)


def test_missing_identifying_attribute_is_rejected(session, academy):
    m = variable(AcademyMember, domain=academy.members)
    with pytest.raises(MissingColumnError):
        eql_to_sql(
            an(entity(m)),
            session,
            select_identifiers=True,
            identifying_attribute="iri",
        )
