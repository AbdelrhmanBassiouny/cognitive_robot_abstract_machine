#!/usr/bin/env python3
"""
What this package needs installed, and which of it this environment is missing.

The declaration is ``pyproject.toml``'s ``[project] dependencies``, which is where every
package in this repository states them, so there is one list rather than a metadata table
and a requirements file that can disagree.

Kept as a module rather than as a snippet inside the shell that calls it: the bash entry
points ask this question before anything is installed, and a question with parsing in it
is real, testable code wherever it is written.

Usage:
    python3 -m basstler.dependencies [--declaration <pyproject.toml>]

Prints one requirement specifier per missing dependency, and nothing at all when the
environment already has them - which is what a caller passes straight to ``pip install``.

..note:: Imports nothing outside the standard library. It runs before any install, so a
    dependency of its own would be the one thing it could never report.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib.metadata import distributions
from pathlib import Path
from typing import ClassVar


class PyprojectKey(StrEnum):
    """
    The keys of ``pyproject.toml`` this module reads.
    """

    PROJECT = "project"
    """
    The table a package's own metadata lives in.
    """

    DEPENDENCIES = "dependencies"
    """
    The field of that table listing the requirement specifiers.
    """


@dataclass
class UnreadableDependencyDeclarationError(Exception):
    """
    Raised when the declaration cannot be read, so nothing can be said about what is
    missing.

    Distinct from *nothing is missing*, which is what a caller would otherwise conclude
    from an empty answer and act on by installing nothing.
    """

    declaration: Path
    """
    The file that was to be read.
    """

    def __str__(self) -> str:
        """:return: What to tell a reader who asked what is missing and cannot be told."""
        return (
            f"{self.declaration} does not exist, so this package's dependencies cannot "
            f"be read"
        )


@dataclass(frozen=True)
class Dependency:
    """
    One requirement this package declares.
    """

    CONSTRAINT_START: ClassVar[re.Pattern[str]] = re.compile(r"[<>=!~;\[ ]")
    """
    The first character that ends a distribution's name and begins a version bound, an extra
    or an environment marker.
    """

    NAME_SEPARATORS: ClassVar[re.Pattern[str]] = re.compile(r"[-_.]+")
    """
    The characters a distribution name may be spelled with interchangeably, per PEP 503.
    """

    specifier: str
    """
    The requirement as ``pyproject.toml`` writes it, version bounds and all.
    """

    @classmethod
    def canonical_name(cls, distribution_name: str) -> str:
        """
        :param distribution_name: A distribution's name as anyone spells it.
        :return: The one spelling ``PyYAML``, ``pyyaml`` and ``py-yaml`` share.
        """
        return cls.NAME_SEPARATORS.sub("-", distribution_name).lower()

    @classmethod
    @cache
    def installed_distribution_names(cls) -> frozenset[str]:
        """
        Read once per process: nothing installs into the environment while it runs.

        :return: The canonical name of every distribution installed in this environment.
        """
        return frozenset(
            cls.canonical_name(installed.metadata["Name"])
            for installed in distributions()
            if installed.metadata["Name"]
        )

    @property
    def distribution_name(self) -> str:
        """:return: The distribution this requirement names, without its constraints."""
        return self.CONSTRAINT_START.split(self.specifier, maxsplit=1)[0].strip()

    @property
    def is_missing(self) -> bool:
        """
        Presence rather than version: an installed distribution is left alone, which is
        what lets a session start run this on every start and install nothing.

        :return: Whether this environment has no distribution of that name.
        """
        return (
            self.canonical_name(self.distribution_name)
            not in self.installed_distribution_names()
        )


@dataclass(frozen=True)
class DependencyDeclaration:
    """
    A ``pyproject.toml`` and the dependencies it declares.
    """

    FILE_NAME: ClassVar[str] = "pyproject.toml"
    """
    The file a package's own metadata is declared in.
    """

    path: Path
    """
    The ``pyproject.toml`` to read.
    """

    @classmethod
    def of_this_package(cls) -> DependencyDeclaration:
        """
        :return: This package's own metadata, found beside the modules it declares the
            dependencies of.
        """
        return cls(Path(__file__).with_name(cls.FILE_NAME))

    def dependencies(self) -> tuple[Dependency, ...]:
        """
        :return: Every dependency it declares, in the order it declares them.
        :raises UnreadableDependencyDeclarationError: If the file is absent.
        """
        if not self.path.is_file():
            raise UnreadableDependencyDeclarationError(self.path)
        project = tomllib.loads(self.path.read_text(encoding="utf-8"))
        return tuple(
            Dependency(specifier)
            for specifier in project[PyprojectKey.PROJECT].get(
                PyprojectKey.DEPENDENCIES, []
            )
        )

    def missing(self) -> tuple[Dependency, ...]:
        """
        :return: The declared dependencies this environment does not have.
        :raises UnreadableDependencyDeclarationError: If the file is absent.
        """
        return tuple(
            dependency for dependency in self.dependencies() if dependency.is_missing
        )


def main() -> None:
    """
    Print one specifier per missing dependency, for a caller to hand to an installer.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--declaration",
        type=Path,
        default=DependencyDeclaration.of_this_package().path,
        help="The pyproject.toml to read the dependencies from",
    )
    declaration = DependencyDeclaration(parser.parse_args().declaration)
    if not declaration.path.is_file():
        sys.exit(str(UnreadableDependencyDeclarationError(declaration.path)))
    for dependency in declaration.missing():
        print(dependency.specifier)


if __name__ == "__main__":
    main()
