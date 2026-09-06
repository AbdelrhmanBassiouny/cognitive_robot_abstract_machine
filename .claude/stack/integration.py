#!/usr/bin/env python3
"""
Build a personal integration branch: the upstream base plus every reviewed stack tip.

Pull requests are produced faster than the upstream merges them, so a feature that is
finished but unmerged is unusable in daily work, and two in-flight features that
conflict discover it only at the far end of the review queue. This assembles a branch
that holds all of them at once::

    python .claude/stack/integration.py build            # build, then run the suite on it
    python .claude/stack/integration.py build --restack  # bring stale tips forward first
    python .claude/stack/integration.py build --tooling  # only the tips that change this tooling
    python .claude/stack/integration.py build --json     # the build as one document

The branch exists to be built *from*, not to be history. It is regenerated from scratch
on every run, nothing is ever merged out of it, and a conflict found on it is fixed in
the feature branch it belongs to - never here.

Only work its author has reviewed is integrated, which this repository records by the
pull request leaving draft. Read down the whole chain rather than per branch: a tip
contains its stack, so a reviewed branch standing on a draft would bring that draft's
commits in under its own name. Everything left out says so, naming the draft that keeps
it out.

It gates nothing. Promotion asks whether one branch is ready for review against the
upstream; integration asks whether the branches coexist. Gating promotion on a clean
build would hold one branch back because another conflicts with it, with no principled
reason that one is the one to wait.

It detects, attributes and skips; it makes no judgement about what a collision means.
That is ``/integration-conflict-triage``'s, which reads the document this emits.

This module is the command line onto the modules that do the work: selecting what to
build from, assembling it, judging it as a candidate, and saying which pair of branches a
failure only the combination has is about.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from exceptions import GitCommandFailed  # noqa: E402
from stack import (  # noqa: E402
    AmbiguousForkRemoteError,
    ForkRemoteNotFoundError,
    load_configuration,
)

from maintenance_board import MissingPullRequestFieldError  # noqa: E402
from maintenance_git_commands import MaintenanceGitCommandRunner  # noqa: E402
from maintenance_github import (  # noqa: E402
    GitHubCredentialUnavailableError,
    GitHubRequestFailed,
)

from integration_commands import COMMANDS
from integration_exit_codes import IntegrationExitCode
from integration_run import IntegrationRun
from integration_suite import TestCommandNotConfiguredError


def _argument_parser() -> argparse.ArgumentParser:
    """:return: The parser, built from the commands rather than from a list of them."""
    parser = argparse.ArgumentParser(
        prog="integration.py",
        description=(
            "Build a personal integration branch: the upstream base plus every "
            "reviewed in-flight stack tip."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        command.declare_arguments(
            subparsers.add_parser(command.invoked_as, help=command.description)
        )
    return parser


def main() -> IntegrationExitCode:
    """
    Run the command line and say, in words, what its status means.

    :return: The process exit code.
    """
    status = _dispatch()
    if status is not IntegrationExitCode.SUCCESS:
        print(
            f"integration.py: {status.name_for_a_caller} ({int(status)})",
            file=sys.stderr,
        )
    return status


def _dispatch() -> IntegrationExitCode:
    """
    Run the requested command, mapping every refusal to its own status.

    :return: The process exit code.
    """
    arguments = _argument_parser().parse_args()
    requested = next(
        entry for entry in COMMANDS if entry.invoked_as == arguments.command
    )
    try:
        return requested.run(
            IntegrationRun(
                configuration=load_configuration(),
                git=MaintenanceGitCommandRunner(working_directory=Path.cwd()),
            ),
            arguments,
        )
    except (ForkRemoteNotFoundError, AmbiguousForkRemoteError) as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.REMOTES_UNRESOLVED
    except GitHubCredentialUnavailableError as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.CREDENTIAL_UNAVAILABLE
    except (MissingPullRequestFieldError, TestCommandNotConfiguredError) as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.USAGE
    except GitCommandFailed as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.GIT_COMMAND_FAILED
    except GitHubRequestFailed as error:
        print(f"{error}", file=sys.stderr)
        return IntegrationExitCode.GITHUB_REQUEST_FAILED


if __name__ == "__main__":
    sys.exit(main())
