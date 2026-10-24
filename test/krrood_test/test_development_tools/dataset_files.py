"""
The input files of the development tools tests.
"""

from __future__ import annotations

from pathlib import Path

from krrood.patterns.path_enumeration import PathEnumeration


class DatasetFile(PathEnumeration):
    """
    The input files of this suite, under its ``dataset`` directory.
    """

    UNFORMATTED_MODULE = Path(__file__).parent / "dataset" / "unformatted_module.py"
    """
    A module ruff and docformatter both change, and agree on.
    """

    FORMATTED_MODULE = Path(__file__).parent / "dataset" / "formatted_module.py"
    """
    :attr:`UNFORMATTED_MODULE` after formatting.
    """

    DOCSTRING_CONFLICTING_MODULE = (
        Path(__file__).parent / "dataset" / "docstring_conflicting_module.py"
    )
    """
    A module whose docformatter output ruff changes again.
    """

    INVALID_SYNTAX_MODULE = (
        Path(__file__).parent / "dataset" / "invalid_syntax_module.py"
    )
    """
    A module ruff rejects.
    """

    INTRODUCTION = Path(__file__).parent / "dataset" / "introduction.md"
    """
    Hand-written text an ``AGENTS.md`` under test holds before its block of shared
    rules.
    """

    PROJECT_RULES = Path(__file__).parent / "dataset" / "project_rules.md"
    """
    Hand-written rules an ``AGENTS.md`` under test holds after its block of shared
    rules.
    """

    RULES = Path(__file__).parent / "dataset" / "rules"
    """
    A rules directory whose Python rule set has rules on errors and whose krrood rule
    set has rules on errors and structured data.
    """
