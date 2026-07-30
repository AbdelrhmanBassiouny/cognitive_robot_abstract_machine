"""
The throwaway git repository the hook integration tests run against.

Every hook in this directory reads git config, fetches a personal-notes branch, or
pushes to one, so testing any of them needs a real repository with a real remote. Both
are built locally here - a project root, and a bare repository standing in for the
notes remote - so no test needs network access or a real personal-notes branch.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import plan_manifest_tools

HOOKS_SOURCE_DIRECTORY = Path(plan_manifest_tools.__file__).parent
"""
The real hooks directory the scripts under test are copied from.
"""

NOTES_BRANCH = "claude/personal-notes"
"""
The personal-notes branch name the hooks resolve to by default.
"""

WORK_BRANCH = "some-work-branch"
"""
The throwaway branch a scratch repository is left checked out on.
"""


def initialize_bare_repository(path: Path) -> Path:
    """
    Create an empty bare repository, usable as a git remote.

    :param path: Where to create it.
    :return: The same path, for passing to git as a remote.
    """
    subprocess.run(
        ["git", "init", "--quiet", "--bare", str(path)],
        check=True,
        capture_output=True,
    )
    return path


@dataclass
class ScratchRepository:
    """
    A scratch project root, a bare repository standing in for its notes remote, and the
    git operations the hook tests perform on the pair.
    """

    project_root: Path
    """
    The working clone the hook scripts under test are run against.
    """

    notes_remote_path: Path
    """
    The bare repository the notes branch is pushed to and fetched from.
    """

    @classmethod
    def create(cls, parent_directory: Path) -> ScratchRepository:
        """
        Build a scratch repository with git initialized and its notes remote created,
        but nothing committed yet.

        :param parent_directory: Where to put the project root and the notes remote,
            typically pytest's per-test temporary directory.
        :return: The new scratch repository.
        """
        project_root = parent_directory / "project"
        (project_root / ".claude" / "hooks").mkdir(parents=True)
        repository = cls(
            project_root,
            initialize_bare_repository(parent_directory / "personal-notes.git"),
        )
        repository.run_git("init", "--quiet")
        # A CI runner has no ambient git identity configured - set one locally so
        # committing here doesn't depend on the environment already having one.
        repository.run_git("config", "user.name", "Scratch Repo")
        repository.run_git("config", "user.email", "scratch-repo@example.com")
        return repository

    def run_git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """
        Run git in the project root, failing the test if it reports an error.

        :param arguments: The arguments to pass to git.
        :return: The finished subprocess.
        """
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return result

    def install_hook_scripts(self, *script_names: str) -> None:
        """
        Copy the real hook scripts under test into the scratch layout.

        :param script_names: File names within the hooks directory.
        """
        for script_name in script_names:
            shutil.copy(
                HOOKS_SOURCE_DIRECTORY / script_name,
                self.project_root / ".claude" / "hooks" / script_name,
            )

    def write(self, relative_path: str, content: str) -> Path:
        """
        Write a file in the project root, creating any missing parent directories.

        :param relative_path: Path relative to the project root.
        :param content: The file's contents.
        :return: The path written to.
        """
        destination = self.project_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        return destination

    def commit_everything(self, message: str) -> None:
        """
        Stage every change in the project root and commit it.

        :param message: The commit message.
        """
        self.run_git("add", "--all")
        self.run_git("commit", "--quiet", "-m", message)

    def publish_notes_branch(self, files: Mapping[str, str]) -> None:
        """
        Push *files* to the notes branch on the notes remote, then leave the repository
        on a work branch that does not carry them.

        Keeping them off the work branch matches how the hooks are really used: notes
        exist only on the notes branch, and are fetched rather than checked out.

        :param files: File contents, keyed by path relative to the project root.
        """
        self.run_git("checkout", "--quiet", "-b", NOTES_BRANCH)
        for relative_path, content in files.items():
            self.write(relative_path, content)
        self.commit_everything("bootstrap personal-notes")
        self.run_git("push", "--quiet", str(self.notes_remote_path), NOTES_BRANCH)

        self.run_git("checkout", "--quiet", "-b", WORK_BRANCH)
        for relative_path in files:
            (self.project_root / relative_path).unlink()
        self.commit_everything("drop the notes from the work branch")

    def clone_branch(self, remote: Path, branch: str, destination: Path) -> Path:
        """
        Check a branch out of a remote, for asserting against what a hook actually
        pushed rather than what it reported.

        :param remote: The remote holding the branch.
        :param branch: The branch to check out.
        :param destination: Where to put the checkout.
        :return: The checkout's path.
        """
        self.run_git(
            "clone", "--quiet", "--branch", branch, str(remote), str(destination)
        )
        return destination

    def clone_notes_branch(self, destination: Path) -> Path:
        """
        Check the notes branch out of the notes remote.

        :param destination: Where to put the checkout.
        :return: The checkout's path.
        """
        return self.clone_branch(self.notes_remote_path, NOTES_BRANCH, destination)

    def remote_branch_commit(self, remote: Path, branch: str) -> str | None:
        """
        Read the commit a branch points at on a remote, for asserting that a re-run
        pushed nothing rather than trusting it said so.

        :param remote: The remote to look the branch up on.
        :param branch: The branch to resolve.
        :return: The commit hash, or ``None`` if the branch isn't on the remote at all.
        """
        result = subprocess.run(
            ["git", "ls-remote", str(remote), branch],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        if not result.stdout.strip():
            return None
        return result.stdout.split()[0]

    def notes_branch_commit(self) -> str | None:
        """
        Read the commit the notes branch points at on the notes remote.

        :return: The commit hash, or ``None`` if the branch isn't on the remote at all.
        """
        return self.remote_branch_commit(self.notes_remote_path, NOTES_BRANCH)

    def resolve_notes_remote_to(self, remote: Path | None = None) -> None:
        """
        Point the personal-notes remote at *remote* through local git config.

        :param remote: The remote the hooks should resolve to, defaulting to this
            repository's own notes remote.
        """
        self.run_git(
            "config",
            "claude.personalNotesRemote",
            str(self.notes_remote_path if remote is None else remote),
        )
