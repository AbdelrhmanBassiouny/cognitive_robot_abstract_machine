"""
Tests for a query backend stating what it can answer, as a capability over a statement
-- the same shape a detector already states its own capability over a look.
"""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from krrood.entity_query_language.backends import (
    EntityQueryLanguageBackend,
    EntityQueryLanguageGenerativeBackend,
    ProbabilisticBackend,
    SQLAlchemyBackend,
    backend_supplies,
)
from krrood.entity_query_language.factories import (
    a,
    an,
    average,
    distribution_of,
    entity,
    variable,
)
from ..dataset.example_classes import EnumAction, KRROODPose, KRROODPosition, TestEnum
from ..dataset.semantic_world_like_classes import Body
from ..dataset.ormatic_interface import *  # type: ignore
from .test_probabilistic_queries._fixtures import OtherClass

# %% a selective backend answers anything but an underspecified match


def test_the_native_backend_answers_a_fully_specified_statement():
    backend = EntityQueryLanguageBackend()
    pose_variable = variable(KRROODPose, domain=[])

    statement = an(entity(pose_variable).where(pose_variable.position.x > 0.5))

    assert backend.capability(statement) is True


def test_the_native_backend_answers_a_fully_specified_match():
    backend = EntityQueryLanguageBackend()

    statement = a(KRROODPosition)(x=1.0, y=2.0, z=3.0)

    assert backend.capability(statement) is True


def test_the_native_backend_refuses_an_underspecified_match():
    backend = EntityQueryLanguageBackend()

    statement = a(KRROODPosition)(x=..., y=2.0, z=3.0)

    assert backend.capability(statement) is False


# %% a generative backend answers only a match, and only where every open leaf is enumerable


def test_the_generative_backend_answers_a_match_left_open_only_on_an_enum_leaf():
    backend = EntityQueryLanguageGenerativeBackend()

    statement = an(EnumAction)(obj=Body("body"), enum=...)

    assert backend.capability(statement) is True


def test_the_generative_backend_refuses_a_match_left_open_on_a_non_enum_leaf():
    backend = EntityQueryLanguageGenerativeBackend()

    statement = an(EnumAction)(obj=..., enum=TestEnum.OPTION_A)

    assert backend.capability(statement) is False


def test_the_generative_backend_refuses_a_statement_that_is_not_a_match():
    backend = EntityQueryLanguageGenerativeBackend()
    pose_variable = variable(KRROODPose, domain=[])

    statement = an(entity(pose_variable))

    assert backend.capability(statement) is False


# %% the database backend answers only what it can also select, over a mapped class


def test_the_database_backend_answers_a_statement_over_a_mapped_class(
    session, database
):
    backend = SQLAlchemyBackend(sessionmaker(session.bind))
    pose_variable = variable(KRROODPose, domain=[])

    statement = an(entity(pose_variable).where(pose_variable.position.x > 0.5))

    assert backend.capability(statement) is True


def test_the_database_backend_refuses_a_statement_over_an_unmapped_class(
    session, database
):
    backend = SQLAlchemyBackend(sessionmaker(session.bind))
    other_variable = variable(OtherClass, domain=[])

    statement = an(entity(other_variable))

    assert backend.capability(statement) is False


def test_the_database_backend_still_refuses_an_underspecified_match(session, database):
    backend = SQLAlchemyBackend(sessionmaker(session.bind))

    statement = a(KRROODPosition)(x=..., y=2.0, z=3.0)

    assert backend.capability(statement) is False


# %% the probabilistic backend answers what it resolves in closed form, or generates otherwise


def test_the_probabilistic_backend_answers_a_bare_average_selection():
    backend = ProbabilisticBackend()
    x = variable(KRROODPosition, domain=[])

    assert backend.capability(entity(average(x.x))) is True


def test_the_probabilistic_backend_answers_a_distribution_query():
    backend = ProbabilisticBackend()

    statement = distribution_of(a(KRROODPosition)(x=..., y=..., z=...))

    assert backend.capability(statement) is True


def test_the_probabilistic_backend_refuses_a_grouped_average_selection():
    backend = ProbabilisticBackend()
    x = variable(KRROODPosition, domain=[])

    assert backend.capability(average(x.x).grouped_by(x)) is False


def test_the_probabilistic_backend_falls_through_to_generating_a_match():
    """
    Unlike :class:`EntityQueryLanguageGenerativeBackend`, the probabilistic backend does
    not need an open leaf to be enum-typed -- it samples continuous leaves from the
    resolved model instead of enumerating them.
    """
    backend = ProbabilisticBackend()

    statement = a(KRROODPosition)(x=..., y=2.0, z=3.0)

    assert backend.capability(statement) is True


# %% asking a backend for one field rather than a whole statement


def test_a_backend_that_can_supply_an_enum_field():
    backend = EntityQueryLanguageGenerativeBackend()
    action = variable(EnumAction, domain=[])

    assert backend_supplies(backend, action.enum) is True


def test_a_backend_that_cannot_supply_a_non_enum_field():
    backend = EntityQueryLanguageGenerativeBackend()
    action = variable(EnumAction, domain=[])

    assert backend_supplies(backend, action.obj) is False
