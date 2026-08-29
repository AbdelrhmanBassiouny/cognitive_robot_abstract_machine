"""
Reading and writing the fork's pull requests.

The reading and the writing halves are declared separately, so a caller that must not
write - the board export - can be handed a reader and provably cannot. Every write here
was probed against the live API first: a pull request's *base branch* is the one the
credential a session carries is refused, which is why retargeting is reported for a
caller to perform rather than performed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from maintenance_board import PullRequestRecord
from maintenance_constants import CREDENTIAL_VARIABLES, GITHUB_API_ROOT
from exceptions import ExternalCallFailed
from stack import Repository

CheckRunRecord = Mapping[str, Any]
"""
One check run as the REST API answers it, before any field is read.
"""

WorkflowRunRecord = Mapping[str, Any]
"""
One workflow run as the REST API answers it, before any field is read.
"""

DISPATCH_EVENT = "workflow_dispatch"
"""
How the API names a run that a dispatch started, which is the only kind read back here.

Spelled here rather than shared with :class:`workflow_document.TriggerEvent`, which names
the same word as a workflow's own trigger: that module reads YAML, and this one is on the
path a maintenance pass takes from a checkout where nothing has been installed.
"""


@dataclass
class GitHubCredentialUnavailableError(RuntimeError):
    """
    Raised when no token is available to authenticate the API calls with.
    """

    variables: tuple[str, ...]
    """The environment variables that were consulted."""

    def __str__(self) -> str:
        """:return: What was looked for, so the caller can supply it."""
        return (
            f"no GitHub token: set one of {', '.join(self.variables)}, or run this "
            f"with a caller that has one"
        )


# %% what a pass reads and writes


@dataclass(frozen=True)
class PullRequestReader(ABC):
    """
    Reading the pull-request state a pass derives from.

    Implementations inherit rather than merely match the shape, so one that omits a read
    is refused when it is constructed rather than when the missing call is first made.
    """

    @abstractmethod
    def open_pull_requests(self) -> list[PullRequestRecord]:
        """:return: Every open pull request on the fork."""

    @abstractmethod
    def pull_request(self, number: int) -> PullRequestRecord:
        """:param number: The pull request to read.
        :return: That pull request."""


@dataclass(frozen=True)
class PullRequestWriter(ABC):
    """
    The three writes a pass makes, each one probed against the live API first.

    Every one of them is available to the credential a session carries; a pull request's
    *base branch* is the single write that is not, which is why reparenting is the
    caller's job and none of this is.
    """

    @abstractmethod
    def replace_labels(self, number: int, labels: Sequence[str]) -> None:
        """:param number: The pull request to write.
        :param labels: The complete label set it must end up with."""

    @abstractmethod
    def add_comment(self, number: int, body: str) -> str:
        """:param number: The pull request to comment on.
        :param body: The comment.
        :return: The comment's URL."""

    @abstractmethod
    def set_description(self, number: int, body: str) -> None:
        """:param number: The pull request to write.
        :param body: The new description."""


@dataclass(frozen=True)
class CandidatePullRequests(ABC):
    """
    Opening a pull request only so a build gets a run, and reading what that run said.

    Declared apart from the reads and writes a maintenance pass makes, because nothing
    that maintains the stack does any of this: a candidate exists to be judged and closed
    unmerged, and a pass handed this interface could open one by mistake.
    """

    @abstractmethod
    def open_pull_request(self, title: str, head: str, base: str, body: str) -> int:
        """:param title: The pull request's title.
        :param head: The branch to be judged.
        :param base: The branch it is opened against.
        :param body: The description.
        :return: The new pull request's number."""

    @abstractmethod
    def close_pull_request(self, number: int) -> None:
        """:param number: The pull request to close without merging."""

    @abstractmethod
    def check_runs(self, reference: str) -> list[CheckRunRecord]:
        """:param reference: The commit or branch to read the checks of.
        :return: Every check run reported against it."""


class DispatchField(StrEnum):
    """
    What a dispatch request is keyed by, which is not what the workflow calls them.

    The reference is ``ref`` here where a run reports it as ``head_branch``, so the two
    are spelled where each is read rather than shared between them.
    """

    REFERENCE = "ref"
    """
    Which copy of the workflow file to run.
    """

    INPUTS = "inputs"
    """
    What to hand the run, keyed by the workflow's own input names.
    """


class HttpMethod(StrEnum):
    """
    The verbs this client calls the API with.
    """

    GET = "GET"
    """
    Read something.
    """

    POST = "POST"
    """
    Create something, or start something running.
    """

    PATCH = "PATCH"
    """
    Change part of something that already exists.
    """

    PUT = "PUT"
    """
    Replace something that already exists, whole.
    """


