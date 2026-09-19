#!/usr/bin/env python3
"""
Report the checks, failing job logs and review threads a fork's pull request has
collected upstream.

Thread resolved-state is only exposed by GitHub's GraphQL API, which is unreachable from
a Claude session, so this runs in the fork's own GitHub Actions runner and the session
reads its job log. ``gh`` is what talks to GitHub, rather than a hand-rolled client:
runners ship it and ``GITHUB_TOKEN`` authenticates it, so no access rule is implemented
here a fourth time.

Every repository name comes from configuration or the runner's own environment, so the
script works unchanged in any contributor's fork.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar, ClassVar

# ``stack.py`` is a single-file script rather than an installed package, so its
# directory joins the path the same way the test suites do it. Reusing its
# ``Repository`` keeps one parser for ``owner/name`` references.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stack"))

import tomllib  # noqa: E402
from stack import CONFIGURATION_PATH, Repository  # noqa: E402

QUERY_DIRECTORY = Path(__file__).resolve().parent / "queries"
"""
Where the ``.graphql`` documents live.
"""


# %% the reading contract


class JSONModel(ABC):
    """
    A dataclass mirroring one object GitHub returns, able to read itself from it.

    Declaring the reader here is what lets :meth:`PullRequestJSONKey.read_list` call
    it on any model. Without it the shared name would be a convention every model
    is trusted to have followed, and a model that spelled it differently would fail
    only when something happened to parse that field.

    ..note:: A reader needing more than the object itself cannot state this
        contract, so :class:`UpstreamPullRequestSnapshot`, which is assembled from
        threads gathered across several responses, does not implement it.
    """

    @classmethod
    @abstractmethod
    def from_json(cls, data: dict[str, Any]) -> JSONModel:
        """
        Read one of these out of the object GitHub returned.

        :param data: The object to read.
        :return: The parsed model.
        """


ParsedItem = TypeVar("ParsedItem", bound=JSONModel)
"""
Whatever model a list-valued field is being parsed into.
"""


# %% wire vocabulary


class PullRequestJSONKey(StrEnum):
    """
    Every field name this script reads out of a GraphQL response.

    Named once here so a key is never spelled twice, and so a rename in the query
    document has exactly one place to follow.
    """

    DATA = "data"
    ERRORS = "errors"
    MESSAGE = "message"
    REPOSITORY = "repository"
    PULL_REQUEST = "pullRequest"
    PULL_REQUESTS = "pullRequests"
    NODES = "nodes"
    PAGE_INFO = "pageInfo"
    HAS_NEXT_PAGE = "hasNextPage"
    END_CURSOR = "endCursor"
    IDENTIFIER = "id"
    IS_RESOLVED = "isResolved"
    IS_OUTDATED = "isOutdated"
    PATH = "path"
    LINE = "line"
    COMMENTS = "comments"
    DATABASE_IDENTIFIER = "databaseId"
    AUTHOR = "author"
    LOGIN = "login"
    BODY = "body"
    CREATED_AT = "createdAt"
    URL = "url"
    REVIEWS = "reviews"
    REVIEW_THREADS = "reviewThreads"
    STATE = "state"
    SUBMITTED_AT = "submittedAt"
    NUMBER = "number"
    TITLE = "title"
    HEAD_REPOSITORY_OWNER = "headRepositoryOwner"
    COMMITS = "commits"
    COMMIT = "commit"
    STATUS_CHECK_ROLLUP = "statusCheckRollup"
    CONTEXTS = "contexts"
    TYPE_NAME = "__typename"
    NAME = "name"
    CONCLUSION = "conclusion"
    DETAILS_URL = "detailsUrl"
    CONTEXT = "context"
    TARGET_URL = "targetUrl"
    QUERY = "query"
    VARIABLES = "variables"

    def read_list(
        self, data: dict[str, Any], model: type[ParsedItem]
    ) -> list[ParsedItem]:
        """
        Parse every entry of the list-valued field this key names.

        GitHub returns a list-valued field as an object holding the array under
        ``nodes`` rather than as the array itself, so that step happens here rather
        than at each call site.

        :param data: The object the field belongs to.
        :param model: The model to parse each entry into.
        :return: The parsed entries, in the order GitHub returned them.
        """
        entries = data[self][PullRequestJSONKey.NODES]
        return [model.from_json(entry) for entry in entries]


class QueryVariable(StrEnum):
    """
    The variables the query documents declare.
    """

    OWNER = "owner"
    NAME = "name"
    HEAD_REF_NAME = "headRefName"
    NUMBER = "number"
    THREAD_CURSOR = "threadCursor"


class GraphQLDocument(StrEnum):
    """
    The query documents, stored as ``.graphql`` files beside this script.
    """

    PULL_REQUEST_FOR_BRANCH = "pull_request_for_branch"
    REVIEW_THREADS_PAGE = "review_threads_page"

    def read(self) -> str:
        """:return: The document's text."""
        return (QUERY_DIRECTORY / f"{self}.graphql").read_text()


