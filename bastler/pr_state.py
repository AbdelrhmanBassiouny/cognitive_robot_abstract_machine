"""
One shared fetch/compute layer for live pull-request state.

Both of this repository's dashboard systems - the stacked-PR board (``stack.py``'s
``board.json``) and the plan dashboards (``build_dashboard.py``'s ``pr_data.json``) -
need the same facts about a pull request: its check conclusion, its size versus its base,
whether it would merge cleanly, and which Claude session is working it. This module
computes those facts once and serializes them into either consumer's document shape, so
neither system re-derives them.
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
from typing import Any, ClassVar

from bastler.maintenance_constants import GITHUB_API_ROOT, CredentialVariable

EXECUTABLE_SEARCH_PATH_VARIABLE = "PATH"
"""
The environment variable the GitHub CLI executable is looked up through.
"""

# %% the vocabulary of GitHub's payloads


class PullRequestField(StrEnum):
    """
    The keys of a pull request's REST payload this module reads.
    """

    NUMBER = "number"
    """
    The pull request number.
    """

    STATE = "state"
    """Open or closed - see :class:`PullRequestState`."""

    DRAFT = "draft"
    """
    Whether the pull request is a draft.
    """

    MERGED_AT = "merged_at"
    """
    GitHub's merge timestamp, ``null`` when never merged.
    """

    HEAD = "head"
    """
    The head side, a mapping carrying :attr:`BRANCH` and :attr:`COMMIT`.
    """

    BASE = "base"
    """
    The base side, a mapping carrying :attr:`BRANCH`.
    """

    BRANCH = "ref"
    """
    A side's branch name.
    """

    COMMIT = "sha"
    """
    A side's commit.
    """

    LABELS = "labels"
    """
    The labels, each a mapping carrying :attr:`LABEL_NAME`.
    """

    LABEL_NAME = "name"
    """
    One label's name.
    """

    BODY = "body"
    """
    The description, where a session link lives.
    """

    ADDITIONS = "additions"
    """
    Lines added versus the base.
    """

    DELETIONS = "deletions"
    """
    Lines deleted versus the base.
    """

    MERGEABLE = "mergeable"
    """
    GitHub's mergeability verdict, ``null`` while it is still being computed.
    """


class IssueField(StrEnum):
    """
    The keys of an issue's REST payload this module reads.
    """

    HTML_URL = "html_url"
    """
    The issue's page on GitHub.
    """


class CheckRunField(StrEnum):
    """
    The keys of a check-runs payload this module reads, in both the REST shape
    (``conclusion``/``status``) and the GraphQL rollup shape (``state``).
    """

    CHECK_RUNS = "check_runs"
    """
    The list of check runs on a commit.
    """

    CONCLUSION = "conclusion"
    """
    A finished check's outcome.
    """

    STATUS = "status"
    """
    An unfinished check's progress.
    """

    STATE = "state"
    """
    A check's state in the GraphQL rollup dialect.
    """


class CheckState(StrEnum):
    """
    The raw per-check states GitHub reports, in the upper case both dialects reduce to.
    """

    FAILURE = "FAILURE"
    """
    The check failed.
    """

    ERROR = "ERROR"
    """
    The check could not run to a verdict.
    """

    CANCELLED = "CANCELLED"
    """
    The check was cancelled.
    """

    TIMED_OUT = "TIMED_OUT"
    """
    The check ran out of time.
    """

    PENDING = "PENDING"
    """
    The check has not started.
    """

    IN_PROGRESS = "IN_PROGRESS"
    """
    The check is running.
    """

    QUEUED = "QUEUED"
    """
    The check is waiting for a runner.
    """

    UNKNOWN = ""
    """
    The payload carried no state at all, which a run still starting can do.
    """


class ListParameter(StrEnum):
    """
    The query parameters of the pull request list endpoint.
    """

    STATE = "state"
    """
    The :class:`PullRequestListFilter` to apply.
    """

    PER_PAGE = "per_page"
    """
    The page size.
    """

    PAGE = "page"
    """
    The page number, counted from one.
    """


class PullRequestListFilter(StrEnum):
    """
    Which pull requests the list endpoint returns.
    """

    OPEN = "open"
    """
    Only open ones.
    """

    CLOSED = "closed"
    """
    Only closed ones, merged or not.
    """

    ALL = "all"
    """
    Every pull request.
    """


class PullRequestState(StrEnum):
    """
    GitHub's coarse-grained pull request state.
    """

    OPEN = "open"
    """
    Still open, whether a draft or ready for review.
    """

    CLOSED = "closed"
    """Closed - merged or not, which only :attr:`PullRequestField.MERGED_AT` tells."""


class BoardEntryKey(StrEnum):
    """
    The keys of one ``board.json`` entry, the shape ``stack.py`` reads.
    """

    PULL_REQUESTS = "pull_requests"
    """
    The document's one top-level key, holding the entries.
    """

    NUMBER = "number"
    """
    The pull request number.
    """

    HEAD = "head"
    """
    The head branch name.
    """

    BASE = "base"
    """The base branch name - the parent in a stack."""

    DRAFT = "draft"
    """
    Whether the pull request is a draft.
    """

    LABELS = "labels"
    """
    The label names.
    """

    CI = "ci"
    """
    The reduced check conclusion, or ``null``.
    """

    SESSION = "session"
    """
    The Claude session URL, or ``null``.
    """


class PullRequestDataKey(StrEnum):
    """
    The keys of one ``pr_data.json`` entry, the shape ``build_dashboard.py`` reads.
    """

    STATE = "state"
    """
    Open or closed.
    """

    DRAFT = "draft"
    """
    Whether the pull request is a draft.
    """

    MERGED_AT = "merged_at"
    """GitHub's merge timestamp, ``null`` when never merged - required on a closed entry."""

    LABELS = "labels"
    """
    The label names.
    """

    CI = "ci"
    """
    The reduced check conclusion, or ``null``.
    """

    ADDITIONS = "additions"
    """
    Lines added versus the base.
    """

    DELETIONS = "deletions"
    """
    Lines deleted versus the base.
    """

    MERGEABLE = "mergeable"
    """
    GitHub's mergeability verdict.
    """

    SESSION_URL = "session_url"
    """
    The Claude session URL parsed from the description.
    """


