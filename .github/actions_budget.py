"""
The Actions budget basstler holds every workflow in ``.github/workflows`` to.

Edit this file by hand from here on.
"""

from __future__ import annotations

from basstler.actions_budget import ActionsBudget, WorkflowLimits

# %% the budget


def actions_budget() -> ActionsBudget:
    """
    :return: This repository's Actions budget.
    """
    return ActionsBudget(
        overrides={
            # The whole library matrix on every pull-request push, until the
            # changed-library matrix narrows it to what a change touches.
            "ci.yml": WorkflowLimits(jobs_per_push_run=16),
            # A fork builds the image its own CI runs in, so a push to a fork has to
            # build it.
            "update_docker.yml": WorkflowLimits(
                job_timeout_minutes=120, skips_push_on_fork=False
            ),
        },
    )
