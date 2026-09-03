"""
Tests for check_dependency_readiness.py: classifying one item's dependencies as ready or
not-ready to build on, via build_dashboard.py's own live-state rule.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

from build_dashboard import (
    DependencyReference,
    Item,
    ItemStatus,
    LiveState,
    Plan,
    PlanDirectory,
    PlanValidationError,
    PullRequestRecord,
    PullRequestState,
    Track,
    Wave,
    validate_plan,
)
from check_dependency_readiness import UnknownItemError, dependency_readiness, main


def make_plan(items: list[Item]) -> Plan:
    """
    Build one :class:`Plan` for a test, with a single wave/track and *items*
    - the shared entry point every test in this file builds a plan through.

    :param items: The plan's items.
    """
    return Plan(
        id="test-plan",
        title="Test Plan",
        description="desc",
        default_repository="owner/repo",
        waves=[Wave(id="wave-1", name="Wave One")],
        tracks=[Track(id="track-1", name="Track One", wave="wave-1")],
        items=items,
    )


def item(
    identifier: str,
    status: ItemStatus,
    pull_request_number: int | None = None,
    depends_on: list[str] | None = None,
) -> Item:
    """
    Build one :class:`Item` for a test, filling in the boilerplate
    (``title``/``branch``/``id`` all equal to *identifier*, a fixed ``track``) every
    item in this file would otherwise repeat.
    """
    return Item(
        title=identifier,
        branch=identifier,
        track="track-1",
        status=status,
        id=identifier,
        pull_request_number=pull_request_number,
        depends_on=depends_on or [],
    )


def test_raises_for_an_unknown_item():
    plan = make_plan([item("a", ItemStatus.NOT_STARTED)])
    with pytest.raises(UnknownItemError, match="ghost"):
        dependency_readiness(plan, "ghost", {})


def test_empty_list_for_an_item_with_no_dependencies():
    plan = make_plan([item("a", ItemStatus.NOT_STARTED)])
    assert dependency_readiness(plan, "a", {}) == []


def test_done_dependency_is_ready():
    plan = make_plan(
        [
            item("a", ItemStatus.DONE),
            item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
        ]
    )
    results = dependency_readiness(plan, "b", {})
    assert results == [
        {"identifier": "a", "title": "a", "live_state": "none", "is_ready": True}
    ]


def test_open_ready_dependency_is_ready():
    pull_requests_by_repository = {
        "owner/repo": {"1": PullRequestRecord(state=PullRequestState.OPEN, draft=False)}
    }
    plan = make_plan(
        [
            item("a", ItemStatus.IN_PROGRESS, pull_request_number=1),
            item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
        ]
    )
    results = dependency_readiness(plan, "b", pull_requests_by_repository)
    assert results == [
        {
            "identifier": "a",
            "title": "a",
            "live_state": "open_ready",
            "is_ready": True,
        }
    ]


def test_open_draft_dependency_is_not_ready():
    pull_requests_by_repository = {
        "owner/repo": {"1": PullRequestRecord(state=PullRequestState.OPEN, draft=True)}
    }
    plan = make_plan(
        [
            item("a", ItemStatus.IN_PROGRESS, pull_request_number=1),
            item("b", ItemStatus.NOT_STARTED, depends_on=["a"]),
        ]
    )
    results = dependency_readiness(plan, "b", pull_requests_by_repository)
    assert results == [
        {
            "identifier": "a",
            "title": "a",
            "live_state": "open_draft",
            "is_ready": False,
        }
    ]


def test_unresolvable_dependency_identifier_is_reported_not_ready():
    plan = make_plan([item("b", ItemStatus.NOT_STARTED, depends_on=["ghost"])])
    results = dependency_readiness(plan, "b", {})
    assert results == [
        {"identifier": "ghost", "title": None, "live_state": None, "is_ready": False}
    ]


def test_multiple_dependencies_reported_in_order():
    plan = make_plan(
        [
            item("a", ItemStatus.DONE),
            item("b", ItemStatus.NOT_STARTED),
            item("c", ItemStatus.NOT_STARTED, depends_on=["b", "a"]),
        ]
    )
    results = dependency_readiness(plan, "c", {})
    assert [entry["identifier"] for entry in results] == ["b", "a"]
    assert [entry["is_ready"] for entry in results] == [False, True]


# %% main


def _minimal_plan_mapping():
    return {
        "schema_version": 1,
        "id": "test-plan",
        "title": "Test Plan",
        "description": "A plan.",
        "default_repository": "owner/repo",
        "waves": [{"id": "wave-1", "name": "Wave 1"}],
        "tracks": [{"id": "track-1", "name": "Track 1", "wave": "wave-1"}],
        "items": [
            {
                "id": "a",
                "title": "Item A",
                "branch": "a",
                "track": "track-1",
                "status": "done",
            },
            {
                "id": "b",
                "title": "Item B",
                "branch": "b",
                "track": "track-1",
                "status": "not_started",
                "depends_on": ["a"],
            },
        ],
    }


def test_main_prints_the_dependency_readiness_of_the_requested_item(
    tmp_path, monkeypatch, capsys
):
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.dump(_minimal_plan_mapping()))
    pull_request_data_path = tmp_path / "pr_data.json"
    pull_request_data_path.write_text("{}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_dependency_readiness.py",
            "--plan",
            str(plan_path),
            "--pr-data",
            str(pull_request_data_path),
            "--item",
            "b",
        ],
    )
    exit_code = main()
    assert exit_code == 0
    results = json.loads(capsys.readouterr().out)
    assert results == [
        {"identifier": "a", "title": "Item A", "live_state": "none", "is_ready": True}
    ]


def test_main_rejects_an_invalid_manifest_instead_of_crashing(
    tmp_path, monkeypatch, capsys
):
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text("")  # yaml.safe_load("") -> None, not a mapping
    pull_request_data_path = tmp_path / "pr_data.json"
    pull_request_data_path.write_text("{}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_dependency_readiness.py",
            "--plan",
            str(plan_path),
            "--pr-data",
            str(pull_request_data_path),
            "--item",
            "b",
        ],
    )
    exit_code = main()
    assert exit_code == 1
    with pytest.raises(PlanValidationError) as expected_error:
        validate_plan(None)
    assert capsys.readouterr().err == f"{expected_error.value}\n"


def test_main_rejects_an_unknown_item_id(tmp_path, monkeypatch, capsys):
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.dump(_minimal_plan_mapping()))
    pull_request_data_path = tmp_path / "pr_data.json"
    pull_request_data_path.write_text("{}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_dependency_readiness.py",
            "--plan",
            str(plan_path),
            "--pr-data",
            str(pull_request_data_path),
            "--item",
            "ghost",
        ],
    )
    exit_code = main()
    assert exit_code == 1
    assert "ghost" in capsys.readouterr().err


# %% cross-plan references


FIXTURE_PLANS_DIRECTORY = Path(__file__).parent / "fixtures" / "plans"
"""
The same two-manifest plans directory test_build_dashboard.py resolves cross-plan
references against.
"""


def foreign_reference(item_identifier: str, plan_id: str = "other-plan") -> str:
    """
    The ``depends_on`` text naming one item of another plan.

    :param item_identifier: The foreign item's own id.
    :param plan_id: The plan holding it.
    """
    return DependencyReference(item_identifier=item_identifier, plan_id=plan_id).text


def test_foreign_dependency_is_read_against_its_own_plans_repository():
    # 91 exists only under other-plan's repository, so reading it against
    # this plan's own would report not_found rather than open_ready.
    reference = foreign_reference("foreign-ready")
    plan = make_plan([item("b", ItemStatus.NOT_STARTED, depends_on=[reference])])
    results = dependency_readiness(
        plan,
        "b",
        {
            "other/owner-repo": {
                "91": PullRequestRecord(state=PullRequestState.OPEN, draft=False)
            }
        },
        PlanDirectory.load(FIXTURE_PLANS_DIRECTORY),
    )
    assert results == [
        {
            "identifier": reference,
            "title": "A foreign item whose pull request is out of draft",
            "live_state": LiveState.OPEN_READY.value,
            "is_ready": True,
        }
    ]


def test_foreign_dependency_is_not_ready_without_a_plans_directory():
    # Nothing can resolve it, and an unresolvable dependency is never ready.
    reference = foreign_reference("foreign-ready")
    plan = make_plan([item("b", ItemStatus.NOT_STARTED, depends_on=[reference])])
    assert dependency_readiness(plan, "b", {}) == [
        {
            "identifier": reference,
            "title": None,
            "live_state": None,
            "is_ready": False,
        }
    ]


def test_main_resolves_a_cross_plan_dependency_against_the_plans_directory(
    tmp_path, monkeypatch, capsys
):
    reference = foreign_reference("foreign-done")
    plan_mapping = _minimal_plan_mapping()
    plan_mapping["items"][1]["depends_on"] = [reference]
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.dump(plan_mapping))
    pull_request_data_path = tmp_path / "pr_data.json"
    pull_request_data_path.write_text("{}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_dependency_readiness.py",
            "--plan",
            str(plan_path),
            "--pr-data",
            str(pull_request_data_path),
            "--item",
            "b",
            "--plans-dir",
            str(FIXTURE_PLANS_DIRECTORY),
        ],
    )
    assert main() == 0
    results = json.loads(capsys.readouterr().out)
    assert [entry["identifier"] for entry in results] == [reference]
    assert [entry["is_ready"] for entry in results] == [True]
