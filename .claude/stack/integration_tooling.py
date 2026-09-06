"""
Carrying only the branches that change this workflow's own tooling.

A full build carries every reviewed branch, so the machinery a maintenance pass runs on
arrives mixed in with the software the repository exists to build, and a suite run over
it answers for both at once. This asks what the tooling amounts to on its own, without a
topology of its own: the same build, over fewer tips.

Which branches those are is not this module's to decide. The fork's own tooling label
says it, written from the files each pull request changes, so this reads that label
rather than deciding again what a tooling change is.
"""

from __future__ import annotations

from dataclasses import dataclass

from stack import Branch, Configuration

from integration_tips import TipStatus


@dataclass(frozen=True)
class ToolingFilter:
    """
    Which branches a build asked for the tooling carries.
    """

    label: str | None
    """
    The label a branch must carry to reach the build, absent when it was not filtered at
    all.
    """

    @classmethod
    def unfiltered(cls) -> ToolingFilter:
        """:return: A filter that leaves every branch in, which is an unfiltered build."""
        return cls(label=None)

    @classmethod
    def over(
        cls, configuration: Configuration, only_the_tooling: bool
    ) -> ToolingFilter:
        """
        :param configuration: The configuration naming the fork's tooling label.
        :param only_the_tooling: Whether the build was asked for the tooling alone.
        :return: The filter, unfiltered when it was not.
        """
        if not only_the_tooling:
            return cls.unfiltered()
        return cls(label=configuration.tooling_label)

    @property
    def is_filtering(self) -> bool:
        """:return: Whether this build was asked for the tooling at all."""
        return self.label is not None

    def leaves_out(self, branch: Branch) -> TipStatus | None:
        """
        Decide whether a filtered build carries a branch, and say why when it does not.

        :param branch: The branch to decide about.
        :return: The status to report it under, or ``None`` when the build carries it.
        """
        if not self.is_filtering:
            return None
        if self.label in branch.labels:
            return None
        return TipStatus.NOT_A_TOOLING_CHANGE
