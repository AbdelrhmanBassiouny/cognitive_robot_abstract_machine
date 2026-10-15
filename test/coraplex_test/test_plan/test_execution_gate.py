"""
Tests for pausing a robot between two control ticks and resuming it where it stopped.
"""

from __future__ import annotations

import threading

from giskardpy.motion_statechart.data_types import LifeCycleValues

from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.execution_gate import ExecutionGate
from coraplex.plans.factories import execute_single
from coraplex.plans.plan import Plan
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from semantic_digital_twin.datastructures.definitions import TorsoState

SECONDS_TO_SHOW_IT_WAITS = 2.0
"""
How long a paused run is watched to see that it does not finish.
"""

SECONDS_TO_FINISH = 120.0
"""
How long a resumed run is given to finish.
"""


def perform_in_simulation(plan: Plan) -> None:
    """
    Perform a plan against a kinematically simulated robot.

    :param plan: The plan to perform.
    """
    with kinematically_simulated_robot:
        plan.perform()


def test_a_new_gate_lets_the_robot_run():
    assert not ExecutionGate().is_paused


def test_a_paused_gate_reports_it_until_resumed():
    gate = ExecutionGate()

    gate.pause()
    paused = gate.is_paused
    gate.resume()

    assert paused
    assert not gate.is_paused


def test_a_paused_robot_holds_still_until_it_is_resumed(pr2_apartment_context):
    world, robot, context = pr2_apartment_context
    plan = execute_single(MoveTorsoAction(TorsoState.HIGH), context=context).plan
    context.execution_gate.pause()

    run = threading.Thread(target=perform_in_simulation, args=(plan,))
    run.start()
    run.join(timeout=SECONDS_TO_SHOW_IT_WAITS)
    still_running_while_paused = run.is_alive()
    context.execution_gate.resume()
    run.join(timeout=SECONDS_TO_FINISH)

    assert still_running_while_paused
    assert not run.is_alive()
    assert plan.root.status == LifeCycleValues.SUCCEEDED