# %% check rollup reduction


class CheckConclusion(StrEnum):
    """
    The single conclusion a pull request's whole check rollup reduces to.
    """

    SUCCESS = "success"
    """
    Every check completed successfully.
    """

    FAILURE = "failure"
    """
    At least one check failed, errored, was cancelled, or timed out.
    """

    PENDING = "pending"
    """
    No check failed, but at least one is still queued or running.
    """


@dataclass(frozen=True)
class CheckRollup:
    """
    The check runs on one head commit, reduced to a single conclusion.
    """

    checks: tuple[dict[str, Any], ...]
    """
    One mapping per check, as GitHub returned it.
    """

    FAILURE_STATES: ClassVar[frozenset[CheckState]] = frozenset(
        {
            CheckState.FAILURE,
            CheckState.ERROR,
            CheckState.CANCELLED,
            CheckState.TIMED_OUT,
        }
    )
    """
    The per-check states that make the whole rollup a failure.
    """

    PENDING_STATES: ClassVar[frozenset[CheckState]] = frozenset(
        {
            CheckState.PENDING,
            CheckState.IN_PROGRESS,
            CheckState.QUEUED,
            CheckState.UNKNOWN,
        }
    )
    """
    The per-check states that make a failure-free rollup pending.
    """

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CheckRollup:
        """
        :param payload: The check-runs endpoint's response for one commit.
        :return: The rollup it describes.
        """
        return cls(tuple(payload[CheckRunField.CHECK_RUNS]))

    @property
    def conclusion(self) -> CheckConclusion | None:
        """
        :return: The reduced conclusion, or ``None`` when no check has run at all.
        """
        if not self.checks:
            return None
        states = {self._state_of(check) for check in self.checks}
        if states & self.FAILURE_STATES:
            return CheckConclusion.FAILURE
        if states & self.PENDING_STATES:
            return CheckConclusion.PENDING
        return CheckConclusion.SUCCESS

    @staticmethod
    def _state_of(check: dict[str, Any]) -> str:
        """
        :param check: One check's mapping, in either payload dialect.
        :return: Its state, upper-cased so both dialects compare alike.
        """
        return str(
            check.get(CheckRunField.CONCLUSION)
            or check.get(CheckRunField.STATE)
            or check.get(CheckRunField.STATUS)
            or CheckState.UNKNOWN
        ).upper()


