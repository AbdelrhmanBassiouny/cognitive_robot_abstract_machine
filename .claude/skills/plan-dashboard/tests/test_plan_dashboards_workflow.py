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

from workflow_document import (
    DEPLOY_PAGES_ACTION,
    CheckoutInput,
    Permission,
    PermissionLevel,
    PullRequestActivity,
    TriggerEvent,
    TriggerKey,
    WorkflowDocument,
)

PLAN_DASHBOARD_DIRECTORY = Path(__file__).parent.parent
REPOSITORY_ROOT = PLAN_DASHBOARD_DIRECTORY.parent.parent.parent
WORKFLOW_FILE = REPOSITORY_ROOT / ".github" / "workflows" / "plan-dashboards.yml"

PUBLISHING_JOB = "publish"
"""The one job the workflow runs, named as the workflow names it."""

CONFIGURATION_SCRIPT = (
    REPOSITORY_ROOT / ".claude" / "hooks" / ("resolve-personal-notes-config.sh")
)

DRIVEN_SCRIPTS = (
    PLAN_DASHBOARD_DIRECTORY / "build_site.py",
    PLAN_DASHBOARD_DIRECTORY / "pages_site.py",
    PLAN_DASHBOARD_DIRECTORY / "publish_site.py",
    PLAN_DASHBOARD_DIRECTORY / "requirements.txt",
)

SHARED_PATH_CONSTANTS = (
    "${BUILD_SITE_SCRIPT}",
    "${PAGES_SITE_SCRIPT}",
    "${PUBLISH_SITE_SCRIPT}",
    "${PLAN_DASHBOARD_REQUIREMENTS_FILE}",
)

FORK_PULL_REQUEST_CONDITION = (
    "github.event.pull_request.head.repo.full_name == github.repository"
)

WHOLE_HISTORY = 0
"""The ``fetch-depth`` asking for every commit, which both pushes need."""


@pytest.fixture
def workflow() -> WorkflowDocument:
    """
    The parsed workflow.

    :return: Its model.
    """
    return WorkflowDocument(WORKFLOW_FILE)


@pytest.fixture
def checkout(workflow: WorkflowDocument):
    """
    The publishing job's checkout step.

    :param workflow: The parsed workflow.
    :return: The step.
    """
    return workflow.job(PUBLISHING_JOB).steps[0]


# %% when it runs


def test_it_publishes_on_every_pull_request_transition_a_dashboard_shows(
    workflow: WorkflowDocument,
):
    """
    A dashboard classifies each item as merged, draft or ready for review, so every
    transition between those has to reach it.
    """
    activities = workflow.trigger(TriggerEvent.PULL_REQUEST)[TriggerKey.ACTIVITY_TYPES]

    assert set(activities) == set(PullRequestActivity)


def test_it_can_be_dispatched(workflow: WorkflowDocument):
    """
    A manifest edit pushed to the notes branch changes the dashboards and raises no
    event here, so the site must be rebuildable on demand.
    """
    assert workflow.answers_to(TriggerEvent.WORKFLOW_DISPATCH)


def test_it_republishes_when_the_renderer_itself_changes(workflow: WorkflowDocument):
    """
    A change to the scripts changes every page, and no pull request event would rebuild
    them.
    """
    watched = workflow.trigger(TriggerEvent.PUSH)[TriggerKey.PATHS]

    assert f"{PLAN_DASHBOARD_DIRECTORY.relative_to(REPOSITORY_ROOT)}/**" in watched
    assert str(WORKFLOW_FILE.relative_to(REPOSITORY_ROOT)) in watched
    assert str(CONFIGURATION_SCRIPT.relative_to(REPOSITORY_ROOT)) in watched


def test_a_superseded_run_is_cancelled_rather_than_queued(workflow: WorkflowDocument):
    """Several pull requests moving at once would otherwise race for the site branch,
    and a superseded build has nothing to contribute - it read its live state before
    the newer one did."""
    assert workflow.cancels_superseded_runs is True


# %% how it publishes


def test_it_publishes_by_a_route_a_pull_request_run_is_allowed_to_take(
    workflow: WorkflowDocument,
):
    """The github-pages environment only accepts deployments from the default branch, so
    a run triggered by a pull request is rejected before its first step - which would
    fail every run on the workflow's main trigger. The site goes to a branch instead,
    and nothing here may reintroduce the environment deployment."""
    job = workflow.job(PUBLISHING_JOB)

    assert job.deploys_to_an_environment is False
    assert job.runs(DEPLOY_PAGES_ACTION) is False


def test_it_holds_the_permissions_its_writes_need(workflow: WorkflowDocument):
    """
    It pushes the site branch and the merged-to-done manifest correction, and points
    Pages at that branch; without both grants one of those fails at the end of a full
    build.
    """
    assert workflow.permissions == {
        Permission.CONTENTS: PermissionLevel.WRITE,
        Permission.PAGES: PermissionLevel.WRITE,
    }


def test_it_builds_with_the_renderer_it_was_started_with(checkout):
    """The workflow and the scripts it drives are versioned together, so the checkout
    names no branch: naming one can name a branch that carries no renderer at all,
    which is what main is today. It also lets the same file publish from wherever it
    is carried - a dispatch from the default branch, a push to main, a pull request -
    without one of those routes silently building nothing."""
    assert checkout.is_given(CheckoutInput.REFERENCE) is False


def test_it_checks_out_the_whole_history(checkout):
    """
    Neither the notes-branch worktree the correction push commits in nor the site
    branch's own can be pushed from a shallow clone.
    """
    assert checkout.given(CheckoutInput.FETCH_DEPTH) == WHOLE_HISTORY


def test_a_fork_pull_request_is_skipped(workflow: WorkflowDocument):
    """
    Its token is read-only and can push neither branch, so the run would only ever fail.
    """
    assert FORK_PULL_REQUEST_CONDITION in workflow.job(PUBLISHING_JOB).condition


# %% what it drives


def test_it_names_no_path_of_its_own(workflow: WorkflowDocument):
    """
    It sources the configuration script and uses the constants defined there, so a moved
    script cannot leave it pointing at a path that no longer exists.
    """
    for constant in SHARED_PATH_CONSTANTS:
        assert constant in workflow.text
    for script in DRIVEN_SCRIPTS:
        assert str(script.relative_to(REPOSITORY_ROOT)) not in workflow.text


def test_the_scripts_it_drives_exist():
    """The constants it sources resolve to real files - the one thing a run would
    otherwise only discover by failing."""
    for script in DRIVEN_SCRIPTS:
        assert script.is_file()
