from __future__ import annotations

from krrood.entity_query_language.dialogue.answer import WhatAnswer
from krrood.entity_query_language.dialogue.speech_act import (
    acknowledge,
    ask,
    explain,
    inform,
    warn,
)
from krrood.entity_query_language.dialogue.verbalization import verbalize_speech_act
from krrood.entity_query_language.factories import why
from ...dataset.montessori_scene import build_montessori_scene


def _scene_question_and_causes():
    scene = build_montessori_scene()
    question = why(scene.over_general_placement_query())
    return scene, question, question.first()


def test_ask_why_verbalizes_as_question():
    """An Ask(Why(...)) renders as a capitalised why-question about the inferred relation."""
    _, question, _ = _scene_question_and_causes()

    text = verbalize_speech_act(ask(question))

    assert text.startswith("Why")
    assert "is in" in text
    assert text.endswith("?")


def test_explain_verbalizes_the_recorded_cause():
    """An Explain renders the recorded over-general condition as the reason."""
    _, _, cause_set = _scene_question_and_causes()

    text = verbalize_speech_act(explain(cause_set))

    assert text.startswith("Because")
    assert "on_board" in text
    assert text.endswith(".")


def test_warn_verbalizes_as_warning():
    """A Warn renders the warned-about relation behind a warning marker."""
    scene = build_montessori_scene()

    text = verbalize_speech_act(warn(scene.over_general_placement_query()))

    assert text.startswith("Warning:")
    assert "is in" in text


def test_inform_verbalizes_as_statement():
    """An Inform renders the asserted relation as a sentence."""
    scene, _, cause_set = _scene_question_and_causes()
    answer = WhatAnswer(
        query=scene.over_general_placement_query(), results=(cause_set.instance,)
    )

    text = verbalize_speech_act(inform(answer))

    assert "is in" in text
    assert text.endswith(".")


def test_acknowledge_verbalizes():
    """An Acknowledge renders the fixed acknowledgement."""
    assert verbalize_speech_act(acknowledge()) == "Understood."