# %% session link


@dataclass(frozen=True)
class ClaudeSessionLink:
    """
    A link to the Claude session working a pull request, the way its description carries
    it.
    """

    session_identifier: str
    """
    What follows the fixed prefix in the URL.
    """

    URL_PREFIX: ClassVar[str] = "https://claude.ai/code/session_"
    """
    Every session URL starts with this.
    """

    PATTERN: ClassVar[re.Pattern[str]] = re.compile(re.escape(URL_PREFIX) + r"([\w-]+)")
    """
    Matches one session URL, capturing its identifier.
    """

    @property
    def url(self) -> str:
        """:return: The full session URL."""
        return f"{self.URL_PREFIX}{self.session_identifier}"

    @classmethod
    def first_in(cls, text: str) -> ClaudeSessionLink | None:
        """
        :param text: A pull request description.
        :return: The first session link in it, or ``None`` if there is none.
        """
        match = cls.PATTERN.search(text)
        return cls(match.group(1)) if match else None


# %% change size


@dataclass(frozen=True)
class ChangeSize:
    """
    How much a pull request changes versus its base, classified against the threshold
    under which a change counts as short.
    """

    additions: int
    """
    Lines added.
    """

    deletions: int
    """
    Lines deleted.
    """

    SHORT_CHANGE_THRESHOLD: ClassVar[int] = 400
    """
    The largest line count, additions plus deletions, that still counts as short.
    """

    @property
    def lines_changed(self) -> int:
        """:return: Additions plus deletions."""
        return self.additions + self.deletions

    @property
    def is_short(self) -> bool:
        """:return: Whether the change is within the short-change threshold."""
        return self.lines_changed <= self.SHORT_CHANGE_THRESHOLD


# %% live-state model


