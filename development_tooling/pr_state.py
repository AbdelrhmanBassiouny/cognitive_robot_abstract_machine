"""
One shared fetch/compute layer for live pull-request state.

Both of this repository's dashboard systems - the stacked-PR board (``stack.py``'s
``board.json``) and the plan dashboards (``build_dashboard.py``'s ``pr_data.json``) -
need the same facts about a pull request: its CI conclusion, its size versus its base,
whether it would merge cleanly, and which Claude session is working it. This module
computes those facts once and serializes them into either consumer's document shape,
so neither system re-derives them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# %% check rollup reduction


class CheckConclusion(StrEnum):
    """The single conclusion a pull request's whole check rollup reduces to."""

    SUCCESS = "success"
    """Every check completed successfully."""

    FAILURE = "failure"
    """At least one check failed, errored, was cancelled, or timed out."""

    PENDING = "pending"
    """No check failed, but at least one is still queued or running."""


FAILURE_STATES = frozenset({"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT"})
"""Raw per-check states that make the whole rollup a :attr:`CheckConclusion.FAILURE`."""

PENDING_STATES = frozenset({"PENDING", "IN_PROGRESS", "QUEUED", ""})
"""Raw per-check states that make a failure-free rollup a
:attr:`CheckConclusion.PENDING`."""


def check_conclusion(checks: list[dict[str, Any]]) -> CheckConclusion | None:
    """Reduce a pull request's check rollup to one conclusion.

    Tolerates both payload dialects for a single check's state: the REST check-runs
    shape (``conclusion``/``status``) and the GraphQL rollup shape (``state``).

    :param checks: One mapping per check, as returned by GitHub.
    :return: The reduced conclusion, or ``None`` when no check has run at all.
    """
    if not checks:
        return None
    states = {
        str(
            check.get("conclusion") or check.get("state") or check.get("status") or ""
        ).upper()
        for check in checks
    }
    if states & FAILURE_STATES:
        return CheckConclusion.FAILURE
    if states & PENDING_STATES:
        return CheckConclusion.PENDING
    return CheckConclusion.SUCCESS


# %% session-link parse

SESSION_URL_PATTERN = re.compile(r"https://claude\.ai/code/session_[\w-]+")
"""What a Claude session link in a pull request body looks like."""


def parse_session_url(body: str) -> str | None:
    """Extract the Claude session URL a pull request body references.

    :param body: The pull request body text.
    :return: The first session URL in it, or ``None`` if there is none.
    """
    match = SESSION_URL_PATTERN.search(body)
    return match.group(0) if match else None


# %% change-size classification

DEFAULT_SHORT_CHANGE_THRESHOLD = 400
"""Lines changed (additions plus deletions) up to which a change counts as short."""


def is_short_change(
    lines_changed: int, threshold: int = DEFAULT_SHORT_CHANGE_THRESHOLD
) -> bool:
    """Classify a change's size against the short-change threshold.

    :param lines_changed: Additions plus deletions versus the base.
    :param threshold: The largest line count that still counts as short.
    :return: Whether the change is short.
    """
    return lines_changed <= threshold


# %% live-state model


class PullRequestState(StrEnum):
    """GitHub's coarse-grained pull request state."""

    OPEN = "open"
    CLOSED = "closed"


