"""
Makes ``upstream_reviews`` importable as a plain module and loads the recorded GraphQL
responses the tests replay.

It is a single-file script run via ``python3 upstream_reviews.py ...``, not an
installed package - so its directory is added to ``sys.path`` here rather than
requiring an ``__init__.py``/packaging setup just for tests. Mirrors
``.claude/stack/tests/conftest.py`` and
``.claude/skills/plan-dashboard/tests/conftest.py``.
"""

import json
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest  # noqa: E402

from upstream_reviews import (  # noqa: E402
    GraphQLClient,
    JobLogReader,
    Repository,
    RepositoryJSON,
)

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"
"""
Where the recorded GraphQL responses live.
"""


class FixtureName(StrEnum):
    """
    The recorded responses the tests replay, named by their filename stem.
    """

    PULL_REQUEST_PAGE_ONE = "pull_request_page_one"
    PULL_REQUEST_PAGE_TWO = "pull_request_page_two"
    PULL_REQUEST_WITHOUT_CHECKS = "pull_request_without_checks"
    BRANCH_PULL_REQUESTS = "branch_pull_requests"
    BRANCH_PULL_REQUESTS_FOREIGN_OWNER = "branch_pull_requests_foreign_owner"
    BRANCH_PULL_REQUESTS_NONE = "branch_pull_requests_none"

    def load(self) -> dict[str, Any]:
        """:return: The recorded ``data`` object this fixture holds."""
        return json.loads((FIXTURE_DIRECTORY / f"{self}.json").read_text())

    def recorded(self) -> RepositoryJSON:
        """
        Read this fixture through the same model the production code uses.

        Lets a test reach recorded values as typed attributes rather than indexing the
        raw data at the call site.

        :return: The recorded repository.
        """
        return RepositoryJSON.from_json(self.load())


@dataclass(frozen=True)
class RecordedCall:
    """
    One query the reader executed, kept so a test can assert on it.
    """

    query: str
    """
    The GraphQL document that was sent.
    """

    variables: dict[str, Any]
    """
    The variables it was sent with.
    """


@dataclass
class ReplayingClient(GraphQLClient):
    """
    A client that returns queued responses instead of calling GitHub.

    Records every call it was given, so a test can assert the exact request the reader
    made.
    """

    responses: list[dict[str, Any]]
    """
    The responses still to be returned, in order.
    """

    calls: list[RecordedCall] = field(default_factory=list)
    """
    Every call the reader executed, oldest first.
    """

    def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """
        Return the next queued data.

        :param query: The GraphQL document, recorded for assertions.
        :param variables: The GraphQL variables, recorded for assertions.
        :return: The next queued data.
        """
        self.calls.append(RecordedCall(query, variables))
        return self.responses.pop(0)


@pytest.fixture
def paginated_client() -> ReplayingClient:
    """:return: A client replaying both pages of the recorded review threads."""
    return ReplayingClient(
        [
            FixtureName.PULL_REQUEST_PAGE_ONE.load(),
            FixtureName.PULL_REQUEST_PAGE_TWO.load(),
        ]
    )


class JobLogFixtureName(StrEnum):
    """
    The recorded job logs the tests read, named by their filename stem.
    """

    FAILED_JOB = "failed_job"
    FAILED_JOB_WITHOUT_SUMMARY = "failed_job_without_summary"

    def load(self) -> str:
        """:return: The recorded log this fixture holds, exactly as recorded."""
        return (FIXTURE_DIRECTORY / f"{self}.log").read_text()


@dataclass(frozen=True)
class RecordedJobLogCall:
    """
    One job log the reader asked for, kept so a test can assert on it.
    """

    repository: Repository
    """
    The repository it was asked of.
    """

    job_identifier: int
    """
    The job it named.
    """


@dataclass
class ReplayingJobLogReader(JobLogReader):
    """
    A log reader that answers from recorded logs instead of calling GitHub.

    Records every read, so a test can assert which job the reader went after and in
    which repository.
    """

    logs: dict[int, str] = field(default_factory=dict)
    """
    The log each job identifier answers with.
    """

    calls: list[RecordedJobLogCall] = field(default_factory=list)
    """
    Every read that was asked for, oldest first.
    """

    def read_job_log(self, repository: Repository, job_identifier: int) -> str:
        """
        Answer with the recorded log for *job_identifier*.

        :param repository: The repository, recorded for assertions.
        :param job_identifier: The job whose log to answer with.
        :return: The recorded log.
        """
        self.calls.append(RecordedJobLogCall(repository, job_identifier))
        return self.logs[job_identifier]
