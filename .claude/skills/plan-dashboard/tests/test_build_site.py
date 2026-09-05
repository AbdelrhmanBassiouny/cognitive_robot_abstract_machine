"""
Tests for the headless static-site build: discovering the plans on a notes branch,
fetching their pull request data through an injected transport, driving one dashboard
refresh per plan, and rendering the master index over the results.

The notes remote is a scratch bare repository, the GitHub side is a fake, and the
per-plan refresh is a recorded stub - ``refresh_dashboard.sh``'s own behaviour has its
own test module and is not re-tested here.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from build_dashboard import PullRequestState
from build_site import (
    DashboardRefreshError,
    RefreshArgument,
    RefreshDashboardCommand,
    SiteBuilder,
    SitePath,
)
from github_api import (
    GitHubApi,
    IssueField,
    PullRequestField,
    PullRequestListParameter,
    RepositoryEndpoints,
)
from personal_notes import PersonalNotesBranch, PlanDocument
from pull_request_detail import PullRequestDetail
from scratch_repositories import PlanFiles
from site_fixtures import (
    RECORDED_ARGUMENTS_FILENAME,
    UNREFERENCED_PULL_REQUEST,
    RecordedArgumentKey,
    SitePlanId,
    SiteStub,
)

SITE_BASE_URL = "https://owner.github.io/repository"
OUTPUT_DIRECTORY_NAME = "_site"

REPOSITORY = SitePlanId.FIRST.plan.default_repository
"""
The repository both fixture plans reference, read off one of them rather than restated:

