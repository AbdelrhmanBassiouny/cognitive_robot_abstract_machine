"""
Tests for the Action that publishes the dashboards as a Pages site.

Nothing here runs the workflow - GitHub does that. What is checked is everything a run
would only discover by failing: that it drives the scripts it means to, at the paths
those scripts actually have; that it fires on the events a dashboard's data changes
with; that it holds the permissions its writes need; and that it publishes by a route a
pull request run is allowed to take.
"""

from pathlib import Path

import pytest
import yaml

PLAN_DASHBOARD_DIRECTORY = Path(__file__).parent.parent
REPOSITORY_ROOT = PLAN_DASHBOARD_DIRECTORY.parent.parent.parent
WORKFLOW_FILE = REPOSITORY_ROOT / ".github" / "workflows" / "plan-dashboards.yml"

DRIVEN_SCRIPTS = (
    PLAN_DASHBOARD_DIRECTORY / "build_site.py",
    PLAN_DASHBOARD_DIRECTORY / "pages_site.py",
    PLAN_DASHBOARD_DIRECTORY / "publish_site.sh",
    PLAN_DASHBOARD_DIRECTORY / "requirements.txt",
)

SHARED_PATH_CONSTANTS = (
    "${BUILD_SITE_SCRIPT}",
    "${PAGES_SITE_SCRIPT}",
    "${PUBLISH_SITE_SCRIPT}",
    "${PLAN_DASHBOARD_REQUIREMENTS_FILE}",
)

PULL_REQUEST_EVENT = "pull_request"
DISPATCH_EVENT = "workflow_dispatch"
PUSH_EVENT = "push"

DEPLOY_PAGES_ACTION = "actions/deploy-pages"


@pytest.fixture
def workflow() -> dict:
    """
    The parsed workflow.

    :return: Its mapping.
    """
    return yaml.safe_load(WORKFLOW_FILE.read_text())


@pytest.fixture
def triggers(workflow: dict) -> dict:
    """
    The workflow's trigger block.

    ``on`` is read back under YAML's boolean spelling: an unquoted ``on:`` key parses as
    ``True``, which is the shape the file on disk actually has.

    :param workflow: The parsed workflow.
    :return: The events it fires on.
    """
    return workflow[True]


# %% when it runs


def test_it_publishes_on_every_pull_request_transition_a_dashboard_shows(
    triggers: dict,
):
    """
    A dashboard classifies each item as merged, draft or ready for review, so every
    transition between those has to reach it.
    """
    assert set(triggers[PULL_REQUEST_EVENT]["types"]) == {
        "opened",
        "reopened",
        "ready_for_review",
        "converted_to_draft",
        "closed",
    }


def test_it_can_be_dispatched(triggers: dict):
    """
    A manifest edit pushed to the notes branch changes the dashboards and raises no
    event here, so the site must be rebuildable on demand.
    """
    assert DISPATCH_EVENT in triggers


def test_it_republishes_when_the_renderer_itself_changes(triggers: dict):
    """
    A change to the scripts changes every page, and no pull request event would rebuild
    them.
    """
    watched = triggers[PUSH_EVENT]["paths"]

    assert f"{PLAN_DASHBOARD_DIRECTORY.relative_to(REPOSITORY_ROOT)}/**" in watched
    assert str(WORKFLOW_FILE.relative_to(REPOSITORY_ROOT)) in watched


def test_a_superseded_run_is_cancelled_rather_than_queued(workflow: dict):
    """Several pull requests moving at once would otherwise race for the site branch,
    and a superseded build has nothing to contribute - it read its live state before
    the newer one did."""
    assert workflow["concurrency"]["cancel-in-progress"] is True


# %% how it publishes


def test_it_publishes_by_a_route_a_pull_request_run_is_allowed_to_take(workflow: dict):
    """The github-pages environment only accepts deployments from the default branch, so
    a run triggered by a pull request is rejected before its first step - which would
    fail every run on the workflow's main trigger. The site goes to a branch instead,
    and nothing here may reintroduce the environment deployment."""
    steps = workflow["jobs"]["publish"]["steps"]

    assert "environment" not in workflow["jobs"]["publish"]
    assert not [step for step in steps if DEPLOY_PAGES_ACTION in step.get("uses", "")]


def test_it_holds_the_permissions_its_writes_need(workflow: dict):
    """
    It pushes the site branch and the merged-to-done manifest correction, and points
    Pages at that branch; without both grants one of those fails at the end of a full
    build.
    """
    assert workflow["permissions"] == {"contents": "write", "pages": "write"}


def test_it_builds_from_the_default_branch_rather_than_the_triggering_head(
    workflow: dict,
):
    """
    A run triggered by a pull request must publish the site the repository defines, not
    whatever that branch has changed the renderer into.
    """
    checkout = workflow["jobs"]["publish"]["steps"][0]

    assert checkout["with"]["ref"] == "${{ github.event.repository.default_branch }}"


def test_it_checks_out_the_whole_history(workflow: dict):
    """
    Neither the notes-branch worktree the correction push commits in nor the site
    branch's own can be pushed from a shallow clone.
    """
    checkout = workflow["jobs"]["publish"]["steps"][0]

    assert checkout["with"]["fetch-depth"] == 0


def test_a_fork_pull_request_is_skipped(workflow: dict):
    """
    Its token is read-only and can push neither branch, so the run would only ever fail.
    """
    condition = workflow["jobs"]["publish"]["if"]

    assert "github.event.pull_request.head.repo.full_name == github.repository" in (
        condition
    )


# %% what it drives


def test_it_names_no_path_of_its_own():
    """
    It sources the configuration script and uses the constants defined there, so a moved
    script cannot leave it pointing at a path that no longer exists.
    """
    workflow_text = WORKFLOW_FILE.read_text()

    for constant in SHARED_PATH_CONSTANTS:
        assert constant in workflow_text
    for script in DRIVEN_SCRIPTS:
        assert str(script.relative_to(REPOSITORY_ROOT)) not in workflow_text


def test_the_scripts_it_drives_exist():
    """The constants it sources resolve to real files - the one thing a run would
    otherwise only discover by failing."""
    for script in DRIVEN_SCRIPTS:
        assert script.is_file()
