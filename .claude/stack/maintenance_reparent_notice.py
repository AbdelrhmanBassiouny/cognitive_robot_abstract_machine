"""
Retargeting a branch whose base has landed, or telling its owner when GitHub refuses.

A Claude session's own proxied credential was probed against the live API and refused a
base-branch retarget - the one write that probe found unavailable to it, so
:func:`stack.reparents` only ever reported it for a session to perform through the
GitHub MCP server. This module's own credential authenticates its requests directly
rather than through that proxy, so it attempts the retarget itself and reports what
GitHub says here rather than assuming the same refusal. Only a genuine refusal falls
back to a notice: a restack conflict already reaches its owner through
:func:`maintenance_restack_steps.conflict_report`, but a pending reparent, left to a run
summary nobody without a session watches, reached nobody at all before this.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from maintenance_board import PullRequestField
from maintenance_constants import NEEDS_RESOLUTION_COMMENT_PREFIX
from maintenance_github import ForkPullRequests
from stack import Branch, LabelWrite, Reparent, Stack


@dataclass(frozen=True)
class RetargetOutcome:
    """
    What became of one pending reparent.
    """

    reparent: Reparent
    """
    What :func:`stack.reparents` found.
    """

    retargeted: bool
    """
    Whether this credential's own retarget succeeded.

    ``False`` means GitHub refused it and the branch's owner was labelled and commented
    at instead.
    """


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
        f"GitHub refused this pass's own attempt to retarget it - a session must do it "
        f"through the GitHub MCP server. This branch is labelled `needs-resolution` so "
        f"later passes do not re-report the same reparent.{addressed}"
    )


def resolve_reparents(
    reparents: Sequence[Reparent], stack: Stack, fork: ForkPullRequests
) -> tuple[RetargetOutcome, ...]:
    """
    Retarget every branch a base landed under, or label and comment where GitHub
    refuses.

    The label write, for a retarget GitHub refuses, reads the labels the branch carries
    *now*, not the ones the board was exported with: promotion and restack both run
    before this and can have written one since, so a snapshot read here would silently
    drop it - the same staleness :func:`maintenance_promotion.promote` already reads
    around.

    :param reparents: What :func:`stack.reparents` found.
    :param stack: The derived stack the reparents were read from, for each branch's
        session (a pull request's description, unlike its labels, does not change
        underneath this pass).
    :param fork: The fork to retarget through, and to read current labels from and
        write the label and comment to when it refuses.
    :return: One outcome per reparent, in the order given.
    """
    branches_by_name = {branch.name: branch for branch in stack.branches}
    outcomes = []
    for reparent in reparents:
        number = reparent.pull_request_number
        if fork.retarget_base(number, reparent.target_base):
            outcomes.append(RetargetOutcome(reparent, retargeted=True))
            continue
        branch = branches_by_name[reparent.branch]
        current_labels = PullRequestField.LABELS.read(fork.pull_request(number), number)
        fork.replace_labels(
            number,
            LabelWrite.replacing(
                current_labels, added=[stack.configuration.needs_resolution_label]
            ).labels,
        )
        fork.add_comment(number, reparent_notice(branch, reparent))
        outcomes.append(RetargetOutcome(reparent, retargeted=False))
    return tuple(outcomes)
