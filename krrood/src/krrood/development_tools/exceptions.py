"""
Exceptions raised by the development tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from krrood.exceptions import DataclassException


@dataclass
class FormatterNotInstalled(DataclassException):
    """
    Raised when a formatting tool the formatter runs is not installed for the running
    interpreter.
    """

    tool_module: str
    """
    The module the missing tool runs under.
    """

    def error_message(self) -> str:
        return f"The formatting tool `{self.tool_module}` is not installed."

    def suggest_correction(self) -> str:
        return 'Install the formatting tools with `pip install "krrood[development-tools]"`.'


@dataclass
class RulesBlockNotFound(DataclassException):
    """
    Raised when an existing ``AGENTS.md`` does not hold exactly one block of shared
    rules, opened and closed by its two marker lines in that order.
    """

    instructions_path: Path
    """
    The ``AGENTS.md`` that lacks a well-formed block.
    """

    begin_marker: str
    """
    The line that opens the block.
    """

    end_marker: str
    """
    The line that closes the block.
    """

    def error_message(self) -> str:
        return (
            f"{self.instructions_path} must contain the line {self.begin_marker} once, "
            f"followed by the line {self.end_marker} once."
        )

    def suggest_correction(self) -> str:
        return (
            "Put those two lines where the shared rules belong, leaving one of each, "
            "then run `krrood agents-md` again."
        )