class EnvironmentVariable(StrEnum):
    """
    Runner-supplied environment this script reads.
    """

    STEP_SUMMARY = "GITHUB_STEP_SUMMARY"
    REPOSITORY_OWNER = "GITHUB_REPOSITORY_OWNER"


class ReviewState(StrEnum):
    """
    The verdict a reviewer submitted with a review.
    """

    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"

    @property
    def spoken(self) -> str:
        """:return: The verdict as it reads in a sentence."""
        return self.replace("_", " ").lower()


class PullRequestState(StrEnum):
    """
    The lifecycle state GitHub reports for a pull request.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MERGED = "MERGED"


class CheckContextType(StrEnum):
    """
    The two shapes GitHub returns inside a status check rollup.

    A pull request can carry both at once: Actions jobs arrive as check runs, while
    anything reporting through the older commit-status API arrives as a status
    context, and each spells its outcome with its own field.
    """

    CHECK_RUN = "CheckRun"
    STATUS_CONTEXT = "StatusContext"


class CheckOutcome(StrEnum):
    """
    Where one check stands, over both shapes a rollup can hold.

    A check run that has not finished reports no conclusion at all, which reads here
    as :attr:`PENDING` so an unfinished check is never mistaken for a passing one.
    """

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    NEUTRAL = "NEUTRAL"
    SKIPPED = "SKIPPED"
    STALE = "STALE"
    STARTUP_FAILURE = "STARTUP_FAILURE"
    PENDING = "PENDING"
    EXPECTED = "EXPECTED"

    @property
    def spoken(self) -> str:
        """:return: The outcome as it reads in a sentence."""
        return self.replace("_", " ").lower()


class RollupState(StrEnum):
    """
    The verdict GitHub itself computes over all of a pull request's checks.
    """

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ERROR = "ERROR"
    PENDING = "PENDING"
    EXPECTED = "EXPECTED"

    @property
    def spoken(self) -> str:
        """:return: The verdict as it reads in a sentence."""
        return self.lower()


class ThreadMarker(StrEnum):
    """
    The annotations a thread can carry in the report.
    """

    RESOLVED = "resolved"
    OUTDATED = "outdated"


# %% errors


@dataclass
class UpstreamReadError(Exception, ABC):
    """
    Base class for every failure this script raises.
    """

    def __post_init__(self) -> None:
        Exception.__init__(self, self.describe())

    @abstractmethod
    def describe(self) -> str:
        """:return: The message a caller should see."""


@dataclass
class GitHubCommandFailed(UpstreamReadError):
    """
    Raised when the ``gh`` invocation itself exits non-zero.
    """

    executable: str
    """
    The command that was run.
    """

    exit_code: int
    """
    The status it exited with.
    """

    error_output: str
    """
    Whatever it wrote to standard error.
    """

    def describe(self) -> str:
        """:return: The message a caller should see."""
        return f"{self.executable} exited {self.exit_code}: {self.error_output}"


@dataclass
class GraphQLErrorsReturned(UpstreamReadError):
    """
    Raised when GitHub answers with an ``errors`` array instead of data.
    """

    messages: list[str]
    """
    Every message GitHub reported.
    """

    def describe(self) -> str:
        """:return: The message a caller should see."""
        return "; ".join(self.messages)


@dataclass
class UpstreamPullRequestNotFound(UpstreamReadError):
    """
    Raised when a branch has no pull request open on the upstream.
    """

    branch: str
    """
    The fork branch that was looked up.
    """

    upstream: Repository
    """
    The repository that was searched.
    """

    fork_owner: str
    """
    The owner whose head branches were being claimed.
    """

    def describe(self) -> str:
        """:return: The message a caller should see."""
        return (
            f"no pull request on {self.upstream} has head "
            f"'{self.fork_owner}:{self.branch}' - the branch has most likely not "
            "been promoted upstream yet"
        )


# %% models mirroring the data


@dataclass(frozen=True)
class Author(JSONModel):
    """
    Whoever wrote a comment or submitted a review.
    """

    login: str
    """
    Their GitHub login, or a placeholder when the account is gone.
    """
    UNKNOWN_LOGIN: ClassVar[str] = "(unknown)"
    """
    Stands in for the author of a comment whose account no longer exists.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> Author:
        """
        Read an author, tolerating the null GitHub returns for deleted users.

        :param data: The ``author`` object, which GitHub may report as null.
        :return: The parsed author.
        """
        if data is None:
            return cls(cls.UNKNOWN_LOGIN)
        return cls(data[PullRequestJSONKey.LOGIN])


