"""
Tests for the headless static-site build: discovering plans from a personal-notes.

remote, fetching their pull request data through an injected GitHub transport, driving
one dashboard refresh per plan, and rendering the master index - the pipeline a Pages
workflow runs with no live session.

The notes remote is a scratch bare repository, the GitHub side is an in-memory fake, and
the per-plan refresh is a recorded stub - ``refresh_dashboard.sh``'s own behaviour is
covered by its own test module, not re-tested here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest
import yaml

from bastler.build_dashboard import Plan, validate_plan
from bastler.build_index import PlanSummary
from bastler.build_site import (
    PlanBuildResult,
    RefreshArgument,
    SiteBuilder,
    SiteBuildReport,
    SitePath,
)
from bastler.plan_item_bootstrap import HookScript, PlanDocument
from bastler.pr_state import (
    CheckConclusion,
    ClaudeSessionLink,
    IssueField,
    PullRequestDataKey,
    PullRequestState,
    RepositoryEndpoints,
)

from .constants import DATASET_DIRECTORY, STUBS_DIRECTORY
from .pull_request_payloads import (
    PullRequestDetailPayload,
    RecordedFakeGitHubApi,
    check_runs_payload,
)
from .scratch_repository import ScratchRepository

SITE_BUILD_PLAN = DATASET_DIRECTORY / "site-build-plan.yaml"
"""
The one plan the scratch notes branch carries.
"""

STUB_REFRESH_DASHBOARD_SCRIPT = STUBS_DIRECTORY / "refresh_dashboard_stub.sh"
"""
Stands in for ``refresh_dashboard.sh``: records its arguments, keeps the pull request
data it was handed, writes a placeholder page and prints a fixed summary.
"""

STUB_DASHBOARD_PAGE = "<html>stub dashboard</html>"
"""
The page the stub writes.
"""

SITE_BASE_URL = "https://example.github.io/site"
"""
Where the built site is to be published.
"""

TRACKING_ISSUE_URL = "https://github.com/owner/repository/issues/9"
"""
What the fake transport reports as the tracking issue's page.
"""

PULL_REQUEST = PullRequestDetailPayload(
    number=1,
    head="a-branch",
    draft=True,
    session=ClaudeSessionLink("01"),
    additions=10,
    deletions=2,
    mergeable=True,
)
"""
The one pull request the plan's item references.
"""


class RefreshStubVariable(StrEnum):
    """
    The knobs the refresh stub reads.
    """

    ARGUMENTS_FILE = "REFRESH_DASHBOARD_STUB_ARGUMENTS_FILE"
    """
    File every invocation's arguments are appended to.
    """

    PULL_REQUEST_DATA_COPY = "REFRESH_DASHBOARD_STUB_PULL_REQUEST_DATA_COPY"
    """
    Where the stub copies the pull request data file it was handed.
    """


@pytest.fixture
def plan() -> Plan:
    """
    The dataset plan, parsed the way the build parses it.
    """
    mapping = yaml.safe_load(SITE_BUILD_PLAN.read_text())
    validate_plan(mapping)
    return Plan.from_mapping(mapping)


@pytest.fixture
def project_with_one_plan(
    scratch_repository: ScratchRepository, scrubbed_environment, plan: Plan
) -> Path:
    """
    A scratch clone whose notes remote carries the dataset plan.
    """
    scratch_repository.install_hook_scripts(HookScript.CONFIGURATION)
    scratch_repository.resolve_notes_remote_to()
    scratch_repository.publish_notes_branch(
        {
            PlanDocument.MANIFEST.path_within_notes_branch(
                plan.id
            ): SITE_BUILD_PLAN.read_text(),
            PlanDocument.ROADMAP.path_within_notes_branch(plan.id): "# Roadmap\n",
        }
    )
    return scratch_repository.project_root


def make_api(plan: Plan) -> RecordedFakeGitHubApi:
    """
    :param plan: The plan whose references the transport must serve.
    :return: A transport serving its tracking issue and its one pull request.
    """
    endpoints = RepositoryEndpoints(plan.default_repository)
    return RecordedFakeGitHubApi(
        {
            endpoints.issue(plan.tracking_issue): {
                IssueField.HTML_URL: TRACKING_ISSUE_URL
            },
            endpoints.pull_request(PULL_REQUEST.number): PULL_REQUEST.to_json(),
            endpoints.check_runs(PULL_REQUEST.head_commit): check_runs_payload(
                CheckConclusion.SUCCESS
            ),
        }
    )


@dataclass(frozen=True)
class BuiltSite:
    """
    One full build, with the refresh stub's recordings beside the outputs.
    """

    summaries: list[PlanSummary]
    """
    What the build returned.
    """

    output_directory: Path
    """
    Where the site was written.
    """

    arguments_file: Path
    """
    The refresh stub's recorded invocations.
    """

    pull_request_data_copy: Path
    """
    The pull request data the refresh stub was handed.
    """


@pytest.fixture
def built_site(project_with_one_plan, plan, tmp_path, monkeypatch) -> BuiltSite:
    """
    The site built against the scratch plan.
    """
    arguments_file = tmp_path / "refresh-arguments"
    pull_request_data_copy = tmp_path / "pr-data-copy.json"
    monkeypatch.setenv(RefreshStubVariable.ARGUMENTS_FILE, str(arguments_file))
    monkeypatch.setenv(
        RefreshStubVariable.PULL_REQUEST_DATA_COPY, str(pull_request_data_copy)
    )
    output_directory = tmp_path / "_site"

    summaries = SiteBuilder(
        output_directory=output_directory,
        site_base_url=SITE_BASE_URL,
        api=make_api(plan),
        repository_root=project_with_one_plan,
        refresh_dashboard_script=STUB_REFRESH_DASHBOARD_SCRIPT,
    ).build()
    return BuiltSite(
        summaries, output_directory, arguments_file, pull_request_data_copy
    )


# %% site structure


def test_the_build_writes_one_dashboard_page_per_plan(built_site, plan):
    dashboard_page = (
        built_site.output_directory
        / SitePath.PLANS_DIRECTORY
        / plan.id
        / SitePath.INDEX_PAGE
    )
    assert dashboard_page.read_text() == STUB_DASHBOARD_PAGE


def test_the_build_writes_the_master_index(built_site, plan):
    index_page = (built_site.output_directory / SitePath.INDEX_PAGE).read_text()
    assert plan.title in index_page
    assert built_site.summaries[0].dashboard_url in index_page


def test_the_build_returns_one_summary_per_plan(built_site, plan):
    assert len(built_site.summaries) == 1
    summary = built_site.summaries[0]
    assert summary.id == plan.id
    assert summary.title == plan.title
    assert summary.done == 2
    assert summary.total == 3
    assert (
        summary.dashboard_url
        == f"{SITE_BASE_URL}/{SitePath.PLANS_DIRECTORY}/{plan.id}/"
    )


# %% what the per-plan refresh was handed


def test_the_refresh_runs_once_per_plan_with_its_identity_and_tracking_url(
    built_site, plan
):
    recorded_runs = built_site.arguments_file.read_text().splitlines()
    assert len(recorded_runs) == 1
    assert f"{RefreshArgument.PLAN_ID} {plan.id}" in recorded_runs[0]
    assert f"{RefreshArgument.TRACKING_URL} {TRACKING_ISSUE_URL}" in recorded_runs[0]


def test_the_refresh_is_handed_pull_request_data_with_the_chip_fields(built_site, plan):
    data = json.loads(built_site.pull_request_data_copy.read_text())
    entry = data[plan.default_repository][str(PULL_REQUEST.number)]
    assert entry[PullRequestDataKey.STATE] == PullRequestState.OPEN
    assert entry[PullRequestDataKey.DRAFT] is PULL_REQUEST.draft
    assert entry[PullRequestDataKey.CI] == CheckConclusion.SUCCESS
    assert entry[PullRequestDataKey.ADDITIONS] == PULL_REQUEST.additions
    assert entry[PullRequestDataKey.DELETIONS] == PULL_REQUEST.deletions
    assert entry[PullRequestDataKey.MERGEABLE] is PULL_REQUEST.mergeable
    assert entry[PullRequestDataKey.SESSION_URL] == PULL_REQUEST.session.url


# %% the printed report


def test_the_report_round_trips_through_json(built_site):
    report = SiteBuildReport.from_summaries(built_site.summaries)
    assert SiteBuildReport.from_json(report.to_json()) == report
    assert report.plans == [
        PlanBuildResult.from_summary(summary) for summary in built_site.summaries
    ]
