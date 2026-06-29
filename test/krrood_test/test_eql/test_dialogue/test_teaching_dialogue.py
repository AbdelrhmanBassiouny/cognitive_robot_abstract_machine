from __future__ import annotations

from krrood.entity_query_language.dialogue.discourse_state import DiscourseState
from krrood.entity_query_language.dialogue.speech_act import (
    acknowledge,
    ask,
    explain,
    warn,
)
from krrood.entity_query_language.dialogue.verbalization import verbalize_speech_act
from krrood.entity_query_language.factories import why
from ...dataset.montessori_scene import build_montessori_scene


def test_full_teaching_dialogue():
    """The whole loop: the learner asks why, the teacher explains then warns, the learner
    acknowledges — every act is verbalized faithfully and every obligation is discharged.

    This ties the pieces together: a real inference explanation (the over-general rule) backs the
    cause set, the speech acts carry it, the discourse obligations sequence the turns, and the
    deterministic verbalizer renders each act.
    """
    scene = build_montessori_scene()
    question = why(scene.over_general_placement_query())
    cause_set = question.first()
    assert not cause_set.is_empty

    state = DiscourseState()
    transcript = []

    learner_question = ask(question)
    state.register(learner_question)
    transcript.append(verbalize_speech_act(learner_question))

    teacher_explanation = explain(cause_set)
    state.register(teacher_explanation)
    transcript.append(verbalize_speech_act(teacher_explanation))

    teacher_warning = warn(scene.over_general_placement_query())
    state.register(teacher_warning)
    transcript.append(verbalize_speech_act(teacher_warning))

    learner_acknowledgement = acknowledge()
    state.register(learner_acknowledgement)
    transcript.append(verbalize_speech_act(learner_acknowledgement))

    state.assert_all_discharged()

    question_text, explanation_text, warning_text, acknowledgement_text = transcript
    assert question_text.startswith("Why") and question_text.endswith("?")
    assert explanation_text.startswith("Because")
    assert warning_text.startswith("Warning:")
    assert acknowledgement_text == "Understood."
