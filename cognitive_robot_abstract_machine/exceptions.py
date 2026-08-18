"""
Errors raised while working with the repository checkout itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from krrood.exceptions import DataclassException


@dataclass
class MissingOrmGeneratorError(DataclassException, FileNotFoundError):
    """
    Raised when the script that generates a package's ORM interface is not there.
    """

    package_name: str
    """
    Name of the package whose generator is missing.
    """

    path: Path
    """
    Where the generator was looked for.
    """

    def error_message(self) -> str:
        return f"{self.package_name} has no ORM interface generator at {self.path}."

    def suggest_correction(self) -> str:
        return (
            "Check that this is a complete checkout of the repository and that the "
            "package still generates its ORM interface."
        )


@dataclass
class MissingOrmInterfaceError(DataclassException, FileNotFoundError):
    """
    Raised when the generated ORM interface of a package is not there.
    """

    package_name: str
    """
    Name of the package whose interface is missing.
    """

    path: Path
    """
    Where the interface was looked for.
    """

    def error_message(self) -> str:
        return f"{self.package_name} has no ORM interface at {self.path}."

    def suggest_correction(self) -> str:
        return (
            "The repository tracks this file as an empty placeholder, so restore it "
            "with 'git checkout' before generating it."
        )
