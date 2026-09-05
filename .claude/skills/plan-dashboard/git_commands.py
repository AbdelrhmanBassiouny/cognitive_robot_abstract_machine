#!/usr/bin/env python3
"""
Running git for these scripts, in one place.

Both things this tooling does with git - reading plan data off the personal-notes branch
and publishing the built site to a branch of its own - go through the same runner, so a
command whose failure matters and one whose failure is an ordinary answer are told apart
by which method was called rather than by each caller remembering to check.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from errors import PlanDashboardError

# %% what a finished command reports


@dataclass
class GitCommandFailed(PlanDashboardError):
    """
    Raised when a git command this tooling depends on the result of fails.
    """

    arguments: tuple[str, ...]
    """
    The git subcommand and its arguments, as invoked.
    """

    exit_status: int
    """
    The status git exited with.
    """

    error_output: str
    """
    What git said about it.
    """

    def error_message(self) -> str:
        """:return: The command line, its status, and git's own explanation."""
        return (
            f"git {' '.join(self.arguments)} failed with {self.exit_status}: "
            f"{self.error_output}"
        )


@dataclass(frozen=True)
class GitCommandResult:
    """
    One finished git command, whether or not it succeeded.
    """

    arguments: tuple[str, ...]
    """
    The git subcommand and its arguments, as invoked.
    """

    exit_status: int
    """
    The status git exited with.
    """

    output: str
    """
    Git's standard output, unstripped.
    """

    error_output: str
    """
    Git's standard error, stripped.
    """

    @property
    def succeeded(self) -> bool:
        """:return: Whether git exited zero."""
        return self.exit_status == 0

    def raise_if_failed(self) -> GitCommandResult:
        """
        :raises GitCommandFailed: When the command did not succeed.
        :return: This result, when it did.
        """
        if not self.succeeded:
            raise GitCommandFailed(
                arguments=self.arguments,
                exit_status=self.exit_status,
                error_output=self.error_output,
            )
        return self


# %% running the commands


@dataclass(frozen=True)
class GitCommandRunner:
    """
    Runs git in one checkout, reporting failures rather than swallowing them.
    """

    working_directory: Path
    """
    The checkout every command runs in.
    """

    environment: Mapping[str, str] | None = field(default=None)
    """
    The environment to run under, or ``None`` to inherit this process's own.
    """

    def attempt(self, *arguments: str) -> GitCommandResult:
        """
        Run a command whose failure is an expected outcome.

        :param arguments: The git subcommand and its arguments.
        :return: The finished command.
        """
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.working_directory,
            capture_output=True,
            text=True,
            env=dict(self.environment) if self.environment is not None else None,
        )
        return GitCommandResult(
            arguments=arguments,
            exit_status=completed.returncode,
            output=completed.stdout,
            error_output=completed.stderr.strip(),
        )

    def run(self, *arguments: str) -> str:
        """
        Run a command this tooling depends on the result of.

        :param arguments: The git subcommand and its arguments.
        :raises GitCommandFailed: If git exits non-zero.
        :return: Git's standard output, stripped.
        """
        return self.attempt(*arguments).raise_if_failed().output.strip()

    def output_or_none(self, *arguments: str, strip: bool = True) -> str | None:
        """
        Run a command whose failure means "no answer" - an unset config key, a path the
        reference does not carry.

        :param arguments: The git subcommand and its arguments.
        :param strip: Whether to strip surrounding whitespace, which file content must
            not be: an empty file stays distinguishable from a missing one.
        :return: Git's standard output, or ``None`` if the command failed.
        """
        result = self.attempt(*arguments)
        if not result.succeeded:
            return None
        return result.output.strip() if strip else result.output

    def in_directory(self, working_directory: Path) -> GitCommandRunner:
        """
        :param working_directory: The checkout to run in instead.
        :return: The same runner pointed at it, keeping this one's environment.
        """
        return GitCommandRunner(
            working_directory=working_directory, environment=self.environment
        )
