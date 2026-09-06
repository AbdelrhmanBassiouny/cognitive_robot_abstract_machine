"""
Telling a branch's owner that its base has landed and it needs retargeting.

Retargeting a pull request's base is the one write this pass's own credential is
refused, so :func:`stack.reparents` only ever reports it. Nothing posted a notice for
that report before this - a restack conflict already reaches its owner through
:func:`maintenance_restack_steps.conflict_report`, but a pending reparent, left to a run
summary nobody without a session watches, reached nobody at all.
"""

from __future__ import annotations

from collections.abc import Sequence

from maintenance_board import PullRequestField
from maintenance_constants import NEEDS_RESOLUTION_COMMENT_PREFIX
from maintenance_github import ForkPullRequests
from stack import Branch, LabelWrite, Reparent, Stack


def reparent_notice(branch: Branch, reparent: Reparent) -> str:
    """
    Write the comment telling a branch's owner that their branch needs retargeting.

    :param branch: The branch whose base has landed.
    :param reparent: What it must be retargeted at.
    :return: The comment body.
    """
    addressed = (
        f"\n\n{branch.session}"
        if branch.session
        else "\n\nThis pull request's description names no session to address."
    )
    return (
        f"{NEEDS_RESOLUTION_COMMENT_PREFIX} `{reparent.current_base}` has landed "
        f"upstream, so `{branch.name}` needs to be retargeted at "
        f"`{reparent.target_base}`.\n\n"
        f"Retargeting a base is the one write this pass cannot perform itself - a "
        f"session must do it through the GitHub MCP server. This branch is labelled "
        f"`needs-resolution` so later passes do not re-report the same "
        f"reparent.{addressed}"
    )


def notify_reparents(
    reparents: Sequence[Reparent], stack: Stack, fork: ForkPullRequests
) -> tuple[Reparent, ...]:
    """
    Label and comment on every branch a base landed under.

    The label write reads the labels the branch carries *now*, not the ones the board
    was exported with: promotion and restack both run before this and can have written
    one since, so a snapshot read here would silently drop it - the same staleness
    :func:`maintenance_promotion.promote` already reads around.

    :param reparents: What :func:`stack.reparents` found.
    :param stack: The derived stack the reparents were read from, for each branch's
        session (a pull request's description, unlike its labels, does not change
        underneath this pass).
    :param fork: The fork to read current labels from and write the label and comment
        to.
    :return: The same reparents, for a caller that wants to know what was notified.
    """
    branches_by_name = {branch.name: branch for branch in stack.branches}
    for reparent in reparents:
        branch = branches_by_name[reparent.branch]
        number = reparent.pull_request_number
        current_labels = PullRequestField.LABELS.read(fork.pull_request(number), number)
        fork.replace_labels(
            number,
            LabelWrite.replacing(
                current_labels, added=[stack.configuration.needs_resolution_label]
            ).labels,
        )
        fork.add_comment(number, reparent_notice(branch, reparent))
    return tuple(reparents)
