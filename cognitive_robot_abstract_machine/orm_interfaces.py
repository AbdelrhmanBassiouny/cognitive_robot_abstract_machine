"""
The ORM interfaces the packages of this repository generate with ORMatic.

The repository tracks every ``ormatic_interface.py`` as an empty placeholder, so a fresh
checkout carries no database mapping at all: nothing can be persisted, and nothing can
be turned into a data access object, until the interfaces have been generated once.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from typing_extensions import Sequence

from cognitive_robot_abstract_machine.exceptions import (
    MissingOrmGeneratorError,
    MissingOrmInterfaceError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
"""
Root of the checkout this package is installed from.
"""


def let_git_ignore_changes(repository_root: Path, path: Path) -> None:
    """
    Set git's skip-worktree bit on a tracked file.

    Git then treats the working-tree content as always equal to what is committed: the
    file never shows up in ``git status``/``git diff``, and ``git add`` cannot stage it.

    :param repository_root: Root of the checkout the file belongs to.
    :param path: Repository-relative path of the tracked file.
    """
    subprocess.run(
        ["git", "update-index", "--skip-worktree", str(path)],
        cwd=repository_root,
        check=True,
    )


# %% a single package's interface


@dataclass
class OrmInterface:
    """
    The ORM interface a single package generates.
    """

    package_name: str
    """
    Name of the package, which is also the name of its source folder and module.
    """

    repository_root: Path
    """
    Root of the checkout the package lives in.
    """

    @property
    def generator(self) -> Path:
        """
        The script that generates this interface.
        """
        return self.repository_root / self.package_name / "scripts" / "generate_orm.py"

    @property
    def path(self) -> Path:
        """
        The generated interface file.
        """
        return (
            self.repository_root
            / self.package_name
            / "src"
            / self.package_name
            / "orm"
            / "ormatic_interface.py"
        )

    @property
    def is_generated(self) -> bool:
        """
        Whether the interface holds generated content rather than the empty placeholder
        the repository tracks.
        """
        return self.path.exists() and self.path.stat().st_size > 0

    def clear(self) -> None:
        """
        Empty the interface without deleting it, so that a stale version cannot be
        imported while the new one is generated.
        """
        if not self.path.exists():
            raise MissingOrmInterfaceError(self.package_name, self.path)
        self.path.write_text("", encoding="utf-8")

    def generate(self) -> None:
        """
        Run this package's generator in a subprocess.
        """
        if not self.generator.exists():
            raise MissingOrmGeneratorError(self.package_name, self.generator)
        subprocess.run(
            [sys.executable, str(self.generator)],
            cwd=self.generator.parent,
            check=True,
        )

    def protect_from_commits(self) -> None:
        """
        Keep git from ever offering the generated content for staging.
        """
        let_git_ignore_changes(
            self.repository_root, self.path.relative_to(self.repository_root)
        )


# %% every interface of the repository


@dataclass
class WorkspaceOrmInterfaces:
    """
    The ORM interfaces of a checkout, as one unit.
    """

    interfaces: Sequence[OrmInterface]
    """
    The interfaces ordered by dependency: each generator imports the already generated
    interfaces of the packages listed before it.
    """

    @property
    def are_generated(self) -> bool:
        """
        Whether every interface holds generated content.
        """
        return all(interface.is_generated for interface in self.interfaces)

    def regenerate(self) -> None:
        """
        Build every interface anew, from an empty state and in dependency order.

        ..note:: This takes about a minute, since every package's generator introspects
            its whole class hierarchy.
        """
        for interface in self.interfaces:
            interface.clear()

        for interface in self.interfaces:
            interface.generate()

        for interface in self.interfaces:
            interface.protect_from_commits()

    def ensure_generated(self) -> bool:
        """
        Leave the checkout with interfaces it can persist objects through.

        A checkout that is missing one is built whole rather than in part: a generator
        reads the interfaces of the packages before it, so the one that is missing
        decides nothing about which of the others are still valid.

        :return: Whether they had to be built.
        """
        if self.are_generated:
            return False
        self.regenerate()
        return True


WORKSPACE_ORM_INTERFACES = WorkspaceOrmInterfaces(
    tuple(
        OrmInterface(package_name, REPOSITORY_ROOT)
        for package_name in (
            "semantic_digital_twin",
            "giskardpy",
            "coraplex",
            "segmind",
            "experiments",
        )
    )
)
"""
The ORM interfaces of this repository.
"""