@dataclass
class PullRequestLiveState:
    """Everything both dashboard systems want to know about one live pull request."""

    number: int
    """The pull request number."""

    head: str
    """The head branch name."""

    base: str
    """The base branch name - the pull request's parent in a stack."""

    state: PullRequestState
    """Whether the pull request is open or closed."""

    draft: bool
    """Whether the pull request is currently a draft."""

    merged_at: str | None
    """GitHub's merge timestamp, or ``None`` if it never recorded a merge."""

    labels: list[str] = field(default_factory=list)
    """The labels currently on the pull request."""

    ci: CheckConclusion | None = None
    """The reduced check conclusion on the head commit, or ``None`` when no check ran."""

    additions: int | None = None
    """Lines added versus the base, or ``None`` when not fetched."""

    deletions: int | None = None
    """Lines deleted versus the base, or ``None`` when not fetched."""

    mergeable: bool | None = None
    """Whether GitHub reports the pull request as cleanly mergeable onto its base -
    ``None`` while GitHub is still computing it or when not fetched."""

    session_url: str | None = None
    """The Claude session URL parsed from the pull request body, if any."""

    @property
    def lines_changed(self) -> int | None:
        """Additions plus deletions versus the base, or ``None`` when either count is
        unknown."""
        if self.additions is None or self.deletions is None:
            return None
        return self.additions + self.deletions

    def to_board_entry(self) -> dict[str, Any]:
        """:return: this pull request as one ``board.json`` entry, the shape the
        stacked-PR helper's ``load_board`` reads."""
        return {
            "number": self.number,
            "head": self.head,
            "base": self.base,
            "draft": self.draft,
            "labels": list(self.labels),
            "ci": self.ci.value if self.ci else None,
            "session": self.session_url,
        }

    def to_pull_request_data_entry(self) -> dict[str, Any]:
        """:return: this pull request as one ``pr_data.json`` entry, the shape the
        plan dashboard's ``build_dashboard.py`` reads (chip fields included)."""
        return {
            "state": self.state.value,
            "draft": self.draft,
            "merged_at": self.merged_at,
            "labels": list(self.labels),
            "ci": self.ci.value if self.ci else None,
            "additions": self.additions,
            "deletions": self.deletions,
            "mergeable": self.mergeable,
            "session_url": self.session_url,
        }


def board_document(states: list[PullRequestLiveState]) -> dict[str, Any]:
    """Serialize live states into the full ``board.json`` document.

    :param states: The pull requests to export.
    :return: The document ``load_board`` parses.
    """
    return {"pull_requests": [state.to_board_entry() for state in states]}


def pull_request_data_document(
    states: list[PullRequestLiveState], repository: str
) -> dict[str, Any]:
    """Serialize live states into the full ``pr_data.json`` document.

    :param states: The pull requests to export.
    :param repository: The ``owner/repository`` they belong to.
    :return: The document ``build_dashboard.py`` parses.
    """
    return {
        repository: {
            str(state.number): state.to_pull_request_data_entry() for state in states
        }
    }


# %% GitHub API transports


class GitHubAccessError(RuntimeError):
    """Raised when no route to the GitHub API is available."""


class GitHubApi(ABC):
    """A minimal read-only GitHub REST transport."""

    @abstractmethod
    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        """Perform one GET request against the GitHub REST API.

        :param path: The endpoint path, without a leading slash (e.g.
            ``repos/owner/repository/pulls``).
        :param parameters: Query parameters, if any.
        :return: The parsed JSON response.
        """


def _path_with_query(path: str, parameters: dict[str, str] | None) -> str:
    """:param path: The endpoint path.
    :param parameters: Query parameters, if any.
    :return: The path with the query string appended."""
    if not parameters:
        return path
    return f"{path}?{urllib.parse.urlencode(parameters)}"


@dataclass
class CommandGitHubApi(GitHubApi):
    """The GitHub CLI transport - authentication is whatever ``gh`` is logged in as."""

    executable: str = "gh"
    """The GitHub CLI executable to invoke."""

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        result = subprocess.run(
            [self.executable, "api", _path_with_query(path, parameters)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)


@dataclass
class TokenGitHubApi(GitHubApi):
    """The plain-HTTP transport, authenticating with a personal or installation
    token."""

    token: str
    """The bearer token sent with every request."""

    base_url: str = "https://api.github.com"
    """The API host requests are made against."""

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}/{_path_with_query(path, parameters)}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(request) as response:
            return json.load(response)


def resolve_github_api() -> GitHubApi:
    """Pick the available GitHub transport: the ``gh`` CLI when installed, else a
    ``GH_TOKEN``/``GITHUB_TOKEN`` environment token.

    :raises GitHubAccessError: When neither route is available.
    :return: The resolved transport.
    """
    if shutil.which("gh"):
        return CommandGitHubApi()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return TokenGitHubApi(token=token)
    raise GitHubAccessError(
        "No route to the GitHub API: neither the `gh` CLI is installed nor a "
        "GH_TOKEN/GITHUB_TOKEN environment variable is set."
    )


# %% fetch orchestration

PULL_REQUESTS_PER_PAGE = 100
"""The list-endpoint page size; a page shorter than this ends pagination."""


