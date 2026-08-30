"""
Makes the plan-dashboard scripts importable as plain modules, and shares the
scratch-notes-branch scaffolding the headless site build's tests are written against.

The scripts are single-file scripts run via ``python3 build_dashboard.py ...``, not an
installed package - so their directory is added to ``sys.path`` here rather than
requiring an ``__init__.py``/packaging setup just for tests.
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_dashboard import PullRequestState
from github_api import LABEL_NAME_FIELD, PullRequestField
from personal_notes import (
    NOTES_BRANCH_SETTING,
    NOTES_REMOTE_SETTING,
    PLAN_MANIFEST_FILENAME,
    PLAN_ROADMAP_FILENAME,
    PLANS_DIRECTORY,
)

# %% scratch git repositories

GIT_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}
"""A fixed identity and a minimal path, so a scratch commit never depends on the
running user's git configuration."""


@dataclass(frozen=True)
class PlanFiles:
    """
    One plan's files, as seeded onto a scratch notes branch.
    """

    manifest: str
    """
    The plan's ``plan.yaml`` source.
    """

    roadmap: str
    """
    The plan's ``roadmap.md`` source.
    """


@pytest.fixture(autouse=True)
def without_inherited_notes_configuration(monkeypatch):
    """
    Strip the caller's own personal-notes settings, so a real remote can never leak into
    a test - and from there onto the network.
    """
    monkeypatch.delenv(NOTES_REMOTE_SETTING.environment_variable, raising=False)
    monkeypatch.delenv(NOTES_BRANCH_SETTING.environment_variable, raising=False)


@pytest.fixture
def plan_files() -> type[PlanFiles]:
    """
    The plan-files type :func:`notes_clone` seeds a branch from.

    Handed over as a fixture rather than imported: several test directories are on the
    path at once under one pytest run, so ``conftest`` is not a name a test module can
    safely import by.

    :return: The :class:`PlanFiles` type.
    """
    return PlanFiles


@pytest.fixture
def run_git() -> Callable[..., None]:
    """
    Run one git command in a scratch repository, under a fixed identity.

    :return: The runner, called as ``run_git(directory, *arguments)``.
    """

    def run(working_directory: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=working_directory,
            check=True,
            capture_output=True,
            env=GIT_ENVIRONMENT,
        )

    return run


@pytest.fixture
def notes_clone(tmp_path: Path, run_git) -> Callable[[Mapping[str, PlanFiles]], Path]:
    """
    Build a scratch clone whose default remote carries a notes branch holding the given
    plans, so a test reads real plan data over real git with no network access.

    :param tmp_path: pytest's per-test temporary directory.
    :param run_git: The scratch git runner.
    :return: The builder, called with the plans to seed and returning the clone's root.
    """

    def build(plans: Mapping[str, PlanFiles]) -> Path:
        remote = tmp_path / "remote.git"
        subprocess.run(
            ["git", "init", "--quiet", "--bare", str(remote)],
            check=True,
            capture_output=True,
        )

        seed = tmp_path / "seed"
        seed.mkdir()
        run_git(
            seed, "init", "--quiet", "--initial-branch", NOTES_BRANCH_SETTING.default
        )
        for plan_identifier, files in plans.items():
            plan_directory = seed / PLANS_DIRECTORY / plan_identifier
            plan_directory.mkdir(parents=True)
            (plan_directory / PLAN_MANIFEST_FILENAME).write_text(files.manifest)
            (plan_directory / PLAN_ROADMAP_FILENAME).write_text(files.roadmap)
        run_git(seed, "add", ".")
        run_git(seed, "commit", "--quiet", "--message", "seed the notes branch")
        run_git(seed, "push", "--quiet", str(remote), NOTES_BRANCH_SETTING.default)

        clone = tmp_path / "clone"
        clone.mkdir()
        run_git(clone, "init", "--quiet")
        run_git(clone, "remote", "add", NOTES_REMOTE_SETTING.default, str(remote))
        return clone

    return build


# %% GitHub payloads


@pytest.fixture
def pull_request_payload() -> Callable[..., dict[str, Any]]:
    """
    Build one pull request as GitHub's listing endpoint reports it.

    :return: The builder, called with the number and whichever of the state, draft flag,
        merge timestamp and label names differ from an open, undrafted, unmerged,
        unlabelled pull request.
    """

    def build(
        number: int,
        state: PullRequestState = PullRequestState.OPEN,
        draft: bool = False,
        merged_at: str | None = None,
        labels: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return {
            PullRequestField.NUMBER.value: number,
            PullRequestField.STATE.value: state.value,
            PullRequestField.DRAFT.value: draft,
            PullRequestField.MERGED_AT.value: merged_at,
            PullRequestField.LABELS.value: [
                {LABEL_NAME_FIELD: name} for name in labels
            ],
        }

    return build
