"""
Tests for the headless static-site build: discovering the plans on a notes branch,
fetching their pull request data through an injected transport, driving one dashboard
refresh per plan, and rendering the master index over the results.

The notes remote is a scratch bare repository, the GitHub side is a fake, and the
per-plan refresh is a recorded stub - ``refresh_dashboard.sh``'s own behaviour has its
own test module and is not re-tested here.
"""

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from build_dashboard import ItemStatus, PullRequestState
from build_site import (
    DASHBOARD_DIRECTORY,
    INDEX_PAGE_FILENAME,
    DashboardRefreshError,
    SiteBuilder,
)
from github_api import (
    ISSUE_URL_FIELD,
    GitHubApi,
    PullRequestField,
    PullRequestListParameter,
)
from personal_notes import PersonalNotesBranch

SITE_BASE_URL = "https://owner.github.io/repository"
REPOSITORY = "owner/repository"
TRACKING_ISSUE_URL = f"https://github.com/{REPOSITORY}/issues/9"
STUBS_DIRECTORY = Path(__file__).parent / "fixtures" / "stubs"
REFRESH_DASHBOARD_STUB = STUBS_DIRECTORY / "refresh_dashboard_stub.sh"
FAILING_REFRESH_DASHBOARD_STUB = STUBS_DIRECTORY / "refresh_dashboard_failure_stub.sh"
RECORDED_ARGUMENTS_FILENAME = "arguments.json"

REFERENCED_PULL_REQUEST = 1
UNREFERENCED_PULL_REQUEST = 2

PLAN_MANIFEST = f"""\
schema_version: 1
id: {{plan_identifier}}
title: "Plan {{plan_identifier}}"
description: "What {{plan_identifier}} is for."
default_repository: {REPOSITORY}
tracking_issue: 9
waves:
  - id: only-wave
    name: "Only wave"
tracks:
  - id: only-track
    name: "Only track"
    wave: only-wave
items:
  - id: an-item
    branch: a-branch
    title: "An item"
    track: only-track
    status: {ItemStatus.IN_PROGRESS.value}
    pull_request_number: {REFERENCED_PULL_REQUEST}
  - id: an-item-nobody-has-opened-yet
    branch: another-branch
    title: "An item nobody has opened yet"
    track: only-track
    status: {ItemStatus.NOT_STARTED.value}
"""


class PlanDataFakeApi(GitHubApi):
    """
    Serves the tracking issue and the pull requests the seeded plans are checked
    against - one they reference and one they do not.
    """

    def __init__(self, pull_request_payload):
        self.pull_request_payload = pull_request_payload

    def get(self, path: str, parameters: Mapping[str, str] | None = None) -> Any:
        if path.endswith("/issues/9"):
            return {ISSUE_URL_FIELD: TRACKING_ISSUE_URL}
        if parameters[PullRequestListParameter.PAGE] != "1":
            return []
        return [
            self.pull_request_payload(
                REFERENCED_PULL_REQUEST, state=PullRequestState.OPEN, draft=True
            ),
            self.pull_request_payload(
                UNREFERENCED_PULL_REQUEST, state=PullRequestState.OPEN
            ),
        ]


@pytest.fixture
def two_plans(plan_files) -> dict:
    """
    Two plans referencing the same repository, to seed a scratch notes branch with.

    :param plan_files: The plan-files type.
    :return: The plans, keyed by identifier.
    """
    return {
        plan_identifier: plan_files(
            manifest=PLAN_MANIFEST.format(plan_identifier=plan_identifier),
            roadmap=f"# {plan_identifier} roadmap\n",
        )
        for plan_identifier in ("first-plan", "second-plan")
    }


@pytest.fixture
def build_site(notes_clone, two_plans, pull_request_payload, tmp_path: Path):
    """
    Build a site builder wired to a scratch clone, the fake transport and a stub
    refresh.

    :param notes_clone: The scratch notes-branch builder.
    :param two_plans: The plans to seed.
    :param pull_request_payload: The GitHub payload builder.
    :param tmp_path: pytest's per-test temporary directory.
    :return: The builder factory, called with the refresh script to drive.
    """
    clone = notes_clone(two_plans)

    def build(refresh_script: Path = REFRESH_DASHBOARD_STUB) -> SiteBuilder:
        return SiteBuilder(
            output_directory=tmp_path / "_site",
            site_base_url=SITE_BASE_URL,
            api=PlanDataFakeApi(pull_request_payload),
            notes=PersonalNotesBranch.resolve(clone),
            refresh_dashboard_script=refresh_script,
        )

    return build


def test_every_plan_gets_a_page_and_the_index_lists_them_all(build_site):
    """
    The site is one directory per plan plus an index, laid out so a directory URL
    resolves to a page.
    """
    builder = build_site()

    summaries = builder.build()

    assert [summary.id for summary in summaries] == ["first-plan", "second-plan"]
    assert (builder.output_directory / INDEX_PAGE_FILENAME).is_file()
    for plan_identifier in ("first-plan", "second-plan"):
        assert (
            builder.output_directory
            / DASHBOARD_DIRECTORY
            / plan_identifier
            / INDEX_PAGE_FILENAME
        ).is_file()


def test_the_index_links_each_plan_at_its_published_url(build_site):
    """
    A plan's index link is absolute against the site's base URL, so it resolves on the
    published site rather than only inside the output directory.
    """
    builder = build_site()

    builder.build()

    expected_url = f"{SITE_BASE_URL}/{DASHBOARD_DIRECTORY}/first-plan/"
    assert builder.dashboard_url_of("first-plan") == expected_url
    assert expected_url in (builder.output_directory / INDEX_PAGE_FILENAME).read_text()


def test_a_plan_summary_reports_the_counts_the_refresh_computed(build_site):
    """
    The index's progress comes from the refresh's own summary, not from a second count
    taken here.
    """
    summaries = build_site().build()

    assert summaries[0].title == "Plan first-plan"
    assert summaries[0].description == "What first-plan is for."
    assert summaries[0].done == 1
    assert summaries[0].total == 2


def test_the_refresh_receives_the_plan_data_and_its_tracking_url(build_site):
    """
    Each plan's refresh is handed that plan's own manifest and roadmap as read off the
    branch, plus the tracking URL GitHub reported for it.
    """
    builder = build_site()

    builder.build()

    recorded = json.loads(
        (
            builder.output_directory
            / DASHBOARD_DIRECTORY
            / "first-plan"
            / RECORDED_ARGUMENTS_FILENAME
        ).read_text()
    )
    assert recorded["--plan-id"] == "first-plan"
    assert recorded["--tracking-url"] == TRACKING_ISSUE_URL
    assert recorded["roadmap"] == "# first-plan roadmap\n"
    assert recorded["plan"] == PLAN_MANIFEST.format(plan_identifier="first-plan")


def test_the_refresh_receives_only_the_pull_requests_the_plan_references(build_site):
    """The data handed down is the plan's own referenced pull requests - not every pull
    request the repository happens to have - and carries the fields the dashboard
    classifies on, ``merged_at`` included."""
    builder = build_site()

    builder.build()

    recorded = json.loads(
        (
            builder.output_directory
            / DASHBOARD_DIRECTORY
            / "first-plan"
            / RECORDED_ARGUMENTS_FILENAME
        ).read_text()
    )
    assert json.loads(recorded["pr-data"]) == {
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
    builder = build_site(FAILING_REFRESH_DASHBOARD_STUB)

    with pytest.raises(DashboardRefreshError) as raised:
        builder.build()

    assert "first-plan" in str(raised.value)
