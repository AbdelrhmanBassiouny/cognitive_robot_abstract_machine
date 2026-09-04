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
from git_commands import GitCommandRunner
from github_api import LabelField, PullRequestField
from personal_notes import (
    NOTES_BRANCH_SETTING,
    NOTES_REMOTE_SETTING,
    PLANS_DIRECTORY,
    PlanDocument,
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

SCRATCH_REMOTE_DIRECTORY = "remote.git"
"""
The bare repository a scratch clone's notes remote points at.
"""


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

    def content_of(self, document: PlanDocument) -> str:
        """
        :param document: The document wanted.
        :return: Its source, so a caller reads by document rather than by field name.
        """
        if document is PlanDocument.MANIFEST:
            return self.manifest
        return self.roadmap


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
def scratch_git() -> Callable[[Path], GitCommandRunner]:
    """
    Run git in a scratch repository under a fixed identity.

    The same runner the scripts themselves use, so a test builds its fixtures through
    the code under test rather than through a second way of calling git.

    :return: The factory, called with the directory to run in.
    """

    def runner_in(working_directory: Path) -> GitCommandRunner:
        return GitCommandRunner(
            working_directory=working_directory, environment=GIT_ENVIRONMENT
        )

    return runner_in


@pytest.fixture
def notes_clone(
    tmp_path: Path, scratch_git
) -> Callable[[Mapping[str, PlanFiles]], Path]:
    """
    Build a scratch clone whose default remote carries a notes branch holding the given
    plans, so a test reads real plan data over real git with no network access.

    :param tmp_path: pytest's per-test temporary directory.
    :param scratch_git: The scratch git runner factory.
    :return: The builder, called with the plans to seed and returning the clone's root.
    """

    def build(plans: Mapping[str, PlanFiles]) -> Path:
        remote = tmp_path / SCRATCH_REMOTE_DIRECTORY
        subprocess.run(
            ["git", "init", "--quiet", "--bare", str(remote)],
            check=True,
            capture_output=True,
        )

        seed = tmp_path / "seed"
        seed.mkdir()
        seed_git = scratch_git(seed)
        seed_git.run(
            "init", "--quiet", "--initial-branch", NOTES_BRANCH_SETTING.default
        )
        for plan_identifier, files in plans.items():
            plan_directory = seed / PLANS_DIRECTORY / plan_identifier
            plan_directory.mkdir(parents=True)
            for document in PlanDocument:
                (plan_directory / document).write_text(files.content_of(document))
        seed_git.run("add", ".")
        seed_git.run("commit", "--quiet", "--message", "seed the notes branch")
        seed_git.run("push", "--quiet", str(remote), NOTES_BRANCH_SETTING.default)

        clone = tmp_path / "clone"
        clone.mkdir()
        clone_git = scratch_git(clone)
        clone_git.run("init", "--quiet")
        clone_git.run("remote", "add", NOTES_REMOTE_SETTING.default, str(remote))
        return clone

    return build


# %% GitHub responses


@pytest.fixture
def pull_request_detail() -> Callable[..., dict[str, Any]]:
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
                {LabelField.NAME.value: name} for name in labels
            ],
        }

    return build
