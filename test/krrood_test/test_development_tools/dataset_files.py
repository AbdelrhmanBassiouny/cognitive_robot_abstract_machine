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

    HAND_WRITTEN_RULES = Path(__file__).parent / "dataset" / "hand_written_rules.md"
    """
    Hand-written rules an ``AGENTS.md`` under test holds after its block of shared
    rules.
    """

    PROJECT_RULES_MODULE = Path(__file__).parent / "dataset" / "project_rules_module.py"
    """
    A module declaring a repository's own rules, one in a shared section and one in a
    section of its own.
    """
