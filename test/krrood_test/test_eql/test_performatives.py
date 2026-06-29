"""
Demo + tests for the framework-agnostic performative (speech-act) layer.

A performative applies a force (find / inform / explain / warn) to an EQL description and verbalizes via
real fragments; compositions (sequential / parallel / try) join their children with the verbalization
engine's own coordination (``oxford_comma`` / connectives), not string concatenation. Motion acts
(``Achieve`` / ``Observe``) live in giskardpy and are tested there.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.factories import a, an, entity, variable
from krrood.entity_query_language.performatives import (
    Composition,
    Explain,
    Find,
    Inform,
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
    query = a(entity(location := variable(Location, [])).where(IsReachable(location)))
    find = Find(query)
    assert find.verbalize() == verbalize_expression(query)   # the query already opens with "Find …"
    assert isinstance(find.perform(), list)                  # find evaluates (empty domain → [])


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


# ── compositions join their children with the engine's coordination ──────────────


def test_sequential_interleaves_then():
    text = Sequential([Inform(_reachable()), Inform(_works_in())]).verbalize()
    assert text == (
        "a Location is reachable, then a StaffMember works in a Department"
    )


def test_parallel_coordinates_with_and_and_marks_concurrency():
    text = Parallel([Inform(_reachable()), Inform(_works_in())]).verbalize()
    assert text.endswith(" simultaneously")
    assert " and " in text


def test_parallel_of_three_uses_oxford_comma():
    text = Parallel(
        [Inform(_reachable()), Inform(_works_in()), Inform(_reachable())]
    ).verbalize()
    assert ", and " in text                              # the And-rule's Oxford comma, reused
    assert text.endswith(" simultaneously")


def test_try_in_order_is_an_ordered_fallback():
    text = TryInOrder([Inform(_reachable()), Inform(_works_in())]).verbalize()
    assert text.startswith("try ")
    assert ", otherwise " in text


def test_try_all_is_a_parallel_disjunction():
    text = TryAll([Inform(_reachable()), Inform(_works_in())]).verbalize()
    assert text.startswith("try ")
    assert " or " in text
    assert text.endswith(" simultaneously")


# ── the shared interface + honest execution boundaries ───────────────────────────


def test_acts_and_compositions_conform_to_performable():
    assert isinstance(Find(an(entity(variable(Location, [])))), Performable)
    assert isinstance(Inform(_reachable()), Performable)
    assert isinstance(Warn(situation="x"), Performable)
    assert isinstance(Sequential([Inform(_reachable())]), Performable)


def test_unsupported_execution_is_delegated_not_faked():
    with pytest.raises(NotImplementedError):
        Explain(_reachable()).perform()
    with pytest.raises(NotImplementedError):
        Sequential([Inform(_reachable())]).perform()
