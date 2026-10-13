"""
The ways a plan-item skill can proceed once it has gathered an item's context.
"""

from __future__ import annotations

from enum import StrEnum


class ExecutionMode(StrEnum):
    """
    How a plan-item skill proceeds once it has gathered the item's context.
    """

    ASK = "ask"
    """
    Put the choice between the other two to the user.
    """

    AUTO = "auto"
    """
    Plan implicitly and implement without waiting for approval.
    """

    PLAN = "plan"
    """
    Present the plan and stop until the user approves it.
    """
