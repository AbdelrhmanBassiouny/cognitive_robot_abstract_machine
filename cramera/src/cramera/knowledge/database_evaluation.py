"""
Answering a query from a database rather than from objects in this process.

Kept out of :mod:`cramera.knowledge.queryable_knowledge` so that nothing is pulled in
from SQLAlchemy unless a demo actually offers a recorded body of knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.evaluable import Evaluable
from krrood.ormatic.eql_interface import eql_to_sql
from sqlalchemy.orm import Session
from typing_extensions import Any, Callable

from cramera.knowledge.queryable_knowledge import QueryEvaluation


@dataclass(frozen=True)
class DatabaseEvaluation(QueryEvaluation):
    """
    Answers by translating the query into SQL and running it where the results live.
    """

    open_session: Callable[[], Session]
    """
    Opens the session a query is answered through, one per query.
    """

    def evaluate(self, expression: Evaluable) -> Any:
        """
        Answer one query against the database.

        The rows are read out before the session closes, since a row still attached to a
        closed session cannot be read from afterwards.

        :param expression: The query to answer.
        """
        with self.open_session() as session:
            return list(eql_to_sql(expression, session).evaluate())
