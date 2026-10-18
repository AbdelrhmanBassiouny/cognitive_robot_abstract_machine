"""
The ``cram-development-tools`` command.
"""

from __future__ import annotations

import argparse
import logging
import sys
from enum import IntEnum, StrEnum
from pathlib import Path

from typing_extensions import Sequence

from cram_development_tools.agents_instructions import AgentsInstructions
from cram_development_tools.docstring_formatting import DocstringFormatter

logger = logging.getLogger(__name__)


# %% command line vocabulary


class Subcommand(StrEnum):
    """
    The subcommands of ``cram-development-tools``.
    """

    FORMAT = "format"
    """
    Format Python files with black and docformatter.
    """

    AGENTS_MD = "agents-md"
    """
    Generate the repository's ``AGENTS.md``.
    """


class Option(StrEnum):
    """
    The command line options of the subcommands.
    """

    CHECK = "--check"
    """
    Verify a generated file instead of writing it.
    """


class ExitStatus(IntEnum):
    """
    The exit status of a subcommand, following pre-commit's convention for hooks.
    """

    SUCCESS = 0
    """
    Nothing had to change.
    """

    FAILURE = 1
    """
    Files were modified, or a checked file is stale.
    """


# %% subcommands


def format_files(arguments: argparse.Namespace) -> ExitStatus:
    """
    Format the files named on the command line.

    :param arguments: The parsed command line.
    :return: :attr:`ExitStatus.FAILURE` if any file was modified.
    """
    if DocstringFormatter().format_files(arguments.files):
        return ExitStatus.FAILURE
    return ExitStatus.SUCCESS


def generate_agents_instructions(arguments: argparse.Namespace) -> ExitStatus:
    """
    Write, or with :attr:`Option.CHECK` verify, the ``AGENTS.md`` of the current directory.

    :param arguments: The parsed command line.
    :return: :attr:`ExitStatus.FAILURE` if the file was rewritten or is stale.
    """
    instructions = AgentsInstructions(Path.cwd())
    if arguments.check:
        if instructions.is_current():
            return ExitStatus.SUCCESS
        logger.error(
            "%s is out of date; run `cram-development-tools %s` to regenerate it",
            instructions.generated_path.name,
            Subcommand.AGENTS_MD,
        )
        return ExitStatus.FAILURE
    if instructions.write():
        logger.info("Wrote %s", instructions.generated_path.name)
        return ExitStatus.FAILURE
    return ExitStatus.SUCCESS


def build_parser() -> argparse.ArgumentParser:
    """
    :return: The parser for the ``cram-development-tools`` command line.
    """
    parser = argparse.ArgumentParser(prog="cram-development-tools")
    subparsers = parser.add_subparsers(required=True)

    format_parser = subparsers.add_parser(
        Subcommand.FORMAT,
        help="Format Python files with black, then docformatter where they agree.",
    )
    format_parser.add_argument("files", nargs="*", type=Path)
    format_parser.set_defaults(run=format_files)

    agents_parser = subparsers.add_parser(
        Subcommand.AGENTS_MD,
        help="Generate AGENTS.md from the packaged rules and AGENTS.project.md.",
    )
    agents_parser.add_argument(
        Option.CHECK,
        action="store_true",
        help="Only verify that AGENTS.md is up to date; exit non-zero if it is not.",
    )
    agents_parser.set_defaults(run=generate_agents_instructions)

    return parser


def main(command_line: Sequence[str] | None = None) -> int:
    """
    Run the subcommand the command line names.

    :param command_line: The arguments after the program name; the process's own when
        omitted.
    :return: The subcommand's exit status.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = build_parser().parse_args(command_line)
    return arguments.run(arguments)


if __name__ == "__main__":
    sys.exit(main())
