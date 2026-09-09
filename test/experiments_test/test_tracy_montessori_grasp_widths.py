"""
Tests for :mod:`experiments.tracy_experiments.montessori.grasp_widths`: the close
setpoint picked for a shape is its override when it has one, and the shared default
otherwise.
"""

from __future__ import annotations

from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.tracy_experiments.montessori.grasp_widths import (
    DEFAULT_CLOSE_SETPOINT,
    RECTANGULAR_PRISM_CLOSE_SETPOINT,
    GraspCloseTable,
)
from experiments.tracy_experiments.robotiq_gripper import FingerSetpoint


def test_default_close_setpoint_is_the_controllers_own_closed_setpoint():
    assert DEFAULT_CLOSE_SETPOINT == float(FingerSetpoint.CLOSED)


def test_a_shape_without_an_override_gets_the_default_setpoint():
    table = GraspCloseTable()

    assert table.setpoint_for(MontessoriShapeCategory.CUBE) == DEFAULT_CLOSE_SETPOINT
    assert (
        table.setpoint_for(MontessoriShapeCategory.CYLINDER) == DEFAULT_CLOSE_SETPOINT
    )
    assert (
        table.setpoint_for(MontessoriShapeCategory.TRIANGULAR_PRISM)
        == DEFAULT_CLOSE_SETPOINT
    )


def test_the_rectangular_prism_is_closed_further_than_the_default():
    table = GraspCloseTable()

    setpoint = table.setpoint_for(MontessoriShapeCategory.RECTANGULAR_PRISM)

    assert setpoint == RECTANGULAR_PRISM_CLOSE_SETPOINT
    assert setpoint > DEFAULT_CLOSE_SETPOINT


def test_overrides_can_be_supplied_explicitly():
    table = GraspCloseTable(
        default_setpoint=0.4, overrides={MontessoriShapeCategory.SPHERE: 0.55}
    )

    assert table.setpoint_for(MontessoriShapeCategory.SPHERE) == 0.55
    assert table.setpoint_for(MontessoriShapeCategory.CUBE) == 0.4
