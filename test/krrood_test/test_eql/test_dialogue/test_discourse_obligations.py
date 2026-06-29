from __future__ import annotations

import pytest

from krrood.entity_query_language.dialogue.discourse_state import (
    DiscourseState,
    ObligationKind,
)
from krrood.entity_query_language.dialogue.exceptions import (
    NoMatchingObligationError,
    ObligationAlreadyDischargedError,
    UndischargedObligationError,
)
from krrood.entity_query_language.dialogue.speech_act import (
    acknowledge,
    ask,
    explain,
    warn,
)
from krrood.entity_query_language.factories import entity, variable, why
from krrood.entity_query_language.questions.cause import CauseSet
from ...dataset.montessori_scene import In, build_montessori_scene


def _inferred_placement(scene):
    return next(scene.over_general_placement_query().evaluate())


def test_ask_raises_answer_obligation_discharged_by_explain():
    """Asking a why-question obliges an answer, discharged by an explanation."""
    scene = build_montessori_scene()
    placement = _inferred_placement(scene)
    cause_set = why(entity(variable(In, domain=[placement]))).first()

    state = DiscourseState()
    state.register(ask(why(entity(variable(In, domain=[placement])))))

    assert len(state.open_obligations) == 1
    assert state.open_obligations[0].kind is ObligationKind.ANSWER

    state.register(explain(cause_set))

    assert state.open_obligations == []


def test_warn_raises_ack_obligation_discharged_by_acknowledge():
    """Warning obliges an acknowledgement, discharged by an acknowledge act."""
    scene = build_montessori_scene()
    placement = _inferred_placement(scene)

    state = DiscourseState()
    state.register(warn(entity(variable(In, domain=[placement]))))

    assert len(state.open_obligations) == 1
    assert state.open_obligations[0].kind is ObligationKind.ACKNOWLEDGEMENT

    state.register(acknowledge())

    assert state.open_obligations == []


def test_undischarged_obligation_detected():
    """Closing a dialogue with an unanswered question is an error."""
    scene = build_montessori_scene()
    placement = _inferred_placement(scene)

    state = DiscourseState()
    state.register(ask(why(entity(variable(In, domain=[placement])))))

    with pytest.raises(UndischargedObligationError):
        state.assert_all_discharged()


def test_double_discharge_raises():
    """Answering an already-answered question is an error."""
    scene = build_montessori_scene()
    placement = _inferred_placement(scene)
    cause_set = why(entity(variable(In, domain=[placement]))).first()

    state = DiscourseState()
    state.register(ask(why(entity(variable(In, domain=[placement])))))
    state.register(explain(cause_set))

    with pytest.raises(ObligationAlreadyDischargedError):
        state.register(explain(cause_set))


def test_response_without_obligation_raises():
    """Acknowledging when nothing was warned is an error."""
    state = DiscourseState()

    with pytest.raises(NoMatchingObligationError):
        state.register(acknowledge())
