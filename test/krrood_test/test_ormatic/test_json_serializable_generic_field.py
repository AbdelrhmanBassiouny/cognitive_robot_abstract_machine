"""
A field typed by a JSON-serializable class keeps its column even when that class is a
generic with a free parameter: the JSON mapping stores the instance whole, so the
parameter has nothing to decide.
"""

from __future__ import annotations

from sqlalchemy import select

from krrood.ormatic.data_access_objects.helper import to_dao

from ..dataset.ormatic_interface import AnsweredQuestionDAO
from ..dataset.role_of_a_json_serializable_generic import (
    AnsweredQuestion,
    YesOrNoQuestion,
)


def test_a_role_of_a_json_serializable_generic_keeps_its_taker(session, database):
    asked = YesOrNoQuestion(wording="Is the cube on the table?")
    answered = AnsweredQuestion(role_taker=asked, answer="yes")

    session.add(to_dao(answered))
    session.commit()

    [restored] = [
        row.from_dao() for row in session.scalars(select(AnsweredQuestionDAO)).all()
    ]
    assert type(restored.role_taker) is YesOrNoQuestion
    assert restored.role_taker.wording == asked.wording
    assert restored.answer == "yes"
