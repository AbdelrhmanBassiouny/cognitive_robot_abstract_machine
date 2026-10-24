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
class MalformedRulesBlock(DataclassException):
    """
    Raised when an ``AGENTS.md`` holds a marker line of the block of generated rules,
    but not exactly one block opened and closed by its two marker lines in that order.
    """

    instructions_path: Path
    """
    The ``AGENTS.md`` whose block is malformed.
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
            "Leave one of each line, in that order, where the rules belong, or "
            "remove both to have `krrood agents-md` put the block at the top; then run "
            "it again."
        )