class ApiResource(StrEnum):
    """
    The addresses below a repository this client calls.

    Written once each, because several are addressed by more than one call: a pull
    request is read, described and closed, and a workflow is both dispatched and read
    back.
    """

    PULL_REQUESTS = "pulls"
    """
    Pull requests, whose labels and comments the API files under :attr:`ISSUES` instead.
    """

    ISSUES = "issues"
    """
    Where a pull request's labels and comments live.
    """

    COMMITS = "commits"
    """
    Commits, and what is reported against them.
    """

    WORKFLOWS = "actions/workflows"
    """
    Workflows, which are addressed by file name rather than by number.
    """

    LABELS = "labels"
    """
    The complete label set of one issue.
    """

    COMMENTS = "comments"
    """
    The comments on one issue.
    """

    CHECK_RUNS = "check-runs"
    """
    The checks reported against one commit.
    """

    DISPATCHES = "dispatches"
    """
    Where a run of one workflow is started.
    """

    RUNS = "runs"
    """
    The runs of one workflow.
    """


@dataclass(frozen=True)
class DispatchedWorkflowRuns(ABC):
    """
    Starting a workflow run, and reading how the ones already started turned out.

    Declared apart from both pull-request surfaces because nothing that maintains the
    stack or judges a candidate starts a run of its own: a localisation dispatches one
    per assembled tree and reads them back, and a caller handed only this cannot touch a
    pull request.
    """

    @abstractmethod
    def dispatch_workflow(
        self, workflow: str, reference: str, inputs: Mapping[str, str]
    ) -> None:
        """:param workflow: The workflow file to run.
        :param reference: The reference to run it on, which is the one whose copy of the
            workflow file runs.
        :param inputs: What to hand it."""

    @abstractmethod
    def workflow_runs(self, workflow: str) -> list[WorkflowRunRecord]:
        """:param workflow: The workflow file to read the runs of.
        :return: Its runs, newest first."""


@dataclass(frozen=True)
class ForkPullRequests(PullRequestReader, PullRequestWriter, ABC):
    """
    Everything a pass does to the fork's pull requests.

    A pass reads state and writes back to the same fork, so the two halves are named
    together wherever both are needed; the board export takes the reading half alone,
    which is what keeps an export from being able to write.
    """


@dataclass
class GitHubRequestFailed(ExternalCallFailed):
    """
    Raised when the API refuses a call this module depends on.
    """

    method: str = ""
    """
    The HTTP method used.
    """

    path: str = ""
    """
    The API path called, without the host.
    """

    @property
    def call(self) -> str:
        """:return: The request line, as issued."""
        return f"{self.method} {self.path}"


# %% the client that makes the calls


