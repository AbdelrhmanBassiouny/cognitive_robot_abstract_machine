"""
The input files of the cram-development-tools tests.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class DatasetFile(Enum):
    """
    The input files of this suite, under its ``dataset`` directory.
    """

    UNFORMATTED_MODULE = Path(__file__).parent / "dataset" / "unformatted_module.py"
    """
    A module black and docformatter both change, and agree on.
    """

    FORMATTED_MODULE = Path(__file__).parent / "dataset" / "formatted_module.py"
    """
    :attr:`UNFORMATTED_MODULE` after formatting.
    """

    DOCSTRING_CONFLICTING_MODULE = (
        Path(__file__).parent / "dataset" / "docstring_conflicting_module.py"
    )
    """
    A module whose docformatter output black changes again.
    """

    INVALID_SYNTAX_MODULE = (
        Path(__file__).parent / "dataset" / "invalid_syntax_module.py"
    )
    """
    A module black rejects.
    """

    PROJECT_RULES = Path(__file__).parent / "dataset" / "project_rules.md"
    """
    An ``AGENTS.project.md`` of a repository under test.
    """
