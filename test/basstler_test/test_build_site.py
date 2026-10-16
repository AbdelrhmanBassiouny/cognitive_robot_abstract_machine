"""
Tests for build_site.py's static site of every plan dashboard.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

from basstler.build_dashboard import Plan, PullRequestRecord, PullRequestState
from basstler.build_site import (
    GitHubPullRequestSource,
    PlanSite,
    PlanSource,
    PullRequestReference,
    PullRequestSource,
    SiteFile,
    pull_request_record_from_api,
)
from basstler.maintenance_github import GitHubRepository, GitHubRequestFailed
from basstler.plan_model import ItemStatus
from basstler.repository import Repository

from .constants import DatasetLocation

SITE_URL = "https://owner.github.io/site/"
"""
The address the site under test is served from.
"""

# %% recorded pull request state


@dataclass
class RecordedPullRequestSource(PullRequestSource):
    """
    Pull request state answered from a fixed record, noting every lookup made.
    """

    records: dict[PullRequestReference, PullRequestRecord] = field(default_factory=dict)
    """
    The pull requests that exist, by reference.
    """

    issue_urls: dict[tuple[str, int], str] = field(default_factory=dict)
    """
    The issue pages that exist, by repository and number.
    """

    looked_up: list[PullRequestReference] = field(default_factory=list)
    """
    Every pull request asked for, in order.
    """

    def pull_request(self, reference: PullRequestReference) -> PullRequestRecord | None:
        self.looked_up.append(reference)
        return self.records.get(reference)

    def issue_url(self, repository: str, number: int) -> str | None:
        return self.issue_urls.get((repository, number))


MERGED_PULL_REQUEST = PullRequestReference("owner/repo", 1)
"""
The first plan's merged item's pull request.
"""

OPEN_PULL_REQUEST = PullRequestReference("owner/repo", 2)
"""
The first plan's open item's pull request.
"""

ELSEWHERE_PULL_REQUEST = PullRequestReference("other/repo", 7)
"""
The first plan's pull request on a repository other than the plan's default.
"""


@pytest.fixture
def pull_request_source() -> RecordedPullRequestSource:
    """
    The live state of the first plan's pull requests, all but one of which exist.
    """
    return RecordedPullRequestSource(
        records={
            MERGED_PULL_REQUEST: PullRequestRecord(
                state=PullRequestState.CLOSED, merged_at=None, labels=["merged"]
            ),
            OPEN_PULL_REQUEST: PullRequestRecord(
                state=PullRequestState.OPEN, draft=True
            ),
        },
        issue_urls={("owner/repo", 5): "https://github.com/owner/repo/issues/5"},
    )


@pytest.fixture
def site(pull_request_source: RecordedPullRequestSource) -> PlanSite:
    """
    A site over the dataset's plans directory.
    """
    return PlanSite(
        plans_directory=DatasetLocation.SITE_PLANS.value,
        site_url=SITE_URL,
        pull_request_source=pull_request_source,
    )


# %% the plans the notes branch carries


def test_every_plan_in_reads_only_directories_that_carry_a_manifest():
    sources = PlanSource.every_plan_in(DatasetLocation.SITE_PLANS.value)
    assert [source.directory_name for source in sources] == [
        "broken-plan",
        "first-plan",
        "second-plan",
    ]


def test_from_directory_reads_the_roadmap():
    directory = DatasetLocation.SITE_PLANS / "first-plan"
    source = PlanSource.from_directory(directory)
    assert source.roadmap_text == (directory / SiteFile.ROADMAP).read_text()


def test_from_directory_without_a_roadmap_reads_it_as_empty(tmp_path: Path):
    manifest = DatasetLocation.SITE_PLANS / "second-plan" / SiteFile.MANIFEST
    (tmp_path / SiteFile.MANIFEST).write_text(manifest.read_text())
    assert PlanSource.from_directory(tmp_path).roadmap_text == ""


# %% building the site


def test_build_writes_the_index_and_a_page_per_valid_plan(
    site: PlanSite, tmp_path: Path
):
    site.build(tmp_path)
    written = sorted(
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert written == [
        SiteFile.NO_JEKYLL,
        SiteFile.PAGE,
        f"{SiteFile.PLANS}/first-plan/{SiteFile.PAGE}",
        f"{SiteFile.PLANS}/second-plan/{SiteFile.PAGE}",
    ]


def test_build_leaves_out_a_plan_whose_manifest_fails_validation(
    site: PlanSite, tmp_path: Path
):
    summaries = site.build(tmp_path)
    assert [summary.id for summary in summaries] == ["first-plan", "second-plan"]


def test_build_links_each_plan_to_its_page_on_the_site(site: PlanSite, tmp_path: Path):
    summaries = site.build(tmp_path)
    index = (tmp_path / SiteFile.PAGE).read_text()
    for summary in summaries:
        assert summary.dashboard_url == site.plan_url(summary.id)
        assert f'href="{summary.dashboard_url}"' in index


def test_plan_url_joins_the_site_address_whether_or_not_it_ends_in_a_slash(
    pull_request_source: RecordedPullRequestSource,
):
    with_slash = PlanSite(Path(), SITE_URL, pull_request_source)
    without_slash = PlanSite(Path(), SITE_URL.rstrip("/"), pull_request_source)
    assert with_slash.plan_url("a") == without_slash.plan_url("a")
    assert with_slash.plan_url("a") == f"{SITE_URL}{SiteFile.PLANS}/a/"


def test_build_counts_done_items_from_the_manifest(site: PlanSite, tmp_path: Path):
    first_plan = next(
        summary for summary in site.build(tmp_path) if summary.id == "first-plan"
    )
    manifest = PlanSource.from_directory(
        DatasetLocation.SITE_PLANS / "first-plan"
    ).manifest
    statuses = [ItemStatus(item["status"]) for item in manifest["items"]]
    assert first_plan.done == statuses.count(ItemStatus.DONE)
    assert first_plan.total == len(statuses)


def test_build_looks_up_every_referenced_pull_request_in_its_own_repository(
    site: PlanSite, pull_request_source: RecordedPullRequestSource, tmp_path: Path
):
    site.build(tmp_path)
    assert pull_request_source.looked_up == [
        MERGED_PULL_REQUEST,
        OPEN_PULL_REQUEST,
        ELSEWHERE_PULL_REQUEST,
    ]


def test_pull_requests_of_leaves_out_a_number_the_repository_does_not_have(
    site: PlanSite, pull_request_source: RecordedPullRequestSource
):
    source = PlanSource.from_directory(DatasetLocation.SITE_PLANS / "first-plan")
    pull_requests = site.pull_requests_of(Plan.from_mapping(source.manifest))
    assert pull_requests == {
        MERGED_PULL_REQUEST.repository: {
            str(reference.number): pull_request_source.records[reference]
            for reference in (MERGED_PULL_REQUEST, OPEN_PULL_REQUEST)
        }
    }


def test_build_links_the_tracking_issue_on_the_plan_page(
    site: PlanSite, pull_request_source: RecordedPullRequestSource, tmp_path: Path
):
    site.build(tmp_path)
    page = (tmp_path / SiteFile.PLANS / "first-plan" / SiteFile.PAGE).read_text()
    assert pull_request_source.issue_urls[("owner/repo", 5)] in page


# %% reading pull requests from the GitHub API


def api_pull_request(number: int, **overrides: Any) -> dict[str, Any]:
    """
    Build one pull request object shaped like the pulls API's.

    :param number: The pull request's number.
    :param overrides: Fields to replace.
    """
    record = {
        "number": number,
        "state": "open",
        "draft": False,
        "merged_at": None,
        "labels": [],
        "html_url": f"https://github.com/owner/repo/pull/{number}",
    }
    record.update(overrides)
    return record


def test_pull_request_record_from_api_reads_label_names():
    record = pull_request_record_from_api(
        api_pull_request(1, labels=[{"name": "bug"}, {"name": "merged"}])
    )
    assert record.labels == ["bug", "merged"]


def test_pull_request_record_from_api_reads_a_merge():
    merged_at = "2026-10-01T12:00:00+00:00"
    record = pull_request_record_from_api(
        api_pull_request(1, state="closed", merged_at=merged_at)
    )
    assert record.was_merged
    assert record.merged_at.isoformat() == merged_at


@dataclass(frozen=True)
class RecordedRepository(GitHubRepository):
    """
    A repository client answering from recorded responses, keyed by request path.
    """

    responses: Mapping[str, Any] = field(default_factory=dict)
    """
    The decoded response to each ``GET`` path; any other path answers not found.
    """

    def _call(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        if path not in self.responses:
            raise GitHubRequestFailed(
                status=HTTPStatus.NOT_FOUND, detail="", method=method, path=path
            )
        return self.responses[path]


@dataclass
class RecordedGitHubPullRequestSource(GitHubPullRequestSource):
    """
    The GitHub source, with its client answering from recorded responses.
    """

    responses: Mapping[str, Any] = field(default_factory=dict)
    """
    What every repository's client answers, by request path.
    """

    def client_for(self, repository: str) -> GitHubRepository:
        return RecordedRepository(
            Repository.parse(repository), self.token, responses=self.responses
        )


LISTING_PATH = "/pulls?state=all&per_page=100&page=1"
"""
The path the first page of every pull request is listed from.
"""


def test_github_source_answers_a_listed_pull_request_from_the_listing():
    source = RecordedGitHubPullRequestSource(
        token="token", responses={LISTING_PATH: [api_pull_request(1, draft=True)]}
    )
    record = source.pull_request(PullRequestReference("owner/repo", 1))
    assert record == pull_request_record_from_api(api_pull_request(1, draft=True))


def test_github_source_reads_an_unlisted_pull_request_on_its_own():
    source = RecordedGitHubPullRequestSource(
        token="token",
        responses={LISTING_PATH: [], "/pulls/9": api_pull_request(9, draft=True)},
    )
    record = source.pull_request(PullRequestReference("owner/repo", 9))
    assert record == pull_request_record_from_api(api_pull_request(9, draft=True))


def test_github_source_answers_none_for_a_pull_request_that_does_not_exist():
    source = RecordedGitHubPullRequestSource(
        token="token", responses={LISTING_PATH: []}
    )
    assert source.pull_request(PullRequestReference("owner/repo", 404)) is None


def test_github_source_reads_an_issue_url():
    issue_url = "https://github.com/owner/repo/issues/5"
    source = RecordedGitHubPullRequestSource(
        token="token", responses={"/issues/5": {"html_url": issue_url}}
    )
    assert source.issue_url("owner/repo", 5) == issue_url


@dataclass(frozen=True)
class RefusingRepository(GitHubRepository):
    """
    A repository client whose every call is refused as forbidden.
    """

    def _call(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        raise GitHubRequestFailed(
            status=HTTPStatus.FORBIDDEN, detail="", method=method, path=path
        )


@dataclass
class RefusingGitHubPullRequestSource(GitHubPullRequestSource):
    """
    The GitHub source, with every call refused.
    """

    def client_for(self, repository: str) -> GitHubRepository:
        return RefusingRepository(Repository.parse(repository), self.token)


def test_github_source_reraises_a_refusal_other_than_not_found():
    with pytest.raises(GitHubRequestFailed) as refused:
        RefusingGitHubPullRequestSource(token="token").issue_url("owner/repo", 5)
    assert refused.value.status == HTTPStatus.FORBIDDEN
