"""
Performs the one-time personal-notes setup non-interactively: points the notes remote at a
repository you own, creates the notes branch, optionally seeds it and records your git
identity, picks the notes up in this clone, and checks the pull request labels the tooling
applies.

Safe to re-run: each step is skipped when check-setup.sh already reports it done. Exits with
check-setup.sh's own final status, so a setup that only half worked never reports success.
Nothing here needs a Claude Code session.

Usage:
    python3 -m basstler.setup_personal_notes --remote <name-or-url> \\
        [--name "Your Name" --email you@example.com] [--starter-notes] [--create-labels]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from basstler.locations import HookScript, PackageLocation, ProjectLocation
from basstler.maintenance_github import (
    GitHubConnection,
    GitHubRepository,
    GitHubRequestFailed,
)
from basstler.repository import Repository
from basstler.repository_label import RepositoryLabel
from basstler.setup_report import CheckStatus, SetupCheck, SetupReport
from basstler.setup_steps import PersonalNotesSetting, git_value
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

PULL_REQUEST_REMOTE = "origin"
"""
The remote naming the repository pull requests are opened against, which is where the
labels have to exist.
"""

STARTER_NOTES_MESSAGE = "Initialize personal notes from the starter template"
"""
The commit message the notes file is seeded with.
"""


class ExitCode(IntEnum):
    """
    The process statuses this command exits with.

    The first two are check-setup.sh's own, which a completed run passes on; ``argparse``
    supplies 2 for a usage error.
    """

    SET_UP = 0
    """
    The run finished and check-setup.sh reports nothing left to do.
    """

    SETUP_INCOMPLETE = 1
    """
    The run finished and check-setup.sh still reports something to set up.
    """

    FOREIGN_NOTES_REMOTE = 3
    """
    The notes remote belongs to somebody else, so nothing was written.
    """

    HOOK_SCRIPT_FAILED = 4
    """
    One of the hook scripts a step runs failed.
    """

    GITHUB_REFUSED = 5
    """
    GitHub refused a call the run depended on.
    """


# %% what the run was asked to do


@dataclass(frozen=True)
class GitIdentity:
    """
    The name and email every clone's commits are authored with.
    """

    name: str
    """
    The value of ``user.name``.
    """

    email: str
    """
    The value of ``user.email``.
    """


@dataclass(frozen=True)
class SetupRequest:
    """
    What one run is asked to set up.
    """

    remote: str
    """
    The remote the notes belong on, as a remote name in this clone or a raw URL.
    """

    identity: GitIdentity | None
    """
    The identity to record on the notes branch, or ``None`` to record none.
    """

    starter_notes: bool
    """
    Whether to seed the notes file from the starter template.
    """

    create_labels: bool
    """
    Whether to create the labels the repository is missing, rather than only report them.
    """

    @classmethod
    def from_arguments(cls, arguments: Sequence[str]) -> SetupRequest:
        """
        Read a request from the command line.

        :param arguments: The command line, without the program name.
        :return: The request.
        """
        parser = argparse.ArgumentParser(
            prog=f"python3 -m {__name__}", description=__doc__.split("\n\n")[0]
        )
        parser.add_argument(
            "--remote",
            required=True,
            help="The remote your notes belong on. Required rather than guessed: a "
            "wrong guess pushes them to a repository you may not own.",
        )
        parser.add_argument("--name", help="The name your commits should carry.")
        parser.add_argument("--email", help="The email your commits should carry.")
        parser.add_argument(
            "--starter-notes",
            action="store_true",
            help="Seed a new notes file from the starter template.",
        )
        parser.add_argument(
            "--create-labels",
            action="store_true",
            help="Create the labels the repository is missing. Off by default, since "
            "labels are visible to everyone who can see the repository.",
        )
        parsed = parser.parse_args(arguments)
        if bool(parsed.name) != bool(parsed.email):
            parser.error("--name and --email go together: a commit needs both.")
        identity = GitIdentity(parsed.name, parsed.email) if parsed.name else None
        return cls(
            remote=parsed.remote,
            identity=identity,
            starter_notes=parsed.starter_notes,
            create_labels=parsed.create_labels,
        )


# %% why a run stops


@dataclass
class SetupError(Exception, ABC):
    """
    A reason the setup stops before it finishes.
    """

    @property
    @abstractmethod
    def exit_code(self) -> ExitCode:
        """:return: The status the command exits with."""


@dataclass
class ForeignNotesRemoteError(SetupError):
    """
    Raised when GitHub says the notes remote belongs to somebody other than the caller.
    """

    repository: Repository
    """
    The repository the notes remote names.
    """

    login: str
    """
    Who the available credential belongs to.
    """

    @property
    def exit_code(self) -> ExitCode:
        """See :attr:`SetupError.exit_code`."""
        return ExitCode.FOREIGN_NOTES_REMOTE

    def __str__(self) -> str:
        """:return: Whose the repository is, and what to pass instead."""
        return (
            f"Refusing to set up personal notes on '{self.repository}': it is owned by "
            f"'{self.repository.owner}', but you are authenticated as '{self.login}'. "
            f"Pass --remote for your own fork instead."
        )


@dataclass
class HookScriptFailedError(SetupError):
    """
    Raised when a hook script a step runs exits with a failure.
    """

    script: HookScript
    """
    The script that failed.
    """

    status: int
    """
    The status it exited with.
    """

    @property
    def exit_code(self) -> ExitCode:
        """See :attr:`SetupError.exit_code`."""
        return ExitCode.HOOK_SCRIPT_FAILED

    def __str__(self) -> str:
        """:return: Which script failed, and how."""
        return f"{self.script} exited with status {self.status}; its output says why."


# %% the run


@dataclass(frozen=True)
class PersonalNotesSetup:
    """
    One setup run against one clone, in the order the steps depend on each other.
    """

    project_root: Path
    """
    The clone being set up.
    """

    environment: Mapping[str, str]
    """
    The environment the hook scripts run in and the settings resolve from.
    """

    request: SetupRequest
    """
    What the run was asked to do.
    """

    connection: GitHubConnection | None
    """
    Access to GitHub, or ``None`` when no credential is available - which leaves the
    owner and the labels unchecked rather than stopping the run.
    """

    def run(self) -> ExitCode:
        """
        Perform every step, then report what is true now.

        :return: check-setup.sh's final status.
        :raises SetupError: If a step cannot be completed.
        :raises GitHubRequestFailed: If GitHub refuses a call a step depends on.
        """
        self.verify_notes_remote_owner()
        self.point_notes_remote()
        report = self.setup_report()
        self.create_notes_branch(report)
        self.seed_notes()
        self.record_identity()
        self.run_hook_script(HookScript.SESSION_START)
        self.check_labels()
        logger.info("\nSetup complete. Final check:")
        final = self.run_check_setup()
        logger.info(final.stdout.rstrip("\n"))
        return ExitCode(final.returncode)

    def verify_notes_remote_owner(self) -> None:
        """
        Refuse a notes remote GitHub positively says is somebody else's.

        Anything less certain - a remote naming no repository, no credential - is
        reported and allowed, since ``--remote`` named it explicitly.

        :raises ForeignNotesRemoteError: If the remote's owner is not the caller.
        """
        remote_url = (
            git_value(self.project_root, "remote", "get-url", self.request.remote)
            or self.request.remote
        )
        if not Repository.names_a_repository(remote_url):
            logger.info(
                f"Could not tell which GitHub repository '{self.request.remote}' is, so "
                f"its owner was not verified."
            )
            return
        repository = Repository.from_remote_url(remote_url)
        if self.connection is None:
            logger.info(
                f"Could not verify that '{repository.owner}' is you: no GitHub "
                f"credentials available. Continuing, since --remote named it."
            )
            return
        login = self.connection.authenticated_login()
        if repository.owner != login:
            raise ForeignNotesRemoteError(repository, login)
        logger.info(f"Notes remote '{repository}' is owned by '{login}'.")

    def point_notes_remote(self) -> None:
        """
        Record the chosen remote in this clone's git config, where every hook reads it.
        """
        subprocess.run(
            [
                "git",
                "config",
                PersonalNotesSetting.REMOTE.git_config_key,
                self.request.remote,
            ],
            cwd=self.project_root,
            check=True,
        )
        logger.info(f"Notes remote set to '{self.request.remote}'.")

    def create_notes_branch(self, report: SetupReport) -> None:
        """
        Create the notes branch unless check-setup.sh already found it.

        :param report: check-setup.sh's report from before any step ran.
        """
        if (
            report.results[SetupCheck.NOTES_BRANCH].status
            is not CheckStatus.NEEDS_SETUP
        ):
            logger.info("Notes branch already exists - left untouched.")
            return
        self.run_hook_script(HookScript.CREATE_NOTES_BRANCH)

    def seed_notes(self) -> None:
        """
        Seed the notes file from the starter template, when asked to.
        """
        notes_path = PersonalNotesSetting.PATH.resolve(
            self.project_root, self.environment
        )
        if not self.request.starter_notes:
            logger.info(
                f"Left '{notes_path}' as it is - pass --starter-notes to seed it from "
                f"the template."
            )
            return
        self.run_hook_script(
            HookScript.WRITE_NOTES_FILE,
            "--source",
            str(ProjectLocation.STARTER_NOTES),
            "--destination",
            notes_path,
            "--message",
            STARTER_NOTES_MESSAGE,
        )

    def record_identity(self) -> None:
        """
        Record the identity on the notes branch, when given one.

        Given none, nothing is recorded and the final report says so.
        """
        if self.request.identity is None:
            return
        self.run_hook_script(
            HookScript.SAVE_GIT_IDENTITY,
            "--name",
            self.request.identity.name,
            "--email",
            self.request.identity.email,
        )

    def check_labels(self) -> None:
        """
        Report which labels the pull-request repository lacks, and create them when
        asked to.

        Never stops the run: a missing label blocks nothing else in the setup.
        """
        remote_url = git_value(
            self.project_root, "remote", "get-url", PULL_REQUEST_REMOTE
        )
        if remote_url is None or not Repository.names_a_repository(remote_url):
            logger.info(
                f"Skipped the label check: could not tell which repository "
                f"'{PULL_REQUEST_REMOTE}' refers to."
            )
            return
        repository = Repository.from_remote_url(remote_url)
        if self.connection is None:
            logger.info(
                f"Skipped the label check on '{repository}': no GitHub credentials "
                f"available."
            )
            return
        labels = GitHubRepository(repository, self.connection)
        present = labels.labels()
        missing = [label for label in RepositoryLabel if label not in present]
        if not missing:
            logger.info(f"Every label this tooling uses is present on '{repository}'.")
            return
        logger.info(f"Missing labels on '{repository}': {' '.join(missing)}")
        if not self.request.create_labels:
            logger.info("Not creating them - re-run with --create-labels to do so.")
            return
        for label in missing:
            labels.create_label(label)
            logger.info(f"Created '{label}' on '{repository}'.")

    def setup_report(self) -> SetupReport:
        """:return: What check-setup.sh reports right now."""
        return SetupReport.from_completed_process(self.run_check_setup())

    def run_check_setup(self) -> subprocess.CompletedProcess[str]:
        """
        Run check-setup.sh, whose non-zero status means only that something still needs
        setting up.

        :return: The finished process, with its report captured.
        """
        return subprocess.run(
            ["bash", str(self.project_root / HookScript.CHECK_SETUP.path)],
            cwd=self.project_root,
            env=dict(self.environment),
            capture_output=True,
            text=True,
        )

    def run_hook_script(self, script: HookScript, *arguments: str) -> None:
        """
        Run one hook script, its output going straight to this process's own.

        :param script: The script to run.
        :param arguments: Its arguments.
        :raises HookScriptFailedError: If it exits with a failure.
        """
        completed = subprocess.run(
            ["bash", str(self.project_root / script.path), *arguments],
            cwd=self.project_root,
            env=dict(self.environment),
        )
        if completed.returncode != 0:
            raise HookScriptFailedError(script, completed.returncode)


def main() -> ExitCode:
    """
    Set up this clone as the command line asks, and report the result.
    """
    request = SetupRequest.from_arguments(sys.argv[1:])
    setup = PersonalNotesSetup(
        project_root=PackageLocation.REPOSITORY_ROOT.value,
        environment=os.environ,
        request=request,
        connection=GitHubConnection.from_environment(os.environ),
    )
    try:
        return setup.run()
    except SetupError as error:
        logger.error(str(error))
        return error.exit_code
    except GitHubRequestFailed as error:
        logger.error(str(error))
        return ExitCode.GITHUB_REFUSED


if __name__ == "__main__":
    sys.exit(main())
