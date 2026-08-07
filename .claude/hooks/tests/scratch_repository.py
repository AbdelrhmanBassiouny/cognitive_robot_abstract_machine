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
from enum import StrEnum
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

SET_UP_CLONE_FIXTURE = Path(__file__).parent / "fixtures" / "set-up-clone"
"""
A checked-in clone layout satisfying every check-setup.sh check that reads a file, laid
out under the same relative paths it will occupy in a scratch project root.
"""


class SetupPrerequisiteFile(StrEnum):
    """
    The files check-setup.sh's ``tooling_files`` check requires, relative to the project
    root.

    Stated here as well as in the fixture tree deliberately. A rename that breaks the
    check then has to be made in both places, rather than the fixture and the tests
    following each other silently and asserting nothing.
    """

    BUILD_DASHBOARD = ".claude/skills/plan-dashboard/build_dashboard.py"
    """
    The dashboard builder the plan-dashboard skill runs.
    """

    REFRESH_DASHBOARD = ".claude/skills/plan-dashboard/refresh_dashboard.sh"
    """
    The refresh entry point the same skill runs.
    """

    DASHBOARD_REQUIREMENTS = ".claude/skills/plan-dashboard/requirements.txt"
    """
    The requirements file check-setup.sh also derives the dependency check from.
    """

    PLAN_SCHEMA = ".claude/skills/plan-dashboard/plan-schema.md"
    """
    The manifest field reference.
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

    def run_git(
        self, *arguments: str, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        """
        Run git in the project root, failing the test if it reports an error.

        :param arguments: The arguments to pass to git.
        :param cwd: Where to run it, defaulting to the project root.
        :return: The finished subprocess.
        """
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd or self.project_root,
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

    def write_setup_prerequisites(self) -> None:
        """
        Write everything check-setup.sh requires of a set up clone, apart from the
        personal-notes branch and CLAUDE.local.md.

        Leaves CLAUDE.local.md out deliberately: session-start.sh writes it, so a test
        of that script must not find it already there - which is why this is a named
        step rather than part of building the repository.
        """
        shutil.copytree(SET_UP_CLONE_FIXTURE, self.project_root, dirs_exist_ok=True)

    def run_hook_script(
        self, script_name: str, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        """
        Run one of the installed hook scripts from the project root.

        Returns the finished process rather than asserting on it, since a hook's exit
        code and stderr are often what a test is about.

        :param script_name: File name within the scratch layout's hooks directory.
        :param arguments: The arguments to pass to the script.
        :return: The finished subprocess.
        """
        return subprocess.run(
            [
                "bash",
                str(self.project_root / ".claude" / "hooks" / script_name),
                *arguments,
            ],
            cwd=self.project_root,
            capture_output=True,
            text=True,
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

    def clone_notes_branch(self, destination: Path) -> Path:
        """
        Check the notes branch out of the notes remote, for asserting against what a
        hook actually pushed rather than what it reported.

        :param destination: Where to put the checkout.
        :return: The checkout's path.
        """
        self.run_git(
            "clone",
            "--quiet",
            "--branch",
            NOTES_BRANCH,
            str(self.notes_remote_path),
            str(destination),
        )
        return destination

    def update_notes_branch_file(self, relative_path: str, content: str) -> None:
        """
        Change one file on the already-published notes branch, the way an edit made from
        another clone would reach it.

        :param relative_path: Path relative to the notes branch's root.
        :param content: The content to commit there.
        """
        checkout = self.project_root.parent / "notes-update-checkout"
        shutil.rmtree(checkout, ignore_errors=True)
        self.clone_notes_branch(checkout)
        self.run_git("config", "user.name", "Scratch Repo", cwd=checkout)
        self.run_git("config", "user.email", "scratch-repo@example.com", cwd=checkout)

        destination = checkout / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        self.run_git("add", relative_path, cwd=checkout)
        self.run_git("commit", "--quiet", "-m", f"Set {relative_path}", cwd=checkout)
        self.run_git("push", "--quiet", "origin", NOTES_BRANCH, cwd=checkout)
        shutil.rmtree(checkout)

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
