"""
The ORM interfaces the packages of this repository generate with ORMatic.

The interfaces are generated rather than written, so the repository ignores them instead
of tracking them: a fresh checkout carries no database mapping at all, and nothing can
be persisted or turned into a data access object until they have been generated once.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from typing_extensions import Sequence

from cognitive_robot_abstract_machine.exceptions import MissingOrmGeneratorError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
"""
Root of the checkout this package is installed from.
"""

INTERFACE_FILE_NAME = "ormatic_interface.py"
"""
Name every package's generator writes its interface to.
"""

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
            / INTERFACE_FILE_NAME
        )

    @property
    def is_generated(self) -> bool:
        """
        Whether this checkout holds the interface.
        """
        return self.path.exists()

    def remove(self) -> None:
        """
        Delete the interface, so that a stale version cannot be imported while the new
        one is generated.
        """
        self.path.unlink(missing_ok=True)

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
            interface.remove()

        for interface in self.interfaces:
            interface.generate()

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
