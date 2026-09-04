#!/usr/bin/env python3
"""
The command line each of these scripts takes, declared as options rather than strings.

Every script names its own options as a ``StrEnum``, and adds them here: the flag is
then spelled once, in the enum, and the attribute a parsed run is read back through
follows from it rather than from a second spelling in the parser call.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import StrEnum

OPTION_PREFIX = "--"
"""
What marks an option on the command line, and what is stripped to derive its attribute.
"""


@dataclass
class ScriptArgumentParser:
    """
    One script's command line.
    """

    description: str
    """
    What the script does, shown by ``--help``. The module docstring, normally.
    """

    parser: argparse.ArgumentParser = field(init=False)
    """
    The parser the options are added to.
    """

    def __post_init__(self) -> None:
        """Build the parser, keeping the description's own line breaks."""
        self.parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

    def add(
        self, option: StrEnum, help_text: str, default: str | None = None
    ) -> ScriptArgumentParser:
        """
        Declare one option.

        :param option: The option, whose value is its flag.
        :param help_text: What it is for.
        :param default: What it stands for when unnamed; required without one.
        :return: This parser, so declarations chain.
        """
        self.parser.add_argument(
            str(option),
            dest=self.attribute_of(option),
            required=default is None,
            default=default,
            help=help_text,
        )
        return self

    def parse(self) -> argparse.Namespace:
        """:return: The parsed command line."""
        return self.parser.parse_args()

    @staticmethod
    def attribute_of(option: StrEnum) -> str:
        """
        :param option: The option to read back.
        :return: The attribute a parsed run carries it under.
        """
        return str(option).removeprefix(OPTION_PREFIX).replace("-", "_")