@dataclass(frozen=True)
class ThreadComment(JSONModel):
    """
    One comment inside a review thread.
    """

    database_identifier: int
    """
    GitHub's numeric identifier, the one that appears in comment permalinks.
    """

    author: Author
    """
    Whoever wrote the comment.
    """

    body: str
    """
    The comment text, exactly as written.
    """

    created_at: str
    """
    When the comment was posted, as an ISO 8601 timestamp.
    """

    url: str
    """
    The permalink to this comment.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ThreadComment:
        """
        Build a comment from one ``comments`` node.

        :param data: The node to read.
        :return: The parsed comment.
        """
        return cls(
            database_identifier=data[PullRequestJSONKey.DATABASE_IDENTIFIER],
            author=Author.from_json(data[PullRequestJSONKey.AUTHOR]),
            body=data[PullRequestJSONKey.BODY],
            created_at=data[PullRequestJSONKey.CREATED_AT],
            url=data[PullRequestJSONKey.URL],
        )


@dataclass(frozen=True)
class ReviewThread(JSONModel):
    """
    A conversation anchored to one location in the pull request's diff.
    """

    identifier: str
    """
    GitHub's node identifier for the thread.
    """

    is_resolved: bool
    """
    Whether a reviewer has marked the thread resolved.
    """

    is_outdated: bool
    """
    Whether the diff hunk the thread was anchored to has since changed.
    """

    path: str
    """
    The file the thread is attached to.
    """

    line: int | None
    """
    The line the thread is attached to, absent once the hunk is outdated.
    """

    comments: list[ThreadComment]
    """
    Every comment in the thread, oldest first.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReviewThread:
        """
        Build a thread from one ``reviewThreads`` node.

        :param data: The node to read.
        :return: The parsed thread.
        """
        return cls(
            identifier=data[PullRequestJSONKey.IDENTIFIER],
            is_resolved=data[PullRequestJSONKey.IS_RESOLVED],
            is_outdated=data[PullRequestJSONKey.IS_OUTDATED],
            path=data[PullRequestJSONKey.PATH],
            line=data[PullRequestJSONKey.LINE],
            comments=PullRequestJSONKey.COMMENTS.read_list(data, ThreadComment),
        )

    @property
    def location(self) -> str:
        """:return: The thread's ``path:line``, or just its path when it is outdated."""
        if self.line is None:
            return self.path
        return f"{self.path}:{self.line}"

    @property
    def markers(self) -> list[ThreadMarker]:
        """:return: The annotations this thread carries."""
        carried = []
        if self.is_resolved:
            carried.append(ThreadMarker.RESOLVED)
        if self.is_outdated:
            carried.append(ThreadMarker.OUTDATED)
        return carried


@dataclass(frozen=True)
class Review(JSONModel):
    """
    A submitted review, separate from the threads it may have opened.
    """

    author: Author
    """
    Whoever submitted the review.
    """

    state: ReviewState
    """
    The verdict the reviewer submitted.
    """

    body: str
    """
    The review's summary text, which is often empty.
    """

    submitted_at: str
    """
    When the review was submitted, as an ISO 8601 timestamp.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Review:
        """
        Build a review from one ``reviews`` node.

        :param data: The node to read.
        :return: The parsed review.
        """
        return cls(
            author=Author.from_json(data[PullRequestJSONKey.AUTHOR]),
            state=ReviewState(data[PullRequestJSONKey.STATE]),
            body=data[PullRequestJSONKey.BODY],
            submitted_at=data[PullRequestJSONKey.SUBMITTED_AT],
        )


@dataclass(frozen=True)
class BranchPullRequest(JSONModel):
    """
    One pull request found by searching the upstream for a head branch.
    """

    number: int
    """
    Its number on the upstream repository.
    """

    state: PullRequestState
    """
    Its lifecycle state.
    """

    head_owner: Author
    """
    The owner of the repository the head branch lives in.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BranchPullRequest:
        """
        Build a summary from one ``pullRequests`` node.

        :param data: The node to read.
        :return: The parsed summary.
        """
        return cls(
            number=data[PullRequestJSONKey.NUMBER],
            state=PullRequestState(data[PullRequestJSONKey.STATE]),
            head_owner=Author.from_json(data[PullRequestJSONKey.HEAD_REPOSITORY_OWNER]),
        )


