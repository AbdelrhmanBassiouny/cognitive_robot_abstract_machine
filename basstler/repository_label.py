"""
The pull request labels this tooling reads or applies, which a fork has to carry.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.repository import Repository


class RepositoryLabel(StrEnum):
    """
    Every label this tooling reads or applies, each with the description it is created
    with.

    A member is its own label name. The dashboard interprets a subset of them
    (``build_dashboard.PullRequestLabel``) and the stack workflow applies others, three of
    them under names ``stack.toml`` lets a fork change - the members here are those
    defaults, held to them by a test.
    """

    purpose: str
    """
    What the label means, used as its description when it is created.
    """

    def __new__(cls, label: str, purpose: str) -> RepositoryLabel:
        """
        Make a member that is its own label name and carries what the label means.

        :param label: The label's name, as GitHub stores it.
        :param purpose: What it means, used as the description when it is created.
        :return: The member.
        """
        member = str.__new__(cls, label)
        member._value_ = label
        member.purpose = purpose
        return member

    MERGED = ("merged", "The changes landed even though GitHub never recorded a merge")
    """
    Read by the dashboard, which treats the label exactly like a real merge.
    """

    IN_REVIEW = ("in-review", "Under review")
    """
    Put on a branch that has reached the upstream review queue.
    """

    BUG = ("bug", "A bug fix")
    """
    Applied by a session opening a bug-fix pull request, and shown as a dashboard chip.
    """

    REBASE = (
        "rebase",
        "Restack this branch by rebasing it rather than merging its parent",
    )
    """
    Authorises the stack workflow to rewrite a branch's published history.
    """

    NEEDS_RESOLUTION = (
        "needs-resolution",
        "Conflicts with its parent, and its owner needs to resolve that",
    )
    """
    Put on a branch whose owner has been asked to resolve a conflict.
    """

    PROMOTION_LINK_SENT = (
        "cram2-link-sent",
        "Carries the link that opens its upstream pull request",
    )
    """
    Marks a branch whose promotion link has been built, so a later pass does not rebuild
    it.
    """

    def creation_command(self, repository: Repository) -> str:
        """
        The ``gh`` command that creates this label.

        :param repository: The repository to create it in.
        :return: The command, ready to paste.
        """
        return (
            f"gh label create {self.value} --repo {repository.full_name} "
            f'--description "{self.purpose}"'
        )
