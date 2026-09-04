"""
Which plan each branch in flight belongs to, so a build can be asked to carry only one.

A full build carries every reviewed branch, and when one goes red the question is
usually whether some one plan's branches hold together on their own. This answers that
without a topology of its own: the same build, the same candidate, over fewer tips.

The mapping is not this tooling's to invent. It is generated onto the personal-notes
branch beside the plans themselves, and read through the same shell configuration every
other reader resolves it with, so nothing here decides where it lives.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dataclass_exception import DataclassException

from integration_tips import TipStatus

REPOSITORY_ROOT = Path(__file__).parent.parent.parent
"""
The checkout this tooling belongs to, from this module's own location.
"""

CONFIGURATION_SCRIPT = (
    REPOSITORY_ROOT / ".claude/hooks/resolve-personal-notes-config.sh"
)
"""
The shell that resolves the personal-notes remote and branch and the index's path.

Asked rather than restated: where the index lives is that file's to decide, and a second
answer here would be one that goes stale silently.
"""

READ_THE_INDEX = (
    f'source "{CONFIGURATION_SCRIPT}" && fetch_personal_notes_branch '
    '&& git show "FETCH_HEAD:${PLAN_BRANCH_INDEX_PATH}"'
)
"""
Fetch the notes branch once and print the whole index.

Once rather than per branch: the shell has a lookup that answers for one branch and
fetches to do it, which over sixty branches is sixty fetches.
"""

INDEX_SEPARATOR = "\t"
"""
What separates a branch from its plan in the index, which is a tab-separated file.
"""

PLAN_SEPARATOR = ","
"""
What separates plans where several are asked for in one argument.
"""


@dataclass
class BranchPlanIndexUnavailable(DataclassException):
    """
    Raised when the branch-to-plan index cannot be read.

    A filtered build cannot proceed without it: every branch would read as belonging to
    no plan, which would either empty the build or carry all of it, and both answer a
    question nobody asked.
    """

    explanation: str
    """
    What the shell said about why it could not be read.
    """

    def error_message(self) -> str:
        return (
            "the branch-to-plan index on the personal-notes branch could not be read, "
            f"so a build cannot be filtered by plan: {self.explanation}"
        )

    def suggest_correction(self) -> str:
        return (
            "check that the personal-notes branch is reachable from here and carries "
            "the generated index; a build carrying everything needs neither."
        )


@dataclass(frozen=True)
class PlanFilter:
    """
    The plans a build was asked to carry, and what the index says each branch belongs to.
    """

    wanted: frozenset[str]
    """
    The plans asked for, empty when the build was not filtered at all.
    """

    plan_of: Mapping[str, str]
    """
    Which plan each indexed branch belongs to.
    """

    @classmethod
    def unfiltered(cls) -> PlanFilter:
        """:return: A filter that leaves every branch in, which is an unfiltered build."""
        return cls(wanted=frozenset(), plan_of={})

    @classmethod
    def over(cls, plans: Iterable[str]) -> PlanFilter:
        """
        Read the index for a build asked to carry the named plans.

        :param plans: The plans asked for, each either one id or several separated by
            commas.
        :return: The filter, unfiltered when no plan was named - in which case the index
            is not read at all, so an unfiltered build never depends on it.
        :raises BranchPlanIndexUnavailable: When plans were named and the index could not
            be read.
        """
        wanted = frozenset(
            named.strip()
            for plan in plans
            for named in plan.split(PLAN_SEPARATOR)
            if named.strip()
        )
        if not wanted:
            return cls.unfiltered()
        return cls(wanted=wanted, plan_of=cls._read_the_index())

    @staticmethod
    def _read_the_index() -> Mapping[str, str]:
        """
        :return: Which plan each indexed branch belongs to.
        :raises BranchPlanIndexUnavailable: When the index could not be read.
        """
        listed = subprocess.run(
            ["bash", "-c", READ_THE_INDEX],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
        )
        if listed.returncode != 0:
            raise BranchPlanIndexUnavailable(listed.stderr.strip())
        return dict(
            line.split(INDEX_SEPARATOR, 1)
            for line in listed.stdout.splitlines()
            if INDEX_SEPARATOR in line
        )

    @property
    def is_filtering(self) -> bool:
        """:return: Whether this build was asked for particular plans at all."""
        return bool(self.wanted)

    def leaves_out(self, branch: str) -> TipStatus | None:
        """
        Decide whether a filtered build carries a branch, and say why when it does not.

        A branch the index names no plan for is reported rather than quietly dropped or
        quietly carried: the filter cannot answer for it either way, and a build that
        silently made the choice would be one nobody could read.

        :param branch: The branch to decide about.
        :return: The status to report it under, or ``None`` when the build carries it.
        """
        if not self.is_filtering:
            return None
        belongs_to = self.plan_of.get(branch)
        if belongs_to is None:
            return TipStatus.NO_PLAN_RECORDED
        if belongs_to in self.wanted:
            return None
        return TipStatus.ANOTHER_PLAN