@dataclass(frozen=True)
class GitHubRepository(ForkPullRequests, CandidatePullRequests, DispatchedWorkflowRuns):
    """
    Every pull-request call this executor makes, against one repository.

    ``gh`` is absent from the environment this normally runs in, so the calls are plain
    authenticated requests rather than a CLI wrapper.
    """

    repository: Repository
    """
    The repository to read and write.
    """

    token: str
    """
    The credential the requests authenticate with.
    """

    page_size: int = 100
    """
    How many pull requests to ask for per request.
    """

    @classmethod
    def from_environment(cls, repository: Repository) -> GitHubRepository:
        """
        Build a client from whichever credential the environment carries.

        :param repository: The repository to read and write.
        :return: The client.
        :raises GitHubCredentialUnavailableError: If no token is set.
        """
        for variable in CREDENTIAL_VARIABLES:
            token = os.environ.get(variable)
            if token:
                return cls(repository, token)
        raise GitHubCredentialUnavailableError(CREDENTIAL_VARIABLES)

    @staticmethod
    def _collection(resource: ApiResource, *below: str | ApiResource) -> str:
        """
        :param resource: The collection to address.
        :param below: What to address below it, member first.
        :return: The path, below the repository.
        """
        return "/".join(("", str(resource), *(str(part) for part in below)))

    def _page(self, page: int, **criteria: str) -> str:
        """
        :param page: Which page to ask for, counting from one.
        :param criteria: What else to narrow the answer by.
        :return: The query asking for that page at this client's page size.
        """
        return urllib.parse.urlencode(
            {**criteria, "per_page": self.page_size, "page": page}
        )

    def open_pull_requests(self) -> list[PullRequestRecord]:
        """:return: Every open pull request on the repository, oldest page first."""
        collected: list[PullRequestRecord] = []
        page = 1
        while True:
            collection = self._collection(ApiResource.PULL_REQUESTS)
            fetched = self._call(
                HttpMethod.GET, f"{collection}?{self._page(page, state='open')}"
            )
            collected.extend(fetched)
            if len(fetched) < self.page_size:
                return collected
            page += 1

    def pull_request(self, number: int) -> PullRequestRecord:
        """:param number: The pull request to read.
        :return: That pull request."""
        return self._call(
            HttpMethod.GET, self._collection(ApiResource.PULL_REQUESTS, str(number))
        )

    def replace_labels(self, number: int, labels: Sequence[str]) -> None:
        """
        Write a pull request's complete label set.

        :param number: The pull request to write.
        :param labels: The complete set it must end up with, computed by
            :meth:`stack.LabelWrite.replacing` - this call replaces rather than adds.
        """
        self._call(
            HttpMethod.PUT,
            self._collection(ApiResource.ISSUES, str(number), ApiResource.LABELS),
            {"labels": list(labels)},
        )

    def add_comment(self, number: int, body: str) -> str:
        """:param number: The pull request to comment on.
        :param body: The comment.
        :return: The comment's URL."""
        created = self._call(
            HttpMethod.POST,
            self._collection(ApiResource.ISSUES, str(number), ApiResource.COMMENTS),
            {"body": body},
        )
        return str(created["html_url"])

    def set_description(self, number: int, body: str) -> None:
        """
        Rewrite a pull request's description and nothing else.

        :param number: The pull request to write.
        :param body: The new description.
        """
        self._call(
            HttpMethod.PATCH,
            self._collection(ApiResource.PULL_REQUESTS, str(number)),
            {"body": body},
        )

    def open_pull_request(self, title: str, head: str, base: str, body: str) -> int:
        """
        Open a pull request, so that something judges the branch it names.

        :param title: The pull request's title.
        :param head: The branch to be judged.
        :param base: The branch it is opened against.
        :param body: The description.
        :return: The new pull request's number.
        """
        opened = self._call(
            HttpMethod.POST,
            self._collection(ApiResource.PULL_REQUESTS),
            {"title": title, "head": head, "base": base, "body": body},
        )
        return int(opened["number"])

    def close_pull_request(self, number: int) -> None:
        """
        Close a pull request without merging it.

        :param number: The pull request to close.
        """
        self._call(
            HttpMethod.PATCH,
            self._collection(ApiResource.PULL_REQUESTS, str(number)),
            {"state": "closed"},
        )

    def check_runs(self, reference: str) -> list[CheckRunRecord]:
        """
        Read every check run reported against a commit or a branch.

        A branch answers with the checks on whatever it points at now, which is what
        lets a branch's own state be asked for without first resolving its head.

        :param reference: The commit or branch to read.
        :return: The check runs, which may be none while the first is still queueing.
        """
        collection = self._collection(
            ApiResource.COMMITS, reference, ApiResource.CHECK_RUNS
        )
        answered = self._call(HttpMethod.GET, f"{collection}?{self._page(1)}")
        return list(answered["check_runs"])

    def dispatch_workflow(
        self, workflow: str, reference: str, inputs: Mapping[str, str]
    ) -> None:
        """
        Start a run of one workflow.

        The reference decides which copy of the workflow file runs, so it is the one
        carrying the pipeline rather than the tree under test - what to run over is an
        input instead.

        :param workflow: The workflow file to run.
        :param reference: The reference to run it on.
        :param inputs: What to hand it.
        """
        self._call(
            HttpMethod.POST,
            self._collection(ApiResource.WORKFLOWS, workflow, ApiResource.DISPATCHES),
            {
                DispatchField.REFERENCE: reference,
                DispatchField.INPUTS: dict(inputs),
            },
        )

    def workflow_runs(self, workflow: str) -> list[WorkflowRunRecord]:
        """
        Read the runs of one workflow, newest first.

        Answered for the workflow rather than for a reference, because every run a
        localisation starts shares the reference it dispatched them on - what tells them
        apart is the name each carries.

        :param workflow: The workflow file to read the runs of.
        :return: Its runs.
        """
        collection = self._collection(ApiResource.WORKFLOWS, workflow, ApiResource.RUNS)
        query = self._page(1, event=DISPATCH_EVENT)
        answered = self._call(HttpMethod.GET, f"{collection}?{query}")
        return list(answered["workflow_runs"])

    def _call(
        self, method: HttpMethod, path: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        """
        Make one authenticated API call.

        :param method: The HTTP method.
        :param path: The path below the repository, starting with a slash.
        :param payload: The JSON body, absent for a read.
        :return: The decoded response, or ``None`` where there is no body - a dispatch
            is accepted with 204 and nothing to read.
        :raises GitHubRequestFailed: If the API answers with an error status.
        """
        request = urllib.request.Request(
            f"{GITHUB_API_ROOT}/repos/{self.repository}{path}",
            method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as refused:
            raise GitHubRequestFailed(
                status=refused.code,
                detail=refused.read().decode(errors="replace"),
                method=method,
                path=path,
            ) from refused
