"""
Demo + tests for the performative (speech-act) layer.

A performative applies a force (find / achieve / observe / inform / explain / warn) to an EQL description,
and verbalizes as a natural-language utterance; compositions (sequential / parallel / try) join their
children. These tests assert the layer's contribution -- the speech-act framing -- on top of the existing
EQL verbalization, over the verbalization example domain.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.performatives import (
    Achieve,
    Composition,
    Explain,
    Find,
    Inform,
    Observe,
    Parallel,
    Performable,
    Sequential,
    TryAll,
    TryInOrder,
    Warn,
)
from krrood.entity_query_language.verbalization.example_domain import (
    Department,
    IsReachable,
    Location,
    StaffMember,
    WorksIn,
)
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.exceptions import DataclassException


@dataclass
class _CannotReach(DataclassException):
    """A demo exception carrying a structured target and a remedy."""

    target: str
    """What could not be reached."""

    def error_message(self) -> str:
        return f"the gripper cannot reach {self.target}"

    def suggest_correction(self) -> str:
        return "move the base closer"


def _reachable():
    return IsReachable(variable(Location, []))


def _works_in():
    return WorksIn(variable(StaffMember, []), variable(Department, []))


# ── atomic acts frame the EQL description with their force ────────────────────────


def test_find_is_the_query_speech_act_and_evaluates():
    query = an(entity(location := variable(Location, [])).where(IsReachable(location)))
    find = Find(query)
    assert find.verbalize() == verbalize_expression(query)   # the query already opens with "Find …"
    assert isinstance(find.perform(), list)                  # find evaluates (empty domain → [])


def test_achieve_frames_the_description():
    reachable = _reachable()
    assert Achieve(reachable).verbalize() == f"Achieve that {verbalize_expression(reachable)}"
    assert "reachable" in Achieve(reachable).verbalize()


def test_observe_frames_the_description():
    reachable = _reachable()
    assert Observe(reachable).verbalize() == f"Observe whether {verbalize_expression(reachable)}"


def test_inform_asserts_the_proposition():
    reachable = _reachable()
    assert Inform(reachable).verbalize() == verbalize_expression(reachable)


def test_explain_frames_the_description():
    reachable = _reachable()
    assert Explain(reachable).verbalize() == f"Explain why {verbalize_expression(reachable)}"


def test_warn_lifts_an_exception_into_a_speech_act():
    warning = Warn.of(_CannotReach(target="the target pose"))
    assert warning.verbalize() == (
        "Warning: the gripper cannot reach the target pose Suggestion: move the base closer"
    )
    assert warning.perform() is warning


def test_warn_without_a_suggestion_omits_it():
    assert Warn(situation="something is off").verbalize() == "Warning: something is off"


# ── compositions join their children with connectives ────────────────────────────


def test_sequential_joins_with_then():
    sequence = Sequential([Achieve(_reachable()), Achieve(_works_in())])
    text = sequence.verbalize()
    assert ", then " in text
    assert text.startswith("Achieve that")


def test_parallel_marks_concurrency():
    assert Parallel([Achieve(_reachable()), Observe(_works_in())]).verbalize().endswith(
        "simultaneously"
    )


def test_try_in_order_is_an_ordered_fallback():
    text = TryInOrder([Achieve(_reachable()), Achieve(_works_in())]).verbalize()
    assert text.startswith("try ")
    assert "; otherwise " in text


def test_try_all_is_a_parallel_disjunction():
    text = TryAll([Achieve(_reachable()), Achieve(_works_in())]).verbalize()
    assert text.startswith("try ")
    assert text.endswith(" in parallel")


# ── the shared protocol + honest execution boundaries ────────────────────────────


def test_acts_and_compositions_conform_to_performable():
    assert isinstance(Find(an(entity(variable(Location, [])))), Performable)
    assert isinstance(Achieve(_reachable()), Performable)
    assert isinstance(Warn(situation="x"), Performable)
    assert isinstance(Sequential([Achieve(_reachable())]), Performable)


def test_motion_and_composition_execution_is_delegated_to_backends():
    with pytest.raises(NotImplementedError):
        Achieve(_reachable()).perform()
    with pytest.raises(NotImplementedError):
        Observe(_reachable()).perform()
    with pytest.raises(NotImplementedError):
        Sequential([Achieve(_reachable())]).perform()
