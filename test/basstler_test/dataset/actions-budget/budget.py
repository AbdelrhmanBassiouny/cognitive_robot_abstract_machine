"""
The budget the workflows beside this file are checked against: each workflow breaks
exactly the one rule its file name says, or none.
"""

from __future__ import annotations

from basstler.actions_budget import ActionsBudget, WorkflowLimits

# %% the budget


def actions_budget() -> ActionsBudget:
    """
    :return: The dataset's budget.
    """
    return ActionsBudget(
        defaults=WorkflowLimits(job_timeout_minutes=10),
        overrides={
            "reusable.yml": WorkflowLimits(job_timeout_minutes=30),
            "overridden-heavy-pull-request.yml": WorkflowLimits(
                job_timeout_minutes=10, jobs_per_push_run=10
            ),
            "fork-push-allowed.yml": WorkflowLimits(
                job_timeout_minutes=10, skips_push_on_fork=False
            ),
            # Names a workflow the dataset does not have.
            "deleted.yml": WorkflowLimits(job_timeout_minutes=10),
        },
    )
