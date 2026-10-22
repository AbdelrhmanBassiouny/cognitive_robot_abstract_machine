"""
Tests for keeping every query Tracy asks while it resolves a sorting plan and carries it
out as a step, and for holding it at each step until the viewer moves on.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import PlanNode
from coraplex.robot_plans.actions.core.placing import PlaceAction
from krrood.entity_query_language.backends import ProbabilisticBackend
from cramera.knowledge.query_runner import EqlQueryRunner
from cramera.live.query_steps import HeldStep
from experiments.eql_showcase.insertion import InsertAction
from experiments.eql_showcase.montessori_demo import (
    MontessoriSorting,
    TracyMontessoriDemonstration,
)
from experiments.eql_showcase.open_slots import HoleRulesBackend, HoleShape
from experiments.eql_showcase.perceived_twin import SeenPiece
from experiments.eql_showcase.performed_actions import PerformedActions
from experiments.eql_showcase.query_steps import (
    EnclosingKind,
    EnclosingStatement,
    Phase,
    QueryVariable,
    QueryStepper,
    SourceExcerpt,
    StepMoment,
    StepSituation,
    VariableRole,
)

from ..conftest import SAMPLING_SEED

# %% a sorting resolved with its queries kept


@pytest.fixture
def unsorted() -> MontessoriSorting:
    """
    What resolves sorting plans for a fresh look, with Tracy's arms parked as the
    demonstration starts them.
    """
    demonstration = TracyMontessoriDemonstration(takes_commands=False)
    world = demonstration.build_simulated_world()
    return MontessoriSorting(
        twin=demonstration.look.twin,
        robot=demonstration.robot_in(world),
        perception_view=demonstration.look.view,
    )


def resolving(title: str) -> StepSituation:
    return StepSituation(Phase.RESOLUTION, title)


def test_each_open_part_of_a_sorting_is_a_query_its_backend_answers(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))
    [piece, *_] = unsorted.pieces()

    with stepper.observing():
        unsorted.insert(piece.kind)

    [resolution] = unsorted.answerer.resolutions
    asked = iter(step.faculty for step in stepper.steps)
    assert all(part.faculty in asked for part in resolution.parts)
    assert all(step.moment is StepMoment.ANSWERED for step in stepper.steps)


def test_a_query_asked_while_another_is_answered_names_its_asker(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))
    [piece, *_] = unsorted.pieces()

    with stepper.observing():
        unsorted.insert(piece.kind)

    [rules] = [
        step
        for step in stepper.steps
        if isinstance(step.asked.backend, HoleRulesBackend)
    ]
    nested = [step for step in stepper.steps if step.asker_number == rules.number]
    assert [step.writing_frame().function_name for step in nested] == [
        HoleRulesBackend.concluded_kind.__name__,
        HoleRulesBackend.evaluate.__name__,
    ]


def test_a_step_shows_the_statement_that_writes_its_query(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))

    with stepper.observing():
        unsorted.pieces()

    [step] = stepper.steps
    frame = step.writing_frame()
    excerpt = step.written_at()
    assert frame.function_name == MontessoriSorting.pieces_with_their_hole.__name__
    assert (excerpt.focus_first_line, excerpt.focus_last_line) == (
        SourceExcerpt.statement_lines(frame.filename, frame.lineno)
    )
    assert excerpt.first_line <= excerpt.focus_first_line
    assert excerpt.focus_last_line < excerpt.first_line + len(excerpt.lines)


def test_a_step_lights_up_the_bodies_its_answers_are_about(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))

    with stepper.observing():
        pieces = unsorted.pieces()

    [step] = stepper.steps
    assert step.to_payload()["highlight"] == [str(piece.root.name) for piece in pieces]


# %% carrying the sorting out


def test_placing_a_piece_not_yet_held_asks_for_the_pick_up_before_it(
    unsorted: MontessoriSorting,
):
    [piece, *_] = unsorted.pieces()
    action = unsorted.insert(piece.kind)
    context = Context(unsorted.twin.world, unsorted.robot, sampling_seed=SAMPLING_SEED)
    plan = sequential([action], context=context).plan
    performed = PerformedActions(plans=[plan])
    stepper = QueryStepper(
        situation_of=lambda: StepSituation.of_performance(performed)
        or resolving("before the plan")
    )

    with stepper.observing(), kinematically_simulated_robot:
        plan.perform()

    written_in = [step.writing_frame().function_name for step in stepper.steps]
    holding = written_in.index(PlaceAction._holding_arm_and_grasp.__name__)
    holding_step, previous_step = stepper.steps[holding : holding + 2]
    assert holding_step.asked.answers == []
    assert written_in[holding + 1] == (
        PlanNode.get_previous_node_by_designator_type.__name__
    )
    [pick_up] = previous_step.asked.answers
    assert pick_up.designator.arm is action.arm
    assert holding_step.situation.phase is Phase.EXPANSION
    assert [
        (statement.kind, statement.title)
        for statement in holding_step.situation.enclosing
    ] == [
        (EnclosingKind.ACTION, type(action).__name__),
        (EnclosingKind.ACTION, InsertAction.__name__),
    ]


# %% holding the robot at each step


def test_a_stepping_robot_is_held_at_a_query_until_the_viewer_moves_on(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"), is_stepping=True)

    def ask() -> None:
        with stepper.observing():
            unsorted.pieces()

    asking = threading.Thread(target=ask)
    asking.start()
    held = []
    for moment in (StepMoment.ASKED, StepMoment.ANSWERED):
        while stepper.held is None or stepper.held.moment is not moment:
            asking.join(0.01)
        held.append((stepper.held.number, stepper.held.moment, asking.is_alive()))
        stepper.advance()
    asking.join(10)

    assert held == [
        (0, StepMoment.ASKED, True),
        (0, StepMoment.ANSWERED, True),
    ]
    assert not asking.is_alive()


def test_a_viewer_moving_on_from_a_step_already_left_does_not_skip_the_next(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"), is_stepping=True)

    def ask() -> None:
        with stepper.observing():
            unsorted.pieces()

    asking = threading.Thread(target=ask)
    asking.start()
    while stepper.held is None:
        asking.join(0.01)
    asked_at = HeldStep(stepper.held.number, stepper.held.moment)
    stepper.advance(asked_at)
    while stepper.held is None:
        asking.join(0.01)
    stepper.advance(asked_at)
    asking.join(0.2)

    assert (stepper.held.number, stepper.held.moment) == (
        asked_at.number,
        StepMoment.ANSWERED,
    )
    assert asking.is_alive()
    stepper.advance()
    asking.join(10)


def test_a_robot_no_longer_stepped_through_carries_on(unsorted: MontessoriSorting):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"), is_stepping=True)

    def ask() -> None:
        with stepper.observing():
            unsorted.pieces()

    asking = threading.Thread(target=ask)
    asking.start()
    while stepper.held is None:
        asking.join(0.01)
    stepper.set_stepping(False, holds_nested=True)
    asking.join(10)

    assert not asking.is_alive()
    assert stepper.steps[0].moment is StepMoment.ANSWERED


def test_a_query_answered_with_kinds_names_each_kind(unsorted: MontessoriSorting):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))

    with stepper.observing():
        kinds = unsorted.kinds_to_sort()

    [step] = stepper.steps
    assert step.to_payload()["answers"] == [kind.__name__ for kind in kinds]


def test_a_query_over_the_twin_shows_which_candidates_answer_it(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))

    with stepper.observing():
        pieces = unsorted.pieces()

    [step] = stepper.steps
    readings = step.reasoning.readings
    assert [reading.thing for reading in readings] == step.candidates()
    assert [reading.thing for reading in readings if reading.selected] == pieces


# %% where a query is asked, and its variables


def test_a_step_names_the_variables_of_its_query_as_the_code_does(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))

    with stepper.observing():
        pieces = unsorted.pieces()

    [step] = stepper.steps
    sought, ranged = QueryVariable.of_asked(step.asked)
    assert (sought.name, sought.role, sought.values) == (
        "piece",
        VariableRole.SOUGHT,
        [QueryVariable.said(piece) for piece in pieces],
    )
    assert (ranged.name, ranged.role) == ("hole", VariableRole.RANGES_OVER)
    assert ranged.looked_at == len(unsorted.twin.holes)


def test_a_part_of_a_plan_is_asked_inside_the_plan_with_what_its_parts_hold(
    unsorted: MontessoriSorting,
):
    def resolving_the_plan() -> StepSituation:
        resolution = unsorted.answerer.resolutions[-1]
        return StepSituation(
            Phase.RESOLUTION,
            resolution.name,
            EnclosingStatement.of_resolution(resolution),
        )

    stepper = QueryStepper(situation_of=resolving_the_plan)
    [piece, *_] = unsorted.pieces()

    with stepper.observing():
        unsorted.insert(piece.kind)

    [side] = [
        step
        for step in stepper.steps
        if isinstance(step.asked.backend, ProbabilisticBackend)
    ]
    [plan] = side.situation.enclosing
    parts = {part.name: (part.role, part.values) for part in plan.variables}
    assert plan.kind is EnclosingKind.PLAN
    assert parts == {
        "piece": (VariableRole.ANSWERED, [QueryVariable.said(piece)]),
        "side": (VariableRole.BEING_ANSWERED, []),
        "arm": (VariableRole.OPEN, []),
        "hole": (VariableRole.OPEN, []),
    }


def test_a_concluded_kind_of_hole_lights_the_holes_of_that_kind(
    unsorted: MontessoriSorting,
):
    stepper = QueryStepper(situation_of=lambda: resolving("sorting"))
    [piece, *_] = unsorted.pieces()

    with stepper.observing():
        unsorted.insert(piece.kind)

    [concluding] = [
        step
        for step in stepper.steps
        if any(isinstance(answer, HoleShape) for answer in step.asked.answers)
    ]
    [concluded] = concluding.asked.answers
    assert concluding.to_payload()["highlight"] == [
        str(hole.region.name)
        for hole in unsorted.twin.holes
        if hole.kind is concluded.kind
    ]


def test_a_statement_typed_in_the_viewer_is_named_by_its_type():
    code = (
        Path(__file__).with_name("dataset") / "statement_typed_in_the_viewer.py"
    ).read_text()
    statement = EqlQueryRunner(
        domains=[], extra_names={SeenPiece.__name__: SeenPiece}
    ).build(code)

    [sought] = QueryVariable.of_statement(statement, [])

    assert sought.name == QueryVariable.noun_of(SeenPiece.__name__)
