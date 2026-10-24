"""
The ``krrood`` command.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from functools import cached_property
from pathlib import Path

from typing_extensions import Sequence

from krrood.development_tools.agent_instructions import (
    AgentsInstructions,
    RepositoryInstructionsFile,
    RuleSet,
)
from krrood.development_tools.formatting import DocstringFormatter

logger = logging.getLogger(__name__)


# %% command line vocabulary


class Subcommand(StrEnum):
    """
    The subcommands of ``krrood``.
    """

    FORMAT = "format"
    """
    Format Python files with ruff and docformatter.
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

    RULE_SETS = "--rule-sets"
    """
    Choose the rule sets a generated ``AGENTS.md`` contains.
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


# %% command line


@dataclass
class CommandLine:
    """
    The ``krrood`` command line: its subcommands, their arguments and running the one a
    command line names.
    """

    program_name: str = "krrood"
    """
    The name the command is invoked by.
    """

    @classmethod
    def main(cls, command_line: Sequence[str] | None = None) -> int:
        """
        Run the subcommand the command line names.

        :param command_line: The arguments after the program name; the process's own when
            omitted.
        :return: The subcommand's exit status.
        """
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        interface = cls()
        arguments = interface.parser.parse_args(command_line)
        return arguments.run(arguments)

    @cached_property
    def parser(self) -> argparse.ArgumentParser:
        """
        The parser for every subcommand, each bound to the method that runs it.
        """
        parser = argparse.ArgumentParser(prog=self.program_name)
        subparsers = parser.add_subparsers(required=True)

        format_parser = subparsers.add_parser(
            Subcommand.FORMAT,
            help="Format Python files with ruff, then docformatter where they agree.",
        )
        format_parser.add_argument("files", nargs="*", type=Path)
        format_parser.set_defaults(run=self.format_files)

        agents_parser = subparsers.add_parser(
            Subcommand.AGENTS_MD,
            help="Generate AGENTS.md from the shared rules and AGENTS.project.md.",
        )
        agents_parser.add_argument(
            Option.CHECK,
            action="store_true",
            help="Only verify that AGENTS.md is up to date; exit non-zero if it is not.",
        )
        agents_parser.add_argument(
            Option.RULE_SETS,
            nargs="+",
            type=RuleSet,
            choices=list(RuleSet),
            default=list(RuleSet),
            help="The rule sets AGENTS.md contains; all of them when omitted.",
        )
        agents_parser.set_defaults(run=self.generate_agents_instructions)

        return parser

    def format_files(self, arguments: argparse.Namespace) -> ExitStatus:
        """
        Format the files named on the command line.

        :param arguments: The parsed command line.
        :return: :attr:`ExitStatus.FAILURE` if any file was modified.
        """
        if DocstringFormatter().format_files(arguments.files):
            return ExitStatus.FAILURE
        return ExitStatus.SUCCESS

    def generate_agents_instructions(self, arguments: argparse.Namespace) -> ExitStatus:
        """
        Write, or with :attr:`Option.CHECK` verify, the ``AGENTS.md`` of the current
        directory.

        :param arguments: The parsed command line.
        :return: :attr:`ExitStatus.FAILURE` if the file was rewritten or is stale.
        """
        rule_sets = tuple(
            rule_set for rule_set in RuleSet if rule_set in arguments.rule_sets
        )
        instructions = AgentsInstructions(Path.cwd(), rule_sets)
        if arguments.check:
            if instructions.is_current():
                return ExitStatus.SUCCESS
            logger.error(
                "%s is out of date. Never edit it by hand: write this repository's own "
                "rules in %s and change a shared rule in its file under %s, then run "
                "`%s %s`.",
                RepositoryInstructionsFile.GENERATED,
                RepositoryInstructionsFile.PROJECT,
                instructions.rules_directory,
                self.program_name,
                Subcommand.AGENTS_MD,
            )
            return ExitStatus.FAILURE
        if instructions.write():
            logger.info("Wrote %s", instructions.generated_path.name)
            return ExitStatus.FAILURE
        return ExitStatus.SUCCESS


if __name__ == "__main__":
    sys.exit(CommandLine.main())
