"""
Where each call this client makes is addressed.

Nothing here reaches the network: what is pinned is the verb and the path, because a
wrong one is a 404 at the far end of a runner rather than a failure anything local sees.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

from maintenance_github import ApiResource, GitHubRepository, HttpMethod
from stack import Repository

A_REPOSITORY = Repository(owner="an-owner", name="a-project")
"""
The repository every call below is made against.
"""

A_PULL_REQUEST = 7
"""
The pull request the calls that take one are made about.
"""

A_WORKFLOW = "integration-probe.yml"
"""
The workflow the calls that take one are made about.
"""

A_PAGE_SIZE = 3
"""
How many to ask for per page, deliberately not the default: a read that spells a size of
its own rather than asking the client's would otherwise be addressed identically.
"""


# %% what a call is, and what it must be addressed to


@dataclass(frozen=True)
class RecordedCall:
    """
    One call, as the client asked for it.
    """

    method: HttpMethod
    """
    The verb it was made with.
    """

    path: str
    """
    The path below the repository it was addressed to.
    """


@dataclass(frozen=True)
class ApiCall:
    """
    One call this client makes, and the address the API documents for it.
    """

    make: Callable[[GitHubRepository], None]
    """
    How to make it.
    """

    method: HttpMethod
    """
    The verb it must be made with.
    """

    path: str
    """
    The path it must be addressed to.
    """

    answer: Any = None
    """
    What the API would answer, for the readers that read one.
    """


# %% making every call without reaching the network


@dataclass
class RecordingClient:
    """
    A client that records where a call would go rather than making it.
    """

    answer: Any = None
    """
    What to hand back to the method under test.
    """

    calls: list[RecordedCall] = field(default_factory=list)
    """
    Every call made through it, in order.
    """

    def record(self, method: HttpMethod, path: str, payload: Any = None) -> Any:
        """
        :param method: The verb the client called with.
        :param path: The path it addressed.
        :param payload: The body it sent, which addressing does not depend on.
        :return: The answer this recorder was built with.
        """
        self.calls.append(RecordedCall(method=method, path=path))
        return self.answer


API_CALLS = {
    "open_pull_requests": ApiCall(
        make=lambda client: client.open_pull_requests(),
        method=HttpMethod.GET,
        path=f"/pulls?state=open&per_page={A_PAGE_SIZE}&page=1",
        answer=[],
    ),
    "pull_request": ApiCall(
        make=lambda client: client.pull_request(A_PULL_REQUEST),
        method=HttpMethod.GET,
        path=f"/pulls/{A_PULL_REQUEST}",
    ),
    "replace_labels": ApiCall(
        make=lambda client: client.replace_labels(A_PULL_REQUEST, ["a-label"]),
        method=HttpMethod.PUT,
        path=f"/issues/{A_PULL_REQUEST}/labels",
    ),
    "add_comment": ApiCall(
        make=lambda client: client.add_comment(A_PULL_REQUEST, "a comment"),
        method=HttpMethod.POST,
        path=f"/issues/{A_PULL_REQUEST}/comments",
        answer={"html_url": "a-url"},
    ),
    "set_description": ApiCall(
        make=lambda client: client.set_description(A_PULL_REQUEST, "a description"),
        method=HttpMethod.PATCH,
        path=f"/pulls/{A_PULL_REQUEST}",
    ),
    "open_pull_request": ApiCall(
        make=lambda client: client.open_pull_request("a title", "a-head", "a-base", ""),
        method=HttpMethod.POST,
        path="/pulls",
        answer={"number": A_PULL_REQUEST},
    ),
    "close_pull_request": ApiCall(
        make=lambda client: client.close_pull_request(A_PULL_REQUEST),
        method=HttpMethod.PATCH,
        path=f"/pulls/{A_PULL_REQUEST}",
    ),
    "check_runs": ApiCall(
        make=lambda client: client.check_runs("a-commit"),
        method=HttpMethod.GET,
        path=f"/commits/a-commit/check-runs?per_page={A_PAGE_SIZE}&page=1",
        answer={"check_runs": []},
    ),
    "dispatch_workflow": ApiCall(
        make=lambda client: client.dispatch_workflow(A_WORKFLOW, "a-reference", {}),
        method=HttpMethod.POST,
        path=f"/actions/workflows/{A_WORKFLOW}/dispatches",
    ),
    "workflow_runs": ApiCall(
        make=lambda client: client.workflow_runs(A_WORKFLOW),
        method=HttpMethod.GET,
        path=(
            f"/actions/workflows/{A_WORKFLOW}/runs"
            f"?event=workflow_dispatch&per_page={A_PAGE_SIZE}&page=1"
        ),
        answer={"workflow_runs": []},
    ),
}
"""
Every call this client makes, keyed by the method that makes it.
"""


def calls_made(call: ApiCall, monkeypatch: pytest.MonkeyPatch) -> list[RecordedCall]:
    """
    :param call: The call to make.
    :param monkeypatch: How the request is intercepted.
    :return: What the client asked for, in order.
    """
    recording = RecordingClient(answer=call.answer)
    monkeypatch.setattr(
        GitHubRepository, "_call", lambda _, *made: recording.record(*made)
    )
    call.make(
        GitHubRepository(
            repository=A_REPOSITORY, token="a-token", page_size=A_PAGE_SIZE
        )
    )
    return recording.calls


@pytest.mark.parametrize("name", sorted(API_CALLS))
def test_every_call_is_addressed_where_the_api_documents_it(
    name: str, monkeypatch: pytest.MonkeyPatch
):
    """
    A path is composed rather than written out, so this is what says the composition
    still produces the address GitHub answers to.
    """
    call = API_CALLS[name]

    made = calls_made(call, monkeypatch)

    assert made == [RecordedCall(method=call.method, path=call.path)]


def test_every_call_this_client_makes_is_one_this_pins():
    """
    A call added without an address here would be unaddressed by anything that fails.
    """
    public = {
        name
        for name in vars(GitHubRepository)
        if not name.startswith("_") and callable(getattr(GitHubRepository, name))
    } - {"from_environment"}

    assert public == set(API_CALLS)