@dataclass(frozen=True)
class ReviewThreadPage(JSONModel):
    """
    One page of review threads, with the cursor that follows it.
    """

    threads: list[ReviewThread]
    """
    The threads on this page.
    """

    has_next_page: bool
    """
    Whether another page follows.
    """

    end_cursor: str | None
    """
    The cursor to request that next page with.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReviewThreadPage:
        """
        Build a page from a ``pullRequest`` node.

        :param data: The node to read.
        :return: The parsed page.
        """
        threads_field = data[PullRequestJSONKey.REVIEW_THREADS]
        page_info = threads_field[PullRequestJSONKey.PAGE_INFO]
        return cls(
            threads=PullRequestJSONKey.REVIEW_THREADS.read_list(data, ReviewThread),
            has_next_page=page_info[PullRequestJSONKey.HAS_NEXT_PAGE],
            end_cursor=page_info[PullRequestJSONKey.END_CURSOR],
        )


@dataclass(frozen=True)
class CheckResult(JSONModel):
    """
    One check reported against the pull request's head commit.
    """

    name: str
    """
    What the check calls itself.
    """

    outcome: CheckOutcome
    """
    Where the check stands.
    """

    url: str
    """
    Where the check's own output is, empty when it reported none.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CheckResult:
        """
        Read one check out of a rollup context node.

        :param data: The node to read.
        :return: The parsed check.
        :raises ValueError: If the node is neither shape a rollup can hold.
        """
        if (
            CheckContextType(data[PullRequestJSONKey.TYPE_NAME])
            is CheckContextType.CHECK_RUN
        ):
            conclusion = data[PullRequestJSONKey.CONCLUSION]
            return cls(
                name=data[PullRequestJSONKey.NAME],
                outcome=(
                    CheckOutcome(conclusion) if conclusion else CheckOutcome.PENDING
                ),
                url=data[PullRequestJSONKey.DETAILS_URL] or "",
            )
        return cls(
            name=data[PullRequestJSONKey.CONTEXT],
            outcome=CheckOutcome(data[PullRequestJSONKey.STATE]),
            url=data[PullRequestJSONKey.TARGET_URL] or "",
        )

    @property
    def succeeded(self) -> bool:
        """:return: Whether this check reported success."""
        return self.outcome is CheckOutcome.SUCCESS


@dataclass(frozen=True)
class CheckStatus(JSONModel):
    """
    Every check reported against the pull request, with GitHub's verdict over them.
    """

    state: RollupState
    """
    The verdict GitHub computed over all of them.
    """

    results: list[CheckResult]
    """
    Every check, in the order GitHub returned them.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CheckStatus:
        """
        Read the rollup out of a ``statusCheckRollup`` object.

        :param data: The rollup to read.
        :return: The parsed status.
        """
        return cls(
            state=RollupState(data[PullRequestJSONKey.STATE]),
            results=PullRequestJSONKey.CONTEXTS.read_list(data, CheckResult),
        )

    @property
    def unsuccessful(self) -> list[CheckResult]:
        """:return: The checks that did not report success."""
        return [result for result in self.results if not result.succeeded]


@dataclass(frozen=True)
class UpstreamPullRequestSnapshot:
    """
    Everything read from one upstream pull request in a single run.
    """

    number: int
    """
    The pull request's number on the upstream repository.
    """

    title: str
    """
    The pull request's title.
    """

    url: str
    """
    The pull request's web URL.
    """

    reviews: list[Review]
    """
    Every submitted review, oldest first.
    """

    threads: list[ReviewThread]
    """
    Every review thread, in the order GitHub returned them.
    """

    checks: CheckStatus | None
    """
    The checks reported against the head commit, absent when none have reported.
    """

    @classmethod
    def from_json(
        cls, data: dict[str, Any], threads: list[ReviewThread]
    ) -> UpstreamPullRequestSnapshot:
        """
        Build a snapshot from a ``pullRequest`` node and its collected threads.

        :param data: The node to read.
        :param threads: Every thread gathered across the paged reads.
        :return: The parsed snapshot.
        """
        return cls(
            number=data[PullRequestJSONKey.NUMBER],
            title=data[PullRequestJSONKey.TITLE],
            url=data[PullRequestJSONKey.URL],
            reviews=PullRequestJSONKey.REVIEWS.read_list(data, Review),
            threads=threads,
            checks=cls._read_checks(data),
        )

    @staticmethod
    def _read_checks(data: dict[str, Any]) -> CheckStatus | None:
        """
        Read the checks reported against the pull request's head commit.

        GitHub hangs the rollup off the commit rather than the pull request, and
        leaves it null while nothing has reported against that commit.

        :param data: The ``pullRequest`` node to read.
        :return: The checks, or ``None`` when nothing has reported.
        """
        commits = data[PullRequestJSONKey.COMMITS][PullRequestJSONKey.NODES]
        if not commits:
            return None
        rollup = commits[-1][PullRequestJSONKey.COMMIT][
            PullRequestJSONKey.STATUS_CHECK_ROLLUP
        ]
        return CheckStatus.from_json(rollup) if rollup else None

    @property
    def unresolved_threads(self) -> list[ReviewThread]:
        """:return: The threads still awaiting action."""
        return [thread for thread in self.threads if not thread.is_resolved]

    def thread(self, identifier: str) -> ReviewThread:
        """
        Look one thread up by its node identifier.

        :param identifier: The thread's node identifier.
        :return: The matching thread.
        :raises KeyError: If no thread carries that identifier.
        """
        for thread in self.threads:
            if thread.identifier == identifier:
                return thread
        raise KeyError(identifier)


@dataclass(frozen=True)
class RepositoryJSON(JSONModel):
    """
    The ``repository`` object every query in this script selects.

    Owns the one access path from a response's data down to the nodes the models parse,
    so no caller spells that path out again.
    """

    data: dict[str, Any]
    """
    The repository object as returned.
    """

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> RepositoryJSON:
        """
        Read the repository out of a response's ``data``.

        :param data: The response's ``data`` object.
        :return: The wrapped repository.
        """
        return cls(data[PullRequestJSONKey.REPOSITORY])

    @property
    def pull_request(self) -> dict[str, Any]:
        """:return: The single ``pullRequest`` this response selected."""
        return self.data[PullRequestJSONKey.PULL_REQUEST]

    @property
    def review_thread_page(self) -> ReviewThreadPage:
        """:return: The pull request's page of review threads."""
        return ReviewThreadPage.from_json(self.pull_request)

    @property
    def pull_request_snapshot(self) -> UpstreamPullRequestSnapshot:
        """:return: The pull request's state, from this response alone.

        Only complete when the response carried every page of threads; a paged
        read assembles the snapshot itself from the threads it accumulated.
        """
        return UpstreamPullRequestSnapshot.from_json(
            self.pull_request, self.review_thread_page.threads
        )

    @property
    def branch_pull_requests(self) -> list[BranchPullRequest]:
        """:return: Every pull request the head-branch search matched."""
        return PullRequestJSONKey.PULL_REQUESTS.read_list(self.data, BranchPullRequest)


