"""
Per-shape close targets for Tracy's Robotiq grippers.

:mod:`~experiments.tracy_experiments.robotiq_gripper` drives the physical gripper to a
single fixed :class:`~experiments.tracy_experiments.robotiq_gripper.FingerSetpoint`
(``0`` fully open, ``0.5`` "closed") for every grasp. ``0.5`` holds the cube, cylinder
and triangular prism but not the thin rectangular prism, which needs the fingers driven
further in before they touch it. This module keeps that one number where it can be
looked up and overridden per
:class:`~experiments.montessori.semantics.MontessoriShapeCategory`, so the real
Montessori demo can size each close to the piece it is about to grasp.

The MuJoCo demo does not need this: its own
:func:`~experiments.tracy_experiments.trajectory_planning.close_gripper_around` already
measures the target body's width and closes to it directly, which the action-server
interface of the physical gripper does not expose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Mapping

from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.tracy_experiments.robotiq_gripper import FingerSetpoint

DEFAULT_CLOSE_SETPOINT = float(FingerSetpoint.CLOSED)
"""
Close setpoint used for any shape without its own entry in
:data:`SHAPE_CLOSE_SETPOINTS`, in the gripper controller's own units (``0`` fully open).

Equal to :attr:`~experiments.tracy_experiments.robotiq_gripper.FingerSetpoint.CLOSED`,
the value the demo drove every grasp to before this module existed.
"""

RECTANGULAR_PRISM_CLOSE_SETPOINT = 0.6
"""
Close setpoint for the rectangular prism, driven further in than
:data:`DEFAULT_CLOSE_SETPOINT` because the piece is too thin for the fingers to reach at
``0.5``.

A starting point to tune against the physical piece, not a measured value: raise it if
the fingers still close on air, lower it if they shove the piece aside before both pads
touch.
"""

SHAPE_CLOSE_SETPOINTS: Mapping[MontessoriShapeCategory, float] = {
    MontessoriShapeCategory.RECTANGULAR_PRISM: RECTANGULAR_PRISM_CLOSE_SETPOINT,
}
"""
Close setpoint per shape category that needs one other than
:data:`DEFAULT_CLOSE_SETPOINT`.
"""


@dataclass(frozen=True)
class GraspCloseTable:
    """
    Maps a :class:`~experiments.montessori.semantics.MontessoriShapeCategory` to the
    close setpoint its grasp should drive to.
    """

    default_setpoint: float = DEFAULT_CLOSE_SETPOINT
    """
    Setpoint for a category with no :attr:`override`.
    """

    overrides: Mapping[MontessoriShapeCategory, float] = field(
        default_factory=lambda: dict(SHAPE_CLOSE_SETPOINTS)
    )
    """
    Setpoint per category that differs from :attr:`default_setpoint`.
    """

    def setpoint_for(self, category: MontessoriShapeCategory) -> float:
        """
        The close setpoint for ``category``.

        :param category: The shape category about to be grasped.
        :return: Its close setpoint, in the gripper controller's own units.
        """
        return self.overrides.get(category, self.default_setpoint)
