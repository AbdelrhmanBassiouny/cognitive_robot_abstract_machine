"""
The runs a demonstration already finished, kept in a database and asked about in SQL.

Each finished run is stored through ORMatic, and a question about past runs is written
in the same entity query language as every other question; ORMatic translates it to SQL
and the database answers it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from typing_extensions import Any, List, Optional

from cramera.knowledge.queryable_knowledge import QueryEvaluation, QueryTranslation
from krrood.entity_query_language.evaluable import Evaluable
from krrood.ormatic.data_access_objects.dao import DataAccessObject
from krrood.ormatic.data_access_objects.helper import to_dao
from krrood.ormatic.eql_interface import eql_to_sql
from krrood.ormatic.utils import create_engine

from experiments.eql_showcase.performed_actions import RecordedRun

logger = logging.getLogger(__name__)

SQLITE_URL_PREFIX = "sqlite:///"
"""
What an SQLAlchemy URL naming an SQLite database file begins with.
"""

SQL_LANGUAGE = "SQL"
"""
The name of the language a translated query is answered in.
"""

# %% the database of finished runs


@dataclass
class RunDatabase:
    """
    A database of finished runs, created on first use.
    """

    path: Path
    """
    The SQLite file the runs are kept in.
    """

    engine: Engine = field(init=False)
    """
    The connection to the database.
    """

    def __post_init__(self) -> None:
        # generated from this package's own classes, so imported only once they exist
        from experiments.orm.ormatic_interface import Base

        self.engine = create_engine(f"{SQLITE_URL_PREFIX}{self.path}")
        Base.metadata.create_all(bind=self.engine)

    def session(self) -> Session:
        """
        A new session on the database.
        """
        return sessionmaker(self.engine)()

    def remember(self, run: RecordedRun) -> None:
        """
        Store a finished run.

        :param run: The run to store.
        """
        with self.session() as session:
            session.add(to_dao(run))
            session.commit()


# %% answering in SQL


@dataclass
class SqlEvaluation(QueryEvaluation):
    """
    Answers a query by translating it to SQL and running it on a database of finished
    runs.
    """

    database: RunDatabase
    """
    The database the translated query runs on.
    """

    def evaluate(self, expression: Evaluable) -> List[Any]:
        """
        Answer the query in SQL, with each stored row read back as the object it stores.

        :param expression: The query to answer.
        """
        with self.database.session() as session:
            translation = eql_to_sql(expression, session)
            logger.info("answered in SQL: %s", self.statement_of(translation))
            return [self._object_of(row) for row in translation.evaluate()]

    def translate(self, expression: Evaluable) -> Optional[QueryTranslation]:
        """
        The SQL statement the query is answered by.

        :param expression: The query to translate.
        """
        with self.database.session() as session:
            return QueryTranslation(
                language=SQL_LANGUAGE,
                statement=self.statement_of(eql_to_sql(expression, session)),
            )

    @staticmethod
    def statement_of(translation: Any) -> str:
        """
        The SQL a translation runs, with its values written in place.

        :param translation: The translation of one query.
        """
        return str(
            translation.sql_query.compile(compile_kwargs={"literal_binds": True})
        )

    def _object_of(self, row: Any) -> Any:
        """
        The value a row of the answer stands for: the object a stored row maps back to,
        and a selected set of values with each value read back the same way.

        :param row: One row of the answer.
        """
        if isinstance(row, DataAccessObject):
            return row.from_dao()
        if isinstance(row, dict):
            return {key: self._object_of(value) for key, value in row.items()}
        return row
