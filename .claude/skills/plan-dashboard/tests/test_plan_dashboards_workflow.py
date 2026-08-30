"""
Tests for the Action that publishes the dashboards as a Pages site.

Nothing here runs the workflow - GitHub does that. What is checked is everything a
run would only discover by failing: that it drives the script it means to, at the path
that script actually has; that it fires on the events a dashboard's data changes with;
and that it holds the permissions its two writes need.
"""

from pathlib import Path

import pytest
import yaml

PLAN_DASHBOARD_DIRECTORY = Path(__file__).parent.parent
REPOSITORY_ROOT = PLAN_DASHBOARD_DIRECTORY.parent.parent.parent
WORKFLOW_FILE = REPOSITORY_ROOT / ".github" / "workflows" / "plan-dashboards.yml"

BUILD_SITE_SCRIPT = PLAN_DASHBOARD_DIRECTORY / "build_site.py"
REQUIREMENTS_FILE = PLAN_DASHBOARD_DIRECTORY / "requirements.txt"

PULL_REQUEST_EVENT = "pull_request"
DISPATCH_EVENT = "workflow_dispatch"
PUSH_EVENT = "push"


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

    ``on`` is read back through YAML's boolean spelling: an unquoted ``on:`` key parses
    as ``True``, which is the shape the file on disk actually has.

    :param workflow: The parsed workflow.
    :return: The events it fires on.
    """
    return workflow[True]


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

    assert f"{BUILD_SITE_SCRIPT.parent.relative_to(REPOSITORY_ROOT)}/**" in watched
    assert str(WORKFLOW_FILE.relative_to(REPOSITORY_ROOT)) in watched


def test_it_drives_the_site_build_through_the_shared_path_constants():
    """
    The workflow names no path of its own: it sources the configuration script and uses
    the constants defined there, so a moved script cannot leave it pointing at a path
    that no longer exists.
    """
    workflow_text = WORKFLOW_FILE.read_text()

    assert "${BUILD_SITE_SCRIPT}" in workflow_text
    assert "${PLAN_DASHBOARD_REQUIREMENTS_FILE}" in workflow_text
    assert str(BUILD_SITE_SCRIPT.relative_to(REPOSITORY_ROOT)) not in workflow_text


def test_the_scripts_the_workflow_drives_exist():
    """The constants it sources resolve to real files - the one thing a run would
    otherwise only discover by failing."""
    assert BUILD_SITE_SCRIPT.is_file()
    assert REQUIREMENTS_FILE.is_file()


def test_it_holds_the_permissions_its_two_writes_need(workflow: dict):
    """
    It pushes the merged-to-done manifest correction back to the notes branch and
    deploys a Pages site; without all three grants one of those fails at the end of a
    full build.
    """
    assert workflow["permissions"] == {
        "contents": "write",
        "pages": "write",
        "id-token": "write",
    }


def test_a_superseded_run_is_cancelled_rather_than_queued(workflow: dict):
    """Several pull requests moving at once would otherwise race for one Pages
    deployment, and a superseded build has nothing to contribute - it read its live
    state before the newer one did."""
    assert workflow["concurrency"]["cancel-in-progress"] is True
