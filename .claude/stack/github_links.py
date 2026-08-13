"""
Every github.com URL this tooling builds or reads back, written once.

A URL format stated in more than one place is two formats that happen to agree today:
the promotion link is *built* when a branch is promoted and *read back* when the pending
ones are reported, and a hand-written pattern for the second is a second copy of the
first. Both come from here, so a change to how a link is composed changes how it is
recognised in the same edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import quote

if TYPE_CHECKING:
    from stack import Repository


@dataclass(frozen=True)
class GitHubLinks:
    """
    The links one repository has, composed from the one statement of the host.
    """

    HOST: ClassVar[str] = "https://github.com"
    """
    Where every link this builds points, named once rather than at each of them.
    """

    repository: Repository
    """
    The repository the links belong to.
    """

    @property
    def repository_url(self) -> str:
        """:return: The repository's own page."""
        return f"{self.HOST}/{self.repository}"

    def pull_request(self, number: int) -> str:
        """:param number: The pull request to link to.
        :return: That pull request's page."""
        return f"{self.repository_url}/pull/{number}"

    def comparison_with(self, base: str) -> str:
        """
        Open the comparison every branch promoted into this repository starts from.

        Everything up to the branch being compared, which is what a caller reading a
        recorded link back has to recognise it by - the branch itself varies, the rest
        does not.

        :param base: The branch being compared against.
        :return: The comparison's URL, up to the branch compared with it.
        """
        return f"{self.repository_url}/compare/{base}..."

    def comparison_pattern(self, base: str) -> re.Pattern[str]:
        """
        Match a comparison link of this repository's wherever it was recorded.

        Backticks end a match as whitespace does, so a description that wraps the link
        in code formatting reads back as the link rather than the formatting around it.

        :param base: The branch being compared against.
        :return: The pattern matching such a link.
        """
        return re.compile(re.escape(self.comparison_with(base)) + r"[^\s`]*")

    def create_pull_request_from(
        self, base: str, head: str, title: str, body: str
    ) -> str:
        """
        Open a comparison ready to be turned into a pull request, already filled in.

        The prefill travels in the query string, so every part of it is encoded here -
        an unencoded character truncates it silently.

        :param base: The branch to merge into.
        :param head: The branch to merge, as ``owner:branch`` when it is another fork's.
        :param title: Title to prefill.
        :param body: Description to prefill.
        :return: The compare-and-create URL.
        """
        return (
            f"{self.comparison_with(base)}{head}"
            f"?expand=1&title={quote(title)}&body={quote(body)}"
        )
