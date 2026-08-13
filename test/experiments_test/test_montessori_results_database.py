"""
Tests for resolving and reaching the database a Montessori run records to.
"""

from __future__ import annotations

import pytest

from experiments.montessori.results_database import (
    DATABASE_URI_ENVIRONMENT_VARIABLE,
    DEFAULT_DATABASE_URI,
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