@dataclass
class PullRequestLiveState:
    """
    Everything both dashboard systems want to know about one live pull request.
    """

    number: int
    """
    The pull request number.
    """

    head: str
    """
    The head branch name.
    """

    base: str
    """The base branch name - the pull request's parent in a stack."""

    state: PullRequestState
    """
    Whether the pull request is open or closed.
    """

    draft: bool
    """
    Whether the pull request is currently a draft.
    """

    merged_at: str | None
    """
    GitHub's merge timestamp, or ``None`` if it never recorded a merge.
    """

    labels: list[str] = field(default_factory=list)
    """
    The labels currently on the pull request.
    """

    ci: CheckConclusion | None = None
    """
    The reduced check conclusion on the head commit, or ``None`` when no check ran.
    """

    additions: int | None = None
    """
    Lines added versus the base, or ``None`` when not fetched.
    """

    deletions: int | None = None
    """
    Lines deleted versus the base, or ``None`` when not fetched.
    """

    mergeable: bool | None = None
    """
    Whether GitHub reports the pull request as cleanly mergeable onto its base -
    ``None`` while GitHub is still computing it or when not fetched.
    """

    session_url: str | None = None
    """
    The Claude session URL parsed from the pull request body, if any.
    """

    @property
    def change_size(self) -> ChangeSize | None:
        """:return: The change size, or ``None`` when either line count is unknown."""
        if self.additions is None or self.deletions is None:
            return None
        return ChangeSize(self.additions, self.deletions)

    @classmethod
    def from_detail(
        cls, detail: dict[str, Any], rollup: CheckRollup
    ) -> PullRequestLiveState:
        """
        :param detail: One pull request's detail payload.
        :param rollup: The check rollup of its head commit.
        :return: The assembled live state.
        """
        session = ClaudeSessionLink.first_in(detail.get(PullRequestField.BODY) or "")
        return cls(
            number=detail[PullRequestField.NUMBER],
            head=detail[PullRequestField.HEAD][PullRequestField.BRANCH],
            base=detail[PullRequestField.BASE][PullRequestField.BRANCH],
            state=PullRequestState(detail[PullRequestField.STATE]),
            draft=bool(detail[PullRequestField.DRAFT]),
            merged_at=detail.get(PullRequestField.MERGED_AT),
            labels=[
                label[PullRequestField.LABEL_NAME]
                for label in detail.get(PullRequestField.LABELS, [])
            ],
            ci=rollup.conclusion,
            additions=detail.get(PullRequestField.ADDITIONS),
            deletions=detail.get(PullRequestField.DELETIONS),
            mergeable=detail.get(PullRequestField.MERGEABLE),
            session_url=session.url if session else None,
        )

    def to_board_entry(self) -> dict[str, Any]:
        """:return: This pull request as one ``board.json`` entry."""
        return {
            BoardEntryKey.NUMBER: self.number,
            BoardEntryKey.HEAD: self.head,
            BoardEntryKey.BASE: self.base,
            BoardEntryKey.DRAFT: self.draft,
            BoardEntryKey.LABELS: list(self.labels),
            BoardEntryKey.CI: self.ci.value if self.ci else None,
            BoardEntryKey.SESSION: self.session_url,
        }

    def to_pull_request_data_entry(self) -> dict[str, Any]:
        """:return: This pull request as one ``pr_data.json`` entry, chip fields
        included."""
        return {
            PullRequestDataKey.STATE: self.state.value,
            PullRequestDataKey.DRAFT: self.draft,
            PullRequestDataKey.MERGED_AT: self.merged_at,
            PullRequestDataKey.LABELS: list(self.labels),
            PullRequestDataKey.CI: self.ci.value if self.ci else None,
            PullRequestDataKey.ADDITIONS: self.additions,
            PullRequestDataKey.DELETIONS: self.deletions,
            PullRequestDataKey.MERGEABLE: self.mergeable,
            PullRequestDataKey.SESSION_URL: self.session_url,
        }


@dataclass(frozen=True)
class PullRequestExport:
    """
    The live states of one repository's pull requests, in either consumer's document
    shape.
    """

    repository: str
    """
    The ``owner/repository`` the states belong to.
    """

    states: list[PullRequestLiveState]
    """
    The pull requests to export.
    """

    def to_board_document(self) -> dict[str, Any]:
        """:return: The ``board.json`` document ``stack.py`` parses."""
        return {
            BoardEntryKey.PULL_REQUESTS: [
                state.to_board_entry() for state in self.states
            ]
        }

    def to_pull_request_data_document(self) -> dict[str, Any]:
        """:return: The ``pr_data.json`` document ``build_dashboard.py`` parses."""
        return {
            self.repository: {
                str(state.number): state.to_pull_request_data_entry()
                for state in self.states
            }
        }


# %% GitHub API transports


class GitHubAccessError(RuntimeError):
    """
    Raised when no route to the GitHub API is available.
    """


@dataclass(frozen=True)
class RepositoryEndpoints:
    """
    The REST paths this module reads for one repository.
    """

    repository: str
    """
    The ``owner/repository`` the paths address.
    """

    @property
    def pull_requests(self) -> str:
        """:return: The pull request list endpoint."""
        return f"repos/{self.repository}/pulls"

    def pull_request(self, number: int) -> str:
        """
        :param number: A pull request number.
        :return: That pull request's detail endpoint.
        """
        return f"{self.pull_requests}/{number}"

    def check_runs(self, commit: str) -> str:
        """
        :param commit: A commit.
        :return: That commit's check-runs endpoint.
        """
        return f"repos/{self.repository}/commits/{commit}/check-runs"

    def issue(self, number: int) -> str:
        """
        :param number: An issue number - a pull request number resolves here too.
        :return: That issue's endpoint.
        """
        return f"repos/{self.repository}/issues/{number}"


