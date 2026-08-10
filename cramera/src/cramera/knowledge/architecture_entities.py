"""
Entities scanned from the CRAM repository's static architecture.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Tuple


@dataclass(unsafe_hash=True)
class Package:
    """
    A top-level package of the CRAM repository.
    """

    name: str
    """
    Directory name, e.g. ``coraplex``.
    """

    description: str
    """
    One-line description (curated, or the first README line).
    """

    module_count: int
    """
    Number of Python modules in the package.
    """

    class_count: int
    """
    Number of classes defined in the package.
    """


@dataclass(unsafe_hash=True)
class SubPackage:
    """
    A qualified subpackage, e.g. ``coraplex.plans``.
    """

    name: str
    """
    Qualified name, e.g. ``coraplex.plans``.
    """

    package: str
    """
    The top-level package this subpackage belongs to.
    """

    module_count: int
    """
    Number of modules in the subpackage.
    """

    class_count: int
    """
    Number of classes defined in the subpackage.
    """


@dataclass(unsafe_hash=True)
class PythonClass:
    """
    A class found by the static scan of the CRAM repository.
    """

    name: str
    """
    Class name.
    """

    package: str
    """
    Top-level package the class is defined in.
    """

    subpackage: str
    """
    Qualified subpackage (equal to ``package`` for top-level modules).
    """

    module: str
    """
    Repository-relative module path.
    """

    bases: Tuple[str, ...]
    """
    Names of the direct base classes.
    """

    methods: int
    """
    Number of methods defined on the class.
    """

    docstring_summary: str
    """
    First docstring line, or ``''``.
    """

    @property
    def qualified_name(self) -> str:
        """
        The class name prefixed with the module it is defined in.

        Unique across the scan, which is what the graph uses as the class's node id.
        """
        return self.module + "." + self.name
