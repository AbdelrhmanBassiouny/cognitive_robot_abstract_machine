"""
The files of this repository that code refers to by path.
"""

from __future__ import annotations

from pathlib import Path

from krrood.patterns.path_enumeration import PathEnumeration

# %% files


class RepositoryFile(PathEnumeration):
    """
    The files of this repository, by their path relative to its root.
    """

    CODE_OWNERS = Path(".github") / "CODEOWNERS"
    """
    The code owners of each part of the repository.
    """