class RequestHeader(StrEnum):
    """
    The request headers the token transport sends.
    """

    AUTHORIZATION = "Authorization"
    """
    Carries the bearer token.
    """

    ACCEPT = "Accept"
    """
    Names the media type asked for.
    """


class GitHubApi(ABC):
    """
    A minimal read-only GitHub REST transport.
    """

    @abstractmethod
    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        """
        Perform one GET request against the GitHub REST API.

        :param path: The endpoint path, without a leading slash.
        :param parameters: Query parameters, if any.
        :return: The parsed JSON response.
        """

    @staticmethod
    def path_with_query(path: str, parameters: dict[str, str] | None) -> str:
        """
        :param path: The endpoint path.
        :param parameters: Query parameters, if any.
        :return: The path with the query string appended.
        """
        if not parameters:
            return path
        return f"{path}?{urllib.parse.urlencode(parameters)}"

    @classmethod
    def resolve(cls) -> GitHubApi:
        """
        Pick the available transport: the GitHub CLI when installed, else a token from
        the environment.

        :raises GitHubAccessError: When neither route is available.
        :return: The resolved transport.
        """
        if shutil.which(CommandGitHubApi.EXECUTABLE):
            return CommandGitHubApi()
        for variable in CredentialVariable:
            token = os.environ.get(variable)
            if token:
                return TokenGitHubApi(token=token)
        variables = "/".join(CredentialVariable)
        raise GitHubAccessError(
            f"No route to the GitHub API: neither the `{CommandGitHubApi.EXECUTABLE}` "
            f"CLI is installed nor a {variables} environment variable is set."
        )


@dataclass(frozen=True)
class CommandGitHubApi(GitHubApi):
    """
    The GitHub CLI transport - authentication is whatever the CLI is logged in as.
    """

    EXECUTABLE: ClassVar[str] = "gh"
    """
    The GitHub CLI executable.
    """
    API_SUBCOMMAND: ClassVar[str] = "api"
    """
    The CLI subcommand that performs a raw REST request.
    """

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        result = subprocess.run(
            [
                self.EXECUTABLE,
                self.API_SUBCOMMAND,
                self.path_with_query(path, parameters),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)


@dataclass(frozen=True)
class TokenGitHubApi(GitHubApi):
    """
    The plain-HTTP transport, authenticating with a personal or installation token.
    """

    token: str
    """
    The bearer token sent with every request.
    """
    base_url: str = GITHUB_API_ROOT
    """
    The API host requests are made against.
    """
    ACCEPTED_MEDIA_TYPE: ClassVar[str] = "application/vnd.github+json"
    """
    The response media type asked for.
    """

    def get(self, path: str, parameters: dict[str, str] | None = None) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}/{self.path_with_query(path, parameters)}",
            headers={
                RequestHeader.AUTHORIZATION: f"Bearer {self.token}",
                RequestHeader.ACCEPT: self.ACCEPTED_MEDIA_TYPE,
            },
        )
        with urllib.request.urlopen(request) as response:
            return json.load(response)


# %% fetch orchestration


