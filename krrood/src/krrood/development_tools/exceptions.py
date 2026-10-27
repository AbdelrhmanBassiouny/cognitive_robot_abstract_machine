"""
Exceptions raised by the development tools.
"""

from __future__ import annotations

from dataclasses import dataclass

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
class SectionWithoutRuleSet(DataclassException):
    """
    Raised when a top-level section of the rules names no rule set for its rules.
    """

    section: type
    """
    The section without a rule set.
    """

    def error_message(self) -> str:
        return f"The top-level section {self.section.__qualname__} names no rule set."

    def suggest_correction(self) -> str:
        return (
            "Override `default_rule_set` with a `classproperty` returning the rule set "
            "of its rules, or `parent` returning the section it is nested under."
        )
