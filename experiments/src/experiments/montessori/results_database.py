"""
Where a Montessori run records its results, and whether that is reachable.

Kept apart from the demo itself so a launcher can check the database before paying for
the CRAM stack's import and a whole world build: reaching it costs a fraction of a
second, and finding out afterwards costs a minute and buries the reason under a hundred-
line traceback.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

from krrood.exceptions import DataclassException
from krrood.ormatic.utils import create_engine
from sqlalchemy import MetaData, Table
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.sqltypes import NullType
from typing_extensions import List, Optional

DEFAULT_DATABASE_URI = (
    "postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/"
    "franka_montessori_sorting_results"
)
"""
Database URI used when neither ``--database-uri`` nor
:data:`DATABASE_URI_ENVIRONMENT_VARIABLE` is given.

Reuses the ``semantic_digital_twin`` role already provisioned on this host for the other
demos/experiments in this workspace (see ``coraplex_panda_demo/demo3.py``'s own
``DATABASE_URI``); only the database itself, ``franka_montessori_sorting_results``, is
dedicated to this demo. Uses the ``psycopg`` (v3) driver explicitly since only that, not
``psycopg2``, is installed in this environment.

Provision the role and this database once, before the first run, with
``semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql``
(see that script's own header for its ``psql`` invocation).
"""

DATABASE_URI_ENVIRONMENT_VARIABLE = "FRANKA_MONTESSORI_SORTING_DATABASE_URI"
"""
Environment variable overriding :data:`DEFAULT_DATABASE_URI` for every run.
"""


def configured_database_uri() -> str:
    """
    The database a run records to when it is not given one on the command line.
    """
    return os.getenv(DATABASE_URI_ENVIRONMENT_VARIABLE, DEFAULT_DATABASE_URI)


def database_label(database_uri: str) -> str:
    """
    A database URI as it can be shown to someone, with its password withheld.

    :param database_uri: The URI to render.
    """
    return make_url(database_uri).render_as_string(hide_password=True)


@dataclass
class ResultsDatabase:
    """
    The database a Montessori run records its results to, and reads them back from.
    """

    uri: str = field(default_factory=configured_database_uri)
    """
    Where the results live.
    """

    _sessions: Optional[sessionmaker] = field(default=None, init=False, repr=False)
    """
    Opens sessions on the engine this database has already prepared, once it has one.
    """

    def open_session(self) -> Session:
        """
        Open a session against the results, preparing the database on the first call.
        """
        if self._sessions is None:
            self._sessions = self._prepared_sessions()
        return self._sessions()

    def _prepared_sessions(self) -> sessionmaker:
        """
        Connect, creating this module's tables if they are not there yet.

        Done once per database rather than once per session: reading the whole generated
        ``experiments`` schema and issuing its ``CREATE TABLE`` statements takes the best
        part of a minute, which a query answered while a demo runs cannot pay.

        Skips any table ORMatic could not assign a real column type to (surfaced as
        SQLAlchemy's ``NullType``, e.g. ``EpisodePlayerDAO.rdr_viewer`` for the
        ``RDRCaseViewer`` field it has no mapping for), together with every table that
        depends on a skipped one through a foreign key -- transitively, since joined-
        table inheritance chains more than one table deep. One unrelated, pre-existing
        gap in the huge generated ``experiments`` schema must not stop every other
        table, including this demo's own, from being created; a table left out purely
        because it depends on a skipped one would otherwise fail with an "undefined
        table" error the moment ``CREATE TABLE`` tried to reference it.
        """
        engine = create_engine(self.uri)
        metadata = self._schema()
        metadata.create_all(engine, tables=self._creatable_tables(metadata))
        return sessionmaker(engine)

    @staticmethod
    def _schema() -> MetaData:
        """
        The generated ``experiments`` schema every result table belongs to.
        """
        import experiments.orm.ormatic_interface as ormatic_interface

        return ormatic_interface.Base.metadata

    @staticmethod
    def _creatable_tables(metadata: MetaData) -> List[Table]:
        """
        Every table of a schema that can actually be created.

        :param metadata: The schema to filter.
        """
        excluded = {
            name
            for name, table in metadata.tables.items()
            if any(isinstance(column.type, NullType) for column in table.columns)
        }
        spreading = True
        while spreading:
            spreading = False
            for name, table in metadata.tables.items():
                if name in excluded:
                    continue
                if any(
                    foreign_key.column.table.name in excluded
                    for foreign_key in table.foreign_keys
                ):
                    excluded.add(name)
                    spreading = True
        return [
            table for name, table in metadata.tables.items() if name not in excluded
        ]


@dataclass
class UnreachableResultsDatabase(DataclassException):
    """
    Raised when the database a run would record its results to cannot be connected to.
    """

    database_uri: str
    """
    The database that could not be reached.
    """

    reason: str
    """
    What the driver said went wrong.
    """

    def error_message(self) -> str:
        return "Cannot reach the results database %s: %s" % (
            database_label(self.database_uri),
            self.reason,
        )

    def suggest_correction(self) -> str:
        return (
            "Provision it once as described in "
            "experiments/src/experiments/montessori/README.md, or point the run at "
            "another database with --database-uri (for a throwaway one, "
            "--database-uri sqlite:///montessori.db). An authentication failure on an "
            "existing role usually means that role's password is not the one "
            "DEFAULT_DATABASE_URI assumes."
        )


def verify_reachable(database_uri: str) -> None:
    """
    Open and close one connection to the database a run would record to.

    :param database_uri: The database to reach.
    :raises UnreachableResultsDatabase: When no connection can be opened.
    """
    try:
        with create_engine(database_uri).connect():
            pass
    except SQLAlchemyError as error:
        raise UnreachableResultsDatabase(
            database_uri=database_uri, reason=str(error.orig or error).strip()
        ) from error


def main(argument_list: Optional[List[str]] = None) -> int:
    """
    Check the database a run would record to, for a launcher to call before starting.

    Reads only ``--database-uri`` and ignores everything else, so a launcher can forward
    the run's whole argument list without knowing which parts are the demo's.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 when the database is reachable, 1 when it is not.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-uri", default=configured_database_uri())
    arguments, _ = parser.parse_known_args(argument_list)
    try:
        verify_reachable(arguments.database_uri)
    except UnreachableResultsDatabase as error:
        print(error, file=sys.stderr)
        return 1
    print("Recording results to %s" % database_label(arguments.database_uri))
    return 0


if __name__ == "__main__":
    sys.exit(main())