@dataclass(frozen=True)
class GraphQLResponse:
    """
    A parsed GraphQL response envelope.
    """

    data: dict[str, Any] | None
    """
    The ``data`` data, absent when the query failed outright.
    """

    errors: list[str] = field(default_factory=list)
    """
    Every message from an ``errors`` array, empty on success.
    """

    @classmethod
    def from_json(cls, text: str) -> GraphQLResponse:
        """
        Parse a response body.

        :param text: The raw JSON GitHub returned.
        :return: The parsed envelope.
        """
        body = json.loads(text)
        return cls(
            data=body.get(PullRequestJSONKey.DATA),
            errors=[
                error[PullRequestJSONKey.MESSAGE]
                for error in body.get(PullRequestJSONKey.ERRORS, [])
            ],
        )

    def result(self) -> dict[str, Any]:
        """:return: The query's result.

        :raises GraphQLErrorsReturned: If GitHub reported errors instead.
        """
        if self.errors:
            raise GraphQLErrorsReturned(self.errors)
        return self.data or {}


# %% the log behind a failed check


JOB_IDENTIFIER_GROUP = "identifier"
"""
What the job's number is called inside :data:`JOB_URL_PATTERN`.
"""

JOB_URL_PATTERN = re.compile(rf"/actions/runs/\d+/job/(?P<{JOB_IDENTIFIER_GROUP}>\d+)")
"""
Where a check's own output link carries the job that produced it.
"""

LOG_TIMESTAMP_PATTERN = re.compile(r"^\S+Z ")
"""
The timestamp a runner writes in front of every line it records.
"""

EXCERPT_LINE_LIMIT = 40
"""
How many lines of one job's log the report is willing to quote.
"""


class LogMarker(StrEnum):
    """
    The lines in a runner's log that say where a failure is described.
    """

    PYTEST_SUMMARY = "short test summary info"
    """
    Opens pytest's own list of what failed, which is the answer wherever there is one.
    """

    ERROR_ANNOTATION = "##[error]"
    """
    Marks a line the runner itself flagged, which is all a job that died before pytest
    leaves behind.
    """


@dataclass(frozen=True)
class FailedJob:
    """
    The Actions job behind a check that did not pass.
    """

    identifier: int
    """
    The job's own number, which is what a log read asks for.
    """

    @classmethod
    def behind(cls, result: CheckResult) -> FailedJob | None:
        """
        Find the job a check's output link points at.

        A rollup also carries contexts posted by services that are not Actions at all,
        and those link somewhere with no job behind them.

        :param result: The check to locate.
        :return: The job, or ``None`` where the link names none.
        """
        match = JOB_URL_PATTERN.search(result.url)
        if match is None:
            return None
        return cls(int(match.group(JOB_IDENTIFIER_GROUP)))


@dataclass(frozen=True)
class FailureLog:
    """
    The part of a failed job's log that says what went wrong.
    """

    check_name: str
    """
    The check whose job this came from.
    """

    lines: list[str]
    """
    The excerpt, oldest line first, with the runner's timestamps taken off.
    """

    @classmethod
    def excerpt(cls, check_name: str, log: str) -> FailureLog:
        """
        Cut one whole job log down to the lines worth reading.

        pytest's own summary is preferred where the job ran that far, the runner's error
        annotations where it did not, and the log's last lines where neither marker
        appears at all.

        :param check_name: The check the job reported for.
        :param log: The job log, exactly as the runner recorded it.
        :return: The excerpt.
        """
        lines = [LOG_TIMESTAMP_PATTERN.sub("", line) for line in log.splitlines()]
        summary = cls._from_marker(lines, LogMarker.PYTEST_SUMMARY)
        if summary:
            return cls(check_name, summary[:EXCERPT_LINE_LIMIT])
        annotations = [line for line in lines if LogMarker.ERROR_ANNOTATION in line]
        if annotations:
            return cls(check_name, annotations[:EXCERPT_LINE_LIMIT])
        return cls(check_name, lines[-EXCERPT_LINE_LIMIT:])

    @staticmethod
    def _from_marker(lines: list[str], marker: LogMarker) -> list[str]:
        """
        :param lines: The log's lines.
        :param marker: What opens the part worth keeping.
        :return: That line and everything after it, empty where it never appears.
        """
        for index, line in enumerate(lines):
            if marker in line:
                return lines[index:]
        return []