the build's own reuse of a single listing depends on their agreeing.
"""

ENDPOINTS = RepositoryEndpoints(REPOSITORY)
"""
The endpoints the fake transport answers on.
"""

TRACKING_ISSUE_URL = (
    f"https://github.com/{REPOSITORY}/issues/{SitePlanId.FIRST.plan.tracking_issue}"
)

REFERENCED_PULL_REQUEST = SitePlanId.FIRST.referenced_item.pull_request_number


@dataclass
class PlanDataFakeApi(GitHubApi):
    """
    Serves the tracking issue and the pull requests the seeded plans are checked
    against - one they reference and one they do not.
    """

    def get(self, path: str, parameters: Mapping[str, str] | None = None) -> Any:
        if path == ENDPOINTS.issue(SitePlanId.FIRST.plan.tracking_issue):
            return {IssueField.URL.value: TRACKING_ISSUE_URL}
        if parameters[PullRequestListParameter.PAGE] != "1":
            return []
        return [
            PullRequestDetail(REFERENCED_PULL_REQUEST, draft=True).to_json(),
            PullRequestDetail(UNREFERENCED_PULL_REQUEST).to_json(),
        ]


@pytest.fixture
def two_plans() -> dict:
    """
    Both fixture plans, read off disk to seed a scratch notes branch with.

    :return: The plans, keyed by identifier.
    """
    return {
        str(plan_id): PlanFiles(
            manifest=plan_id.document(PlanDocument.MANIFEST),
            roadmap=plan_id.document(PlanDocument.ROADMAP),
        )
        for plan_id in SitePlanId
    }


@pytest.fixture
def build_site(notes_clone, two_plans, tmp_path: Path):
    """
    Build a site builder wired to a scratch clone, the fake transport and a stub
    refresh.

    :param notes_clone: The scratch notes remote.
    :param two_plans: The plans to seed.
    :param tmp_path: pytest's per-test temporary directory.
    :return: The builder factory, called with the refresh script to drive.
    """
    clone = notes_clone.seed(two_plans)

    def build(stub: SiteStub = SiteStub.REFRESH_DASHBOARD) -> SiteBuilder:
        return SiteBuilder(
            output_directory=tmp_path / OUTPUT_DIRECTORY_NAME,
            site_base_url=SITE_BASE_URL,
            api=PlanDataFakeApi(),
            notes=PersonalNotesBranch.resolve(clone),
            refresh_dashboard_script=stub.path,
        )

    return build


def recorded_arguments(builder: SiteBuilder, plan_id: SitePlanId) -> dict[str, Any]:
    """
    What the stub refresh was handed for one plan.

    :param builder: The builder that ran it.
    :param plan_id: The plan whose refresh to read back.
    :return: The recorded arguments.
    """
    return json.loads(
        (
            builder.output_directory
            / SitePath.PLANS_DIRECTORY
            / plan_id
            / RECORDED_ARGUMENTS_FILENAME
        ).read_text()
    )


def test_every_plan_gets_a_page_and_the_index_lists_them_all(build_site):
    """
    The site is one directory per plan plus an index, laid out so a directory URL
    resolves to a page.
    """
    builder = build_site()

    summaries = builder.build()

    assert [summary.id for summary in summaries] == [
        SitePlanId.FIRST,
        SitePlanId.SECOND,
    ]
    assert (builder.output_directory / SitePath.INDEX_PAGE).is_file()
    for plan_id in SitePlanId:
        assert (
            builder.output_directory
            / SitePath.PLANS_DIRECTORY
            / plan_id
            / SitePath.INDEX_PAGE
        ).is_file()


def test_the_index_links_each_plan_at_its_published_url(build_site):
    """
    A plan's index link is absolute against the site's base URL, so it resolves on the
    published site rather than only inside the output directory.
    """
    builder = build_site()

    builder.build()

    expected_url = f"{SITE_BASE_URL}/{SitePath.PLANS_DIRECTORY}/{SitePlanId.FIRST}/"
    assert builder.dashboard_url_of(SitePlanId.FIRST) == expected_url
    assert expected_url in (builder.output_directory / SitePath.INDEX_PAGE).read_text()


def test_a_plan_summary_reports_the_counts_the_refresh_computed(build_site):
    """
    The index's progress comes from the refresh's own summary, not from a second count
    taken here.
    """
    summaries = build_site().build()
    first_plan = SitePlanId.FIRST.plan

    assert summaries[0].title == first_plan.title
    assert summaries[0].description == first_plan.description
    assert summaries[0].done == 1
    assert summaries[0].total == 2


def test_the_refresh_receives_the_plan_data_and_its_tracking_url(build_site):
    """
    Each plan's refresh is handed that plan's own manifest and roadmap as read off the
    branch, plus the tracking URL GitHub reported for it.
    """
    builder = build_site()

    builder.build()

    recorded = recorded_arguments(builder, SitePlanId.FIRST)
    assert recorded[RefreshArgument.PLAN_ID] == SitePlanId.FIRST
    assert recorded[RefreshArgument.TRACKING_URL] == TRACKING_ISSUE_URL
    assert recorded[RecordedArgumentKey.ROADMAP] == SitePlanId.FIRST.document(
        PlanDocument.ROADMAP
    )
    assert recorded[RecordedArgumentKey.PLAN] == SitePlanId.FIRST.document(
        PlanDocument.MANIFEST
    )


def test_the_refresh_receives_only_the_pull_requests_the_plan_references(build_site):
    """The data handed down is the plan's own referenced pull requests - not every pull
    request the repository happens to have - and carries the fields the dashboard
    classifies on, ``merged_at`` included."""
    builder = build_site()

    builder.build()

    recorded = recorded_arguments(builder, SitePlanId.FIRST)
    assert json.loads(recorded[RecordedArgumentKey.PULL_REQUEST_DATA]) == {
        REPOSITORY: {
            str(REFERENCED_PULL_REQUEST): {
                PullRequestField.STATE.value: PullRequestState.OPEN.value,
                PullRequestField.DRAFT.value: True,
                PullRequestField.MERGED_AT.value: None,
                PullRequestField.LABELS.value: [],
            }
        }
    }


def test_a_repository_is_listed_once_however_many_plans_reference_it(build_site):
    """Both plans reference the same repository, and one listing serves both - a
    listing per plan would repeat the same pages."""
    builder = build_site()

    builder.build()

    assert list(builder.pull_requests_by_repository) == [REPOSITORY]


def test_a_failing_refresh_names_the_plan_it_failed_for(build_site):
    """A plan whose refresh fails stops the build, saying which plan - the site must
    not publish an index over pages no script agreed to write."""
    builder = build_site(SiteStub.FAILING_REFRESH_DASHBOARD)

    with pytest.raises(DashboardRefreshError) as raised:
        builder.build()

    assert raised.value.plan_identifier == SitePlanId.FIRST


# %% the refresh command


def test_the_refresh_command_omits_the_tracking_option_when_there_is_no_issue(
    tmp_path: Path,
):
    """
    A plan that tracks no issue is refreshed without the option at all, rather than with
    an empty one the script would then have to interpret.
    """
    command = RefreshDashboardCommand(
        plan_identifier=SitePlanId.FIRST,
        manifest_file=tmp_path / PlanDocument.MANIFEST,
        roadmap_file=tmp_path / PlanDocument.ROADMAP,
        pull_request_data_file=tmp_path / "pr_data.json",
        dashboard_page=tmp_path / SitePath.INDEX_PAGE,
    )

    assert RefreshArgument.TRACKING_URL not in command.command_line(tmp_path / "run.sh")


def test_the_refresh_command_names_every_option_it_was_given(tmp_path: Path):
    """
    Each field the command carries reaches the script under its own option, so a file
    staged here cannot be handed over under the wrong flag.
    """
    dashboard_page = tmp_path / SitePath.INDEX_PAGE
    command = RefreshDashboardCommand(
        plan_identifier=SitePlanId.FIRST,
        manifest_file=tmp_path / PlanDocument.MANIFEST,
        roadmap_file=tmp_path / PlanDocument.ROADMAP,
        pull_request_data_file=tmp_path / "pr_data.json",
        dashboard_page=dashboard_page,
        tracking_url=TRACKING_ISSUE_URL,
    )

    command_line = command.command_line(tmp_path / "run.sh")

    for option, expected in (
        (RefreshArgument.PLAN_ID, str(SitePlanId.FIRST)),
        (RefreshArgument.PLAN, str(command.manifest_file)),
        (RefreshArgument.ROADMAP, str(command.roadmap_file)),
        (RefreshArgument.PULL_REQUEST_DATA, str(command.pull_request_data_file)),
        (RefreshArgument.OUTPUT, str(dashboard_page)),
        (RefreshArgument.TRACKING_URL, TRACKING_ISSUE_URL),
    ):
        assert command_line[command_line.index(option) + 1] == expected
