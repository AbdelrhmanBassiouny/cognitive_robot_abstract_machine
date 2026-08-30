"""
Calling github-api.sh from a test, and the GitHub vocabulary those calls are made in.

The script is sourced rather than executed, so a call is a shell function name and its
arguments. Naming the functions and running them through one runner keeps a test from
composing a shell program in an f-string, the same way the maintenance pass reaches git
through a runner rather than spelling command lines.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from scratch_repository import HOOKS_SOURCE_DIRECTORY
from stub_executables import StubbedExecutable, StubExecutableDirectory
from tooling_files import HookScript

# %% the vocabulary


class GitHubApiCall(StrEnum):
    """
    The shell functions github-api.sh defines, named for what each answers.
    """

    AUTHENTICATED_LOGIN = "github_authenticated_login"
    """
    Who the available credentials belong to.
    """

    REPOSITORY_OF_REMOTE = "github_repository_of_remote"
    """
    The ``owner/repo`` a remote name or URL refers to.
    """

    LABEL_EXISTS = "github_repository_has_label"
    """
    Whether a repository already carries a label, as an exit status.
    """

    CREATE_LABEL = "github_create_label"
    """
    Creates a label, reporting the API's own refusal rather than claiming it acted.
    """


class PullRequestLabel(StrEnum):
    """
    The labels this tooling reads and applies.

    Held equal to ``PULL_REQUEST_LABELS`` in ``resolve-personal-notes-config.sh``, which
    is where the shell reads them from, by
    :func:`test_github_api_sh.test_the_labels_match_the_ones_the_shell_declares`.
    """

    MERGED = "merged"
    """
    The changes landed even though GitHub never recorded a merge.
    """

    BUG = "bug"
    """
    Fixes incorrect behaviour.
    """

    IN_REVIEW = "in-review"
    """
    Promoted upstream and waiting on review.
    """


class GitHubRemoteUrl(StrEnum):
    """
    The spellings of a remote URL ``github_repository_of_remote`` has to read an
    ``owner/repo`` out of, each stated once as a format.

    A member's value is a format string taking the repository, so a test names the case
    it exercises rather than rebuilding the URL.
    """

    HTTPS = "https://github.com/{repository}"
    """
    What GitHub's own clone button offers.
    """

    HTTPS_WITH_SUFFIX = "https://github.com/{repository}.git"
    """
    The same, carrying git's optional suffix.
    """

    SCP_STYLE_SSH = "git@github.com:{repository}.git"
    """
    The abbreviated ssh spelling, whose separator is a colon rather than a slash.
    """

    SSH = "ssh://git@github.com/{repository}.git"
    """
    The full ssh URL.
    """

    CLOUD_SESSION_PROXY = "http://local_proxy@127.0.0.1:41729/git/{repository}"
    """
    A Claude Code cloud session's clone, rewritten through its local git proxy - no
    ``github.com`` host anywhere in it, which is why the parser reads trailing path
    segments instead of matching a host.
    """

    def for_repository(self, repository: str) -> str:
        """
        This spelling of one repository's remote URL.

        :param repository: The ``owner/repo`` to address.
        :return: The URL.
        """
        return self.value.format(repository=repository)


# %% making a call


@dataclass(frozen=True)
class GitHubApiRunner:
    """
    Runs one github-api.sh call against the stubbed ``PATH``.
    """

    stub_executables: StubExecutableDirectory
    """
    The stub directory the call resolves ``gh`` and ``curl`` from.
    """

    working_directory: Path
    """
    Where to run, which matters only for the calls that consult git.
    """

    script: Path = HOOKS_SOURCE_DIRECTORY / HookScript.GITHUB_API.value
    """
    The script under test, sourced directly - it resolves no repository paths of its
    own, so it needs no scratch layout.
    """

    def run(
        self,
        call: GitHubApiCall,
        *arguments: str,
        hidden_executables: tuple[StubbedExecutable, ...] = (),
        **environment_overrides: str,
    ) -> subprocess.CompletedProcess[str]:
        """
        Source the script and make one call.

        :param call: The function to call.
        :param arguments: That function's arguments, in order.
        :param hidden_executables: Executables to make unfindable for this run.
        :param environment_overrides: Variables to set, chiefly the stubs' ``STUB_*``
            controls.
        :return: The finished subprocess.
        """
        return subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; shift; "$@"',
                "_",
                str(self.script),
                call.value,
                *arguments,
            ],
            cwd=self.working_directory,
            capture_output=True,
            text=True,
            env=self.stub_executables.subprocess_environment(
                hidden_executables=hidden_executables, **environment_overrides
            ),
        )
