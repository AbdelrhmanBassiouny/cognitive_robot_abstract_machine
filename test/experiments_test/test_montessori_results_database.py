"""
Tests for resolving and reaching the database a Montessori run records to.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from experiments.montessori.results_database import (
    DATABASE_URI_ENVIRONMENT_VARIABLE,
    DEFAULT_DATABASE_URI,
    ResultsDatabase,
    UnreachableResultsDatabase,
    configured_database_uri,
    main,
    verify_reachable,
)

UNREACHABLE_URI = (
    "postgresql+psycopg://nobody:wrong@127.0.0.1:1/franka_montessori_sorting_results"
)
"""
A Postgres URI on a port nothing listens on, so reaching it fails without waiting.
"""


# %% which database a run records to
class TestResolvingTheUri:
    def test_the_default_is_used_when_nothing_overrides_it(self, monkeypatch):
        monkeypatch.delenv(DATABASE_URI_ENVIRONMENT_VARIABLE, raising=False)

        assert configured_database_uri() == DEFAULT_DATABASE_URI

    def test_the_environment_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv(DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite://")

        assert configured_database_uri() == "sqlite://"


# %% opening it
class TestOpeningSessions:
    """
    A run writes its results and the viewer reads them back, so both open the same
    database the same way.
    """

    def test_a_session_is_opened_against_the_configured_database(self, tmp_path):
        database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))

        with database.open_session() as session:
            assert session.bind.url.database == str(tmp_path / "results.db")

    def test_the_schema_is_created_before_the_first_write(self, tmp_path):
        """
        A fresh database has no tables of its own, and a run must not have to be told to
        create them first.
        """
        database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))

        with database.open_session() as session:
            tables = inspect(session.bind).get_table_names()

        assert "ShapeInsertionResultDAO" in tables

    def test_the_default_database_is_the_configured_one(self, monkeypatch):
        monkeypatch.setenv(DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite://")

        assert ResultsDatabase().uri == "sqlite://"


# %% is it actually reachable
class TestReachingTheDatabase:
    def test_a_reachable_database_verifies_quietly(self):
        assert verify_reachable("sqlite://") is None

    def test_an_unreachable_database_raises(self):
        with pytest.raises(UnreachableResultsDatabase):
            verify_reachable(UNREACHABLE_URI)

    def test_the_failure_names_the_database_without_its_password(self):
        """
        The message is printed to a terminal, so it says which database could not be
        reached without putting that database's password there too.
        """
        with pytest.raises(UnreachableResultsDatabase) as raised:
            verify_reachable(UNREACHABLE_URI)

        message = str(raised.value)
        assert "franka_montessori_sorting_results" in message
        assert "wrong" not in message

    def test_the_failure_says_what_to_do_about_it(self):
        with pytest.raises(UnreachableResultsDatabase) as raised:
            verify_reachable(UNREACHABLE_URI)

        assert "--database-uri" in str(raised.value)


# %% the pre-flight a launcher runs
class TestPreflight:
    def test_it_reports_success_for_a_reachable_database(self, capsys):
        assert main(["--database-uri", "sqlite://"]) == 0
        assert "sqlite" in capsys.readouterr().out

    def test_it_fails_for_an_unreachable_database(self, capsys):
        assert main(["--database-uri", UNREACHABLE_URI]) == 1
        assert "--database-uri" in capsys.readouterr().err

    def test_it_ignores_arguments_meant_for_the_demo(self):
        """
        A launcher forwards the run's whole argument list, most of which is the demo's.
        """
        assert main(["--viewer", "--no-rviz", "--database-uri", "sqlite://"]) == 0

    def test_it_falls_back_to_the_configured_database(self, monkeypatch):
        monkeypatch.setenv(DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite://")

        assert main([]) == 0