@dataclass(frozen=True)
class PullRequestFetcher:
    """
    Fetches the live state of one repository's pull requests through a transport.

    Each pull request costs one detail request - for the line counts and the mergeable
    verdict, which the list endpoint omits - plus one check-runs request for its head.
    """

    repository: str
    """
    The ``owner/repository`` to fetch from.
    """
    api: GitHubApi
    """
    The transport to fetch through.
    """
    PAGE_SIZE: ClassVar[int] = 100
    """
    The list-endpoint page size; a page shorter than this ends pagination.
    """

    @property
    def endpoints(self) -> RepositoryEndpoints:
        """:return: The repository's endpoints."""
        return RepositoryEndpoints(self.repository)

    def fetch(
        self,
        numbers: list[int] | None = None,
        listing: PullRequestListFilter = PullRequestListFilter.OPEN,
    ) -> list[PullRequestLiveState]:
        """
        :param numbers: The specific pull requests wanted; ``None`` fetches every pull
            request *listing* returns.
        :param listing: The discovery filter when *numbers* is ``None``.
        :return: One live state per pull request, in the order requested or discovered.
        """
        if numbers is None:
            numbers = self._discover_numbers(listing)
        return [self.fetch_one(number) for number in numbers]

    def fetch_one(self, number: int) -> PullRequestLiveState:
        """
        :param number: The pull request to fetch.
        :return: Its live state.
        """
        detail = self.api.get(self.endpoints.pull_request(number))
        head_commit = detail[PullRequestField.HEAD][PullRequestField.COMMIT]
        rollup = CheckRollup.from_payload(
            self.api.get(self.endpoints.check_runs(head_commit))
        )
        return PullRequestLiveState.from_detail(detail, rollup)

    def _discover_numbers(self, listing: PullRequestListFilter) -> list[int]:
        """
        List every pull request number *listing* covers, paginating until a short page.

        :param listing: The list filter.
        :return: The discovered numbers.
        """
        numbers: list[int] = []
        page = 1
        while True:
            listed = self.api.get(
                self.endpoints.pull_requests,
                {
                    ListParameter.STATE: listing,
                    ListParameter.PER_PAGE: str(self.PAGE_SIZE),
                    ListParameter.PAGE: str(page),
                },
            )
            numbers.extend(entry[PullRequestField.NUMBER] for entry in listed)
            if len(listed) < self.PAGE_SIZE:
                return numbers
            page += 1


# %% local-git probes


@dataclass(frozen=True)
class LocalGitProbe:
    """
    The facts about two references a checkout can answer without the network: how many
    lines one changes versus the other, and whether merging them would conflict.
    """

    repository_root: Path
    """
    The checkout to run git in.
    """
    SHORTSTAT_COUNT_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(\d+) (?:insertion|deletion)"
    )
    """
    How ``git diff --shortstat`` reports its per-kind change counts.
    """

    def lines_changed_between(
        self, base_reference: str, head_reference: str
    ) -> int | None:
        """
        Count the lines the head changes versus the base, over the three-dot range so
        only the head side's own changes count.

        :param base_reference: The base git reference.
        :param head_reference: The head git reference.
        :return: Additions plus deletions, or ``None`` when a reference does not
            resolve.
        """
        result = self._run(
            "diff", "--shortstat", f"{base_reference}...{head_reference}"
        )
        if result.returncode != 0:
            return None
        return sum(
            int(count) for count in self.SHORTSTAT_COUNT_PATTERN.findall(result.stdout)
        )

    def merge_conflicts_between(
        self, base_reference: str, head_reference: str
    ) -> bool | None:
        """
        Probe whether merging the head onto the base would conflict right now, without
        changing anything.

        :param base_reference: The base git reference.
        :param head_reference: The head git reference.
        :return: Whether the merge would conflict, or ``None`` when a reference does not
            resolve.

        ..note:: The references are verified first because ``merge-tree`` exits with
            the same status for a conflict and for a reference it cannot merge, so the
            status alone cannot tell a conflict from a typo.
        """
        if not all(
            self._resolves(reference) for reference in (base_reference, head_reference)
        ):
            return None
        result = self._run("merge-tree", "--write-tree", base_reference, head_reference)
        return result.returncode != 0

    def _resolves(self, reference: str) -> bool:
        """
        :param reference: A git reference.
        :return: Whether it names a commit in this checkout.
        """
        return (
            self._run(
                "rev-parse", "--verify", "--quiet", f"{reference}^{{commit}}"
            ).returncode
            == 0
        )

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """
        :param arguments: The git subcommand and its arguments.
        :return: The finished command, output captured, not checked.
        """
        return subprocess.run(
            ["git", *arguments],
            capture_output=True,
            text=True,
            cwd=self.repository_root,
        )
