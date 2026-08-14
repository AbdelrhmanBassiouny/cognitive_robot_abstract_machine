"""
Tests for resolving and reaching the database a Montessori run records to.
"""

from __future__ import annotations

import pytest
from krrood.ormatic.utils import create_engine
from sqlalchemy import inspect

from experiments.montessori.results_database import (
    ConfiguredDatabase,
    DATABASE_URI_ENVIRONMENT_VARIABLE,
    DEFAULT_DATABASE_URI,
    DatabaseUriOrigin,
    ReadOnlyResultsDatabase,
    ResultsDatabase,
    UnreachableResultsDatabase,
    configured_database_uri,
    main,
    verify_reachable,
    verify_writable,
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


# %% can it actually be recorded to
@pytest.fixture
def read_only_database(tmp_path) -> str:
    """
    A database that exists and accepts connections but refuses every write.

    What a role provisioned for reading only looks like from the outside, which is the
    misconfiguration a run cannot notice until its first insert.
    """
    path = tmp_path / "results.db"
    ResultsDatabase(uri="sqlite:///%s" % path).open_session().close()
    return "sqlite:///file:%s?mode=ro&uri=true" % path


class TestWritingToTheDatabase:
    def test_a_writable_database_verifies_quietly(self, tmp_path):
        assert verify_writable("sqlite:///%s" % (tmp_path / "results.db")) is None

    def test_a_read_only_database_raises(self, read_only_database):
        """
        Connecting says nothing about recording: this database is reachable, and every
        table a run writes to is already there.
        """
        assert verify_reachable(read_only_database) is None

        with pytest.raises(ReadOnlyResultsDatabase):
            verify_writable(read_only_database)

    def test_the_failure_names_the_database_without_its_password(self):
        with pytest.raises(ReadOnlyResultsDatabase) as raised:
            verify_writable(
                "postgresql+psycopg://reader:secret@127.0.0.1:1/"
                "franka_montessori_sorting_results"
            )

        message = str(raised.value)
        assert "franka_montessori_sorting_results" in message
        assert "secret" not in message

    def test_the_failure_points_at_the_environment_variable(self, read_only_database):
        """
        A URI that came from the environment appears nowhere in the command that was
        run, so a failure has to say where else to look for it.
        """
        with pytest.raises(ReadOnlyResultsDatabase) as raised:
            verify_writable(read_only_database)

        assert DATABASE_URI_ENVIRONMENT_VARIABLE in str(raised.value)

    def test_verifying_leaves_nothing_behind(self, tmp_path):
        """
        The check runs before every run, so it must not accumulate anything in the
        database it is checking.
        """
        uri = "sqlite:///%s" % (tmp_path / "results.db")
        tables_before = inspect(create_engine(uri)).get_table_names()

        verify_writable(uri)

        assert inspect(create_engine(uri)).get_table_names() == tables_before


# %% where the database came from
class TestResolvingWithItsOrigin:
    def test_a_uri_given_on_the_command_line_says_so(self, monkeypatch):
        monkeypatch.setenv(DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite://")

        resolved = ConfiguredDatabase.resolve("sqlite:///given.db")

        assert resolved.uri == "sqlite:///given.db"
        assert resolved.origin is DatabaseUriOrigin.COMMAND_LINE

    def test_a_uri_from_the_environment_says_so(self, monkeypatch):
        monkeypatch.setenv(DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite:///from_env.db")

        resolved = ConfiguredDatabase.resolve(None)

        assert resolved.uri == "sqlite:///from_env.db"
        assert resolved.origin is DatabaseUriOrigin.ENVIRONMENT

    def test_the_built_in_default_says_so(self, monkeypatch):
        monkeypatch.delenv(DATABASE_URI_ENVIRONMENT_VARIABLE, raising=False)

        resolved = ConfiguredDatabase.resolve(None)

        assert resolved.uri == DEFAULT_DATABASE_URI
        assert resolved.origin is DatabaseUriOrigin.BUILT_IN_DEFAULT


# %% the pre-flight a launcher runs
class TestPreflight:
    def test_it_reports_success_for_a_reachable_database(self, capsys, tmp_path):
        assert main(["--database-uri", "sqlite:///%s" % (tmp_path / "r.db")]) == 0
        assert "sqlite" in capsys.readouterr().out

    def test_it_fails_for_an_unreachable_database(self, capsys):
        assert main(["--database-uri", UNREACHABLE_URI]) == 1
        assert "--database-uri" in capsys.readouterr().err

    def test_it_fails_for_a_database_it_cannot_record_to(
        self, capsys, read_only_database
    ):
        """
        The whole point of the pre-flight is that a bad database is reported in a
        fraction of a second rather than after a world has been built.
        """
        assert main(["--database-uri", read_only_database]) == 1

        assert DATABASE_URI_ENVIRONMENT_VARIABLE in capsys.readouterr().err

    def test_it_ignores_arguments_meant_for_the_demo(self, tmp_path):
        """
        A launcher forwards the run's whole argument list, most of which is the demo's.
        """
        uri = "sqlite:///%s" % (tmp_path / "r.db")

        assert main(["--viewer", "--no-rviz", "--database-uri", uri]) == 0

    def test_it_falls_back_to_the_configured_database(self, monkeypatch, tmp_path):
        monkeypatch.setenv(
            DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite:///%s" % (tmp_path / "r.db")
        )

        assert main([]) == 0

    def test_it_says_the_environment_chose_the_database(
        self, monkeypatch, capsys, tmp_path
    ):
        """
        A URI set in a shell profile is invisible in the command that was run, so a run
        recording somewhere unexpected has to be traceable from what it printed.
        """
        monkeypatch.setenv(
            DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite:///%s" % (tmp_path / "r.db")
        )

        main([])

        assert DATABASE_URI_ENVIRONMENT_VARIABLE in capsys.readouterr().out
