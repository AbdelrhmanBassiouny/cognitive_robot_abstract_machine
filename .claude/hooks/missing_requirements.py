#!/usr/bin/env python3
"""
Which distributions a requirements file lists that are not installed.

Every script that needs Python dependencies asks this the same way and names none of
them itself: the requirements file is the one place a dependency is written down, so a
dependency added there is checked everywhere without a second list being updated to
match.

Usage:
    python3 missing_requirements.py <requirements-file>

Prints the missing distribution names on one line, empty when nothing is missing.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import ClassVar

COMMENT_MARKER = "#"
"""
What opens a comment in a requirements file, whether or not a requirement precedes it.
"""

SPECIFIER_START = re.compile(r"[<>=!~;\[ ]")
"""
The first character that can follow a distribution name in a requirement, so everything
before it is the name.
"""


@dataclass(frozen=True)
class RequirementsFile:
    """
    A pip requirements file, read for the distributions it asks for.

    Distribution names are taken as the file states them and looked up unchanged, so no
    ``pyyaml``/``yaml``-style mapping between install and import names has to be kept
    anywhere.
    """

    FILENAME: ClassVar[str] = "requirements.txt"
    """
    What such a file is called wherever this repository keeps one, so a caller composing
    a path to one never spells it.
    """

    path: Path
    """
    The file to read.
    """

    def distribution_names(self) -> list[str]:
        """
        Read every distribution the file asks for, in the order it lists them.

        :return: The names, stripped of version specifiers, extras and comments.
        """
        names = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            requirement = line.split(COMMENT_MARKER, 1)[0].strip()
            if not requirement:
                continue
            names.append(SPECIFIER_START.split(requirement, maxsplit=1)[0])
        return names

    def missing(self) -> list[str]:
        """
        Judge every distribution the file asks for against what is installed.

        :return: The names that are not installed, in the order the file lists them -
            empty when every requirement is satisfied.
        """
        return [
            name for name in self.distribution_names() if not self.is_installed(name)
        ]

    @staticmethod
    def is_installed(distribution_name: str) -> bool:
        """
        Whether one distribution is installed for the running interpreter.

        :param distribution_name: The name to look up.
        :return: Whether it resolves to an installed distribution.
        """
        try:
            distribution(distribution_name)
        except PackageNotFoundError:
            return False
        return True


def main() -> int:
    """
    Print the missing distribution names for the requirements file named on the command
    line.

    :return: The process exit code, always zero - this reports, it never refuses.
    """
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} <requirements-file>", file=sys.stderr)
        return 2
    print(" ".join(RequirementsFile(Path(sys.argv[1])).missing()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