def _live_state_of_detail(
    detail: dict[str, Any], ci: CheckConclusion | None
) -> PullRequestLiveState:
    """:param detail: One pull request's detail payload (``GET .../pulls/{number}``).
    :param ci: The reduced check conclusion for its head commit.
    :return: The assembled live state."""
    return PullRequestLiveState(
        number=detail["number"],
        head=detail["head"]["ref"],
        base=detail["base"]["ref"],
        state=PullRequestState(detail["state"]),
        draft=bool(detail["draft"]),
        merged_at=detail.get("merged_at"),
        labels=[label["name"] for label in detail.get("labels", [])],
        ci=ci,
        additions=detail.get("additions"),
        deletions=detail.get("deletions"),
        mergeable=detail.get("mergeable"),
        session_url=parse_session_url(detail.get("body") or ""),
    )


def _discover_pull_request_numbers(
    repository: str, api: GitHubApi, state: str
) -> list[int]:
    """List every pull request number in a repository, paginating until a short page.

    :param repository: The ``owner/repository`` to list.
    :param api: The transport to use.
    :param state: The list filter: ``open``, ``closed``, or ``all``.
    :return: The discovered numbers.
    """
    numbers: list[int] = []
    page = 1
    while True:
        listed = api.get(
            f"repos/{repository}/pulls",
            {
                "state": state,
                "per_page": str(PULL_REQUESTS_PER_PAGE),
                "page": str(page),
            },
        )
        numbers.extend(entry["number"] for entry in listed)
        if len(listed) < PULL_REQUESTS_PER_PAGE:
            return numbers
        page += 1


def fetch_pull_request_states(
    repository: str,
    api: GitHubApi,
    numbers: list[int] | None = None,
    state: str = "open",
) -> list[PullRequestLiveState]:
    """Fetch the live state of a repository's pull requests.

    Each pull request costs one detail request (for the diff counts and the mergeable
    probe, which the list endpoint omits) plus one check-runs request for its head
    commit.

    :param repository: The ``owner/repository`` to fetch from.
    :param api: The transport to use.
    :param numbers: The specific pull requests wanted; ``None`` fetches every pull
        request the *state* filter lists.
    :param state: The discovery filter when *numbers* is ``None``.
    :return: One live state per pull request, in the order requested or discovered.
    """
    if numbers is None:
        numbers = _discover_pull_request_numbers(repository, api, state)
    states = []
    for number in numbers:
        detail = api.get(f"repos/{repository}/pulls/{number}")
        rollup = api.get(
            f"repos/{repository}/commits/{detail['head']['sha']}/check-runs"
        )
        states.append(
            _live_state_of_detail(detail, check_conclusion(rollup["check_runs"]))
        )
    return states


# %% local-git probes

SHORTSTAT_COUNT_PATTERN = re.compile(r"(\d+) (?:insertion|deletion)")
"""How ``git diff --shortstat`` reports its per-kind change counts."""


def lines_changed_between(
    base_reference: str, head_reference: str, repository_root: Path | None = None
) -> int | None:
    """Count the lines a branch changes versus a base, via local git.

    Uses the three-dot range, so only the head side's own changes count, not what the
    base gained since they diverged.

    :param base_reference: The base git reference.
    :param head_reference: The head git reference.
    :param repository_root: The repository to run in; the working directory if unset.
    :return: Additions plus deletions, or ``None`` when a reference doesn't resolve.
    """
    result = subprocess.run(
        ["git", "diff", "--shortstat", f"{base_reference}...{head_reference}"],
        capture_output=True,
        text=True,
        cwd=repository_root or Path.cwd(),
    )
    if result.returncode != 0:
        return None
    return sum(int(count) for count in SHORTSTAT_COUNT_PATTERN.findall(result.stdout))


def merge_conflicts_between(
    base_reference: str, head_reference: str, repository_root: Path | None = None
) -> bool | None:
    """Probe whether merging a branch onto a base would conflict right now, without
    mutating anything (``git merge-tree --write-tree``).

    :param base_reference: The base git reference.
    :param head_reference: The head git reference.
    :param repository_root: The repository to run in; the working directory if unset.
    :return: Whether the merge would conflict, or ``None`` when a reference doesn't
        resolve.

    ..note:: The reference check is explicit because ``merge-tree`` exits with the
        same code for "conflicts" and "not something we can merge" - the exit code
        alone cannot tell a conflict from a typo.
    """
    root = repository_root or Path.cwd()
    for reference in (base_reference, head_reference):
        verification = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{reference}^{{commit}}"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if verification.returncode != 0:
            return None
    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", base_reference, head_reference],
        capture_output=True,
        text=True,
        cwd=root,
    )
    return result.returncode != 0