# %% client


class GitHubEndpoint(StrEnum):
    """
    The REST paths this script asks ``gh`` for.
    """

    JOB_LOG = "repos/{repository}/actions/jobs/{job}/logs"
    """
    One Actions job's whole recorded log.
    """


class JobLogReader(ABC):
    """
    Reads the log one Actions job recorded.
    """

    @abstractmethod
    def read_job_log(self, repository: Repository, job_identifier: int) -> str:
        """
        Read one job's whole log.

        :param repository: The repository the job ran in.
        :param job_identifier: The job to read.
        :return: The log, exactly as the runner recorded it.
        """


class GraphQLClient(ABC):
    """
    Sends a GraphQL document to GitHub and returns its ``data`` data.
    """

    @abstractmethod
    def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """
        Run one GraphQL query.

        :param query: The GraphQL document.
        :param variables: The document's variables.
        :return: The response's ``data`` data.
        """


@dataclass
class GitHubCommandLineClient(GraphQLClient, JobLogReader):
    """
    A client that shells out to ``gh api graphql``.

    The runner already ships ``gh`` and authenticates it from ``GITHUB_TOKEN``, so this
    holds no credential handling of its own.
    """

    executable: str = "gh"
    """
    The command to invoke, overridable for testing.
    """

    def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """
        Run one GraphQL query through ``gh``.

        :param query: The GraphQL document.
        :param variables: The document's variables.
        :return: The response's ``data`` data.
        :raises GitHubCommandFailed: If ``gh`` exits non-zero.
        :raises GraphQLErrorsReturned: If GitHub answers with errors.
        """
        request = json.dumps(
            {PullRequestJSONKey.QUERY: query, PullRequestJSONKey.VARIABLES: variables}
        )
        return GraphQLResponse.from_json(
            self._run(["api", "graphql", "--input", "-"], request)
        ).result()

    def read_job_log(self, repository: Repository, job_identifier: int) -> str:
        """
        Read one job's log through ``gh``.

        The upstream is a different repository from the one the runner is running in,
        which its token reads as anyone else does.

        :param repository: The repository the job ran in.
        :param job_identifier: The job to read.
        :return: The log, exactly as the runner recorded it.
        :raises GitHubCommandFailed: If ``gh`` exits non-zero.
        """
        return self._run(
            [
                "api",
                GitHubEndpoint.JOB_LOG.format(
                    repository=repository, job=job_identifier
                ),
            ]
        )

    def _run(self, arguments: list[str], standard_input: str | None = None) -> str:
        """
        Invoke ``gh`` once and hand back what it wrote.

        :param arguments: The arguments to pass.
        :param standard_input: What to write to its standard input, if anything.
        :return: Its standard output.
        :raises GitHubCommandFailed: If it exits non-zero.
        """
        completed = subprocess.run(
            [self.executable, *arguments],
            input=standard_input,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise GitHubCommandFailed(
                self.executable, completed.returncode, completed.stderr.strip()
            )
        return completed.stdout


# %% reading


@dataclass
class UpstreamPullRequestReader:
    """
    Reads one upstream pull request's checks and review state through a client.
    """

    client: GraphQLClient
    """
    How GraphQL queries reach GitHub.
    """

    upstream_repository: Repository
    """
    The repository the fork's pull requests are opened against.
    """

    fork_owner: str
    """
    The owner whose branches this reader will claim as its own.
    """

    @property
    def _repository_variables(self) -> dict[str, Any]:
        """:return: The owner and name every query in this script takes."""
        return {
            QueryVariable.OWNER: self.upstream_repository.owner,
            QueryVariable.NAME: self.upstream_repository.name,
        }

    def resolve_pull_request_number(self, branch: str) -> int:
        """
        Find the upstream pull request opened from *branch*.

        Prefers an open pull request, falling back to the most recent closed one so a
        branch under post-merge discussion still resolves.

        :param branch: The fork branch name.
        :return: The upstream pull request number.
        :raises UpstreamPullRequestNotFound: If the fork has no such pull request.
        """
        data = self.client.execute(
            GraphQLDocument.PULL_REQUEST_FOR_BRANCH.read(),
            {**self._repository_variables, QueryVariable.HEAD_REF_NAME: branch},
        )
        candidates = [
            pull_request
            for pull_request in RepositoryJSON.from_json(data).branch_pull_requests
            if pull_request.head_owner.login == self.fork_owner
        ]
        if not candidates:
            raise UpstreamPullRequestNotFound(
                branch, self.upstream_repository, self.fork_owner
            )
        open_candidates = [
            pull_request
            for pull_request in candidates
            if pull_request.state is PullRequestState.OPEN
        ]
        return (open_candidates or candidates)[0].number

    def read_current_state(
        self, pull_request_number: int
    ) -> UpstreamPullRequestSnapshot:
        """
        Read the checks, reviews and review threads on one upstream pull request.

        :param pull_request_number: The upstream pull request's number.
        :return: The assembled snapshot.
        """
        threads: list[ReviewThread] = []
        cursor: str | None = None
        repository = None
        while True:
            data = self.client.execute(
                GraphQLDocument.REVIEW_THREADS_PAGE.read(),
                {
                    **self._repository_variables,
                    QueryVariable.NUMBER: pull_request_number,
                    QueryVariable.THREAD_CURSOR: cursor,
                },
            )
            repository = RepositoryJSON.from_json(data)
            page = repository.review_thread_page
            threads.extend(page.threads)
            if not page.has_next_page:
                break
            cursor = page.end_cursor
        return UpstreamPullRequestSnapshot.from_json(repository.pull_request, threads)


@dataclass
class FailureLogReader:
    """
    Reads the log behind every check a pull request did not pass.
    """

    job_logs: JobLogReader
    """
    How one job's log is fetched.
    """

    upstream_repository: Repository
    """
    The repository whose jobs are read.
    """

    def read(self, checks: CheckStatus | None) -> list[FailureLog]:
        """
        Excerpt the log behind each check that failed.

        A check still running has no failure to describe, and one whose link names no
        job has no log to read, so both are left out rather than reported empty.

        :param checks: The head commit's checks, where it reported any.
        :return: One excerpt per failed check with a job behind it.
        """
        if checks is None:
            return []
        excerpts = []
        for result in checks.unsuccessful:
            if result.outcome is CheckOutcome.PENDING:
                continue
            job = FailedJob.behind(result)
            if job is None:
                continue
            excerpts.append(
                FailureLog.excerpt(
                    result.name,
                    self.job_logs.read_job_log(
                        self.upstream_repository, job.identifier
                    ),
                )
            )
        return excerpts


# %% configuration


def resolve_upstream_repository(
    path: Path = CONFIGURATION_PATH, override: str | None = None
) -> Repository:
    """
    Decide which repository the fork's pull requests are reviewed on.

    Reads the committed defaults only. The per-user layer lives on the personal-notes
    branch, which a runner does not check out, so *override* is the escape hatch for a
    checkout whose upstream differs.

    :param path: The committed stack configuration file.
    :param override: An ``owner/name`` reference outranking the file.
    :return: The upstream repository.
    """
    if override:
        return Repository.parse(override)
    values = tomllib.loads(path.read_text())
    return Repository.parse(values[UPSTREAM_REPOSITORY_SETTING])


UPSTREAM_REPOSITORY_SETTING = "upstream_repository"
"""
The ``stack.toml`` key naming the repository reviews happen on.
"""


# %% report


class ReportText(StrEnum):
    """
    The fixed lines the report states rather than computes.
    """

    CHECKS_HEADING = "## Checks"
    NO_CHECKS = "No checks have reported."
    FAILURE_LOGS_HEADING = "## The log behind each failed check"
    REVIEWS_HEADING = "## Reviews"
    NO_REVIEWS = "No reviews submitted."
    NO_UNRESOLVED_HEADING = "## No unresolved review threads"
    NOTHING_TO_ACT_ON = "Nothing to act on."


@dataclass
class UpstreamPullRequestReport:
    """
    Renders a pull request's current upstream state as the markdown a session or a phone
    reads.
    """

    snapshot: UpstreamPullRequestSnapshot
    """
    The upstream state to describe.
    """

    include_resolved: bool = False
    """
    Whether threads already marked resolved are shown too.
    """

    failure_logs: list[FailureLog] = field(default_factory=list)
    """
    The excerpts to quote under the checks, empty where none were read.
    """

    def render(self) -> str:
        """:return: The report as markdown."""
        lines = [
            f"# Upstream pull request: #{self.snapshot.number} {self.snapshot.title}",
            "",
            self.snapshot.url,
            "",
        ]
        lines.extend(self._render_checks())
        lines.extend(self._render_failure_logs())
        lines.extend(self._render_reviews())
        lines.extend(self._render_threads())
        return "\n".join(lines)

    def heading(self, shown_count: int) -> str:
        """
        Describe the set actually being listed, not just the unresolved one.

        :param shown_count: How many threads the section goes on to list.
        :return: The section heading.
        """
        unresolved_count = len(self.snapshot.unresolved_threads)
        if not unresolved_count:
            return ReportText.NO_UNRESOLVED_HEADING
        if self.include_resolved:
            return f"## {shown_count} review threads, {unresolved_count} unresolved"
        return f"## {unresolved_count} unresolved review threads"

    @property
    def shown_threads(self) -> list[ReviewThread]:
        """:return: The threads this report lists."""
        if self.include_resolved:
            return self.snapshot.threads
        return self.snapshot.unresolved_threads

    def _render_checks(self) -> list[str]:
        """:return: The checks section."""
        checks = self.snapshot.checks
        if checks is None:
            return [ReportText.CHECKS_HEADING, "", ReportText.NO_CHECKS, ""]
        unsuccessful = checks.unsuccessful
        succeeded = len(checks.results) - len(unsuccessful)
        lines = [
            f"{ReportText.CHECKS_HEADING}: {checks.state.spoken} "
            f"({succeeded}/{len(checks.results)} passed)",
            "",
        ]
        for result in unsuccessful:
            location = f" <{result.url}>" if result.url else ""
            lines.append(f"- **{result.name}** — {result.outcome.spoken}{location}")
        lines.append("")
        return lines

    def _render_failure_logs(self) -> list[str]:
        """:return: The quoted-log section, empty where nothing was read."""
        if not self.failure_logs:
            return []
        lines = [ReportText.FAILURE_LOGS_HEADING, ""]
        for failure in self.failure_logs:
            lines.extend([f"### {failure.check_name}", "", "```"])
            lines.extend(failure.lines)
            lines.extend(["```", ""])
        return lines

    def _render_reviews(self) -> list[str]:
        """:return: The submitted-reviews section."""
        if not self.snapshot.reviews:
            return [ReportText.REVIEWS_HEADING, "", ReportText.NO_REVIEWS, ""]
        lines = [ReportText.REVIEWS_HEADING, ""]
        for review in self.snapshot.reviews:
            lines.append(
                f"- **{review.author.login}** — {review.state.spoken} "
                f"({review.submitted_at})"
            )
            if review.body.strip():
                lines.append(f"  > {review.body.strip()}")
        lines.append("")
        return lines

    def _render_threads(self) -> list[str]:
        """:return: The review-threads section."""
        shown = self.shown_threads
        lines = [self.heading(len(shown)), ""]
        if not shown:
            lines.extend([ReportText.NOTHING_TO_ACT_ON, ""])
            return lines
        for thread in shown:
            lines.extend(self._render_thread(thread))
        return lines

    def _render_thread(self, thread: ReviewThread) -> list[str]:
        """
        Render one thread with every comment in it.

        :param thread: The thread to render.
        :return: The thread's markdown lines.
        """
        markers = thread.markers
        suffix = f" _({', '.join(markers)})_" if markers else ""
        lines = [f"### `{thread.location}`{suffix}", ""]
        for comment in thread.comments:
            lines.append(f"- **{comment.author.login}**: {comment.body.strip()}")
        if thread.comments:
            lines.extend(["", f"<{thread.comments[0].url}>", ""])
        return lines


# %% command line


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """
    Parse the command line.

    :param argv: The arguments to parse, defaulting to the process's own.
    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--pull-request", type=int, help="the upstream pull request number to read"
    )
    target.add_argument(
        "--branch", help="the fork branch whose upstream pull request to read"
    )
    parser.add_argument(
        "--fork-owner",
        default=os.environ.get(EnvironmentVariable.REPOSITORY_OWNER, ""),
        help="the owner whose branches to claim, defaulting to the runner's own",
    )
    parser.add_argument(
        "--upstream", help="an owner/name upstream outranking the configured one"
    )
    parser.add_argument(
        "--include-resolved",
        action="store_true",
        help="show threads already marked resolved as well",
    )
    parser.add_argument(
        "--failure-logs",
        action="store_true",
        help="quote the log behind each check that failed",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    Read one upstream pull request and print its report.

    A branch that was never promoted upstream is an ordinary answer rather than a crash,
    so this boundary turns the script's own errors into a stated reason. Anything else
    still propagates with its traceback intact.

    :param argv: The arguments to parse, defaulting to the process's own.
    :return: The process exit status.
    """
    arguments = _parse_arguments(argv)
    try:
        report = _build_report(arguments)
    except UpstreamReadError as failure:
        print(failure, file=sys.stderr)
        return 1
    print(report)
    summary_path = os.environ.get(EnvironmentVariable.STEP_SUMMARY)
    if summary_path:
        Path(summary_path).write_text(report)
    return 0


def _build_report(arguments: argparse.Namespace) -> str:
    """
    Read the requested pull request and render its report.

    :param arguments: The parsed command line.
    :return: The rendered markdown.
    """
    client = GitHubCommandLineClient()
    upstream = resolve_upstream_repository(override=arguments.upstream)
    reader = UpstreamPullRequestReader(client, upstream, arguments.fork_owner)
    number = arguments.pull_request or reader.resolve_pull_request_number(
        arguments.branch
    )
    snapshot = reader.read_current_state(number)
    failure_logs = (
        FailureLogReader(client, upstream).read(snapshot.checks)
        if arguments.failure_logs
        else []
    )
    return UpstreamPullRequestReport(
        snapshot,
        include_resolved=arguments.include_resolved,
        failure_logs=failure_logs,
    ).render()


if __name__ == "__main__":
    sys.exit(main())
