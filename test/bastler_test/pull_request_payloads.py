"""
The GitHub payloads the pull-request state tests feed their fakes, built from the same
key vocabulary the production code reads them with.

A payload is a dataclass rendered to JSON rather than a dict literal, so a test names a
field once and never spells a key the production enum already owns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bastler.pull_request_state import (
    CheckConclusion,
    CheckRunField,
    ClaudeSessionLink,
    GitHubApi,
    PullRequestField,
    PullRequestState,
)


@dataclass(frozen=True)
class PullRequestPayload:
    """
    One pull request, rendered into whichever shape an endpoint returns it in.
    """

    number: int
    """
    The pull request number.
    """

    head: str
    """
    The head branch name.
    """

    base: str = "main"
    """
    The base branch name.
    """

    state: PullRequestState = PullRequestState.OPEN
    """
    Open or closed.
    """

    draft: bool = False
    """
    Whether it is a draft.
    """

    merged_at: str | None = None
    """
    GitHub's merge timestamp.
    """

    labels: tuple[str, ...] = ()
    """
    The label names.
    """

    session: ClaudeSessionLink | None = None
    """
    The session link the description carries, if any.
    """

    additions: int | None = None
    """
    Lines added.
    """

    deletions: int | None = None
    """
    Lines deleted.
    """

    mergeable: bool | None = None
    """
    GitHub's mergeability verdict.
    """

    @property
    def head_commit(self) -> str:
        """:return: The head commit, derived from the number so every payload's differs."""
        return f"sha-{self.number}"

    def to_json(self) -> dict[str, Any]:
        """:return: The detail payload."""
        return {
            PullRequestField.NUMBER: self.number,
            PullRequestField.STATE: self.state.value,
            PullRequestField.DRAFT: self.draft,
            PullRequestField.MERGED_AT: self.merged_at,
            PullRequestField.HEAD: {
                PullRequestField.BRANCH: self.head,
                PullRequestField.COMMIT: self.head_commit,
            },
            PullRequestField.BASE: {PullRequestField.BRANCH: self.base},
            PullRequestField.LABELS: [
                {PullRequestField.LABEL_NAME: label} for label in self.labels
            ],
            PullRequestField.BODY: (
                f"Session: {self.session.url}\n" if self.session else ""
            ),
            PullRequestField.ADDITIONS: self.additions,
            PullRequestField.DELETIONS: self.deletions,
            PullRequestField.MERGEABLE: self.mergeable,
        }

    def to_list_entry(self) -> dict[str, Any]:
        """:return: The same pull request as the list endpoint returns it - the detail
        payload without the line counts and the mergeable verdict."""
        entry = self.to_json()
        for omitted in (
            PullRequestField.ADDITIONS,
            PullRequestField.DELETIONS,
            PullRequestField.MERGEABLE,
        ):
            del entry[omitted]
        return entry


def check_runs_payload(*conclusions: CheckConclusion) -> dict[str, Any]:
    """
    :param conclusions: One finished check per conclusion.
    :return: The check-runs endpoint's response carrying them.
    """
    return {
        CheckRunField.CHECK_RUNS: [
            {CheckRunField.CONCLUSION: conclusion.value} for conclusion in conclusions
        ]
    }


@dataclass
class RecordedFakeGitHubApi(GitHubApi):
    """
    An in-memory transport returning canned payloads keyed by path, recording every
    request it serves.
    """

    responses: dict[str, Any]
    """
    The payload to return for each path.
    """

    requested_paths: list[str] = field(default_factory=list)
    """
    Every path requested so far, in order.
    """

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        self.requested_paths.append(path)
        return self.responses[path]
