"""
The ORM interfaces the packages of this repository generate with ORMatic.

The interfaces are generated rather than written, so the repository ignores them instead
of tracking them: a fresh checkout carries no database mapping at all, and nothing can
be persisted or turned into a data access object until they have been generated once.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from krrood.class_diagrams.progress_report import (
    ClassDiagramProgress,
    ProgressEnvironmentVariable,
)
from tqdm import tqdm
from typing_extensions import Optional, Sequence

from cognitive_robot_abstract_machine.exceptions import (
    MissingOrmGeneratorError,
    OrmGenerationFailedError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
"""
Root of the checkout this package is installed from.
"""

INTERFACE_FILE_NAME = "ormatic_interface.py"
"""
Name every package's generator writes its interface to.
"""

PROGRESS_DESCRIPTION = "Building ORM interfaces"
"""
What the progress bar of a build calls itself.
"""

PROGRESS_REQUESTED = "1"
"""
What a generator is told to report the classes it finishes.
"""

# %% what a build shows while it runs


@dataclass
class BuildProgress:
    """
    A bar counting the classes of the interface being built, and how many of the
    interfaces are done.
    """

    total_interfaces: int
    """
    How many interfaces the build covers.
    """

    show_generator_output: bool
    """
    Whether the generators write to the terminal, which leaves no room for a bar.
    """

    completed_interfaces: int = field(default=0, init=False)
    """
    How many of them are built.
    """

    bar: Optional[tqdm] = field(default=None, init=False)
    """
    The bar, absent while the generators have the terminal to themselves.
    """

    counted_classes: bool = field(default=False, init=False)
    """
    Whether the interface being built has said how many classes it holds.
    """

    def __enter__(self) -> BuildProgress:
        if not self.show_generator_output:
            self.bar = tqdm(unit="class")
            self.show_interfaces_done()
        return self

    def __exit__(self, *exception: object) -> None:
        if self.bar is not None:
            self.bar.close()

    def show_interfaces_done(self) -> None:
        """
        Put how far along the interfaces are beside the bar.
        """
        self.bar.set_description_str(
            f"{PROGRESS_DESCRIPTION} {self.completed_interfaces}/{self.total_interfaces}"
        )

    def start(self, package_name: str) -> None:
        """
        Begin reporting on the interface of a package.

        :param package_name: The package whose interface is being built.
        """
        self.counted_classes = False
        if self.bar is None:
            return
        self.bar.set_postfix_str(package_name)

    def advance(self, report: ClassDiagramProgress) -> None:
        """
        Count one class of the interface being built as done.

        :param report: What the generator said about the class it finished.
        """
        if self.bar is None:
            return
        if not self.counted_classes:
            self.bar.reset(total=report.total_classes)
            self.counted_classes = True
            self.show_interfaces_done()
        self.bar.update(1)

    def finish(self) -> None:
        """
        Count the interface being built as done.
        """
        self.completed_interfaces += 1
        if self.bar is None:
            return
        self.show_interfaces_done()


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

    def remove(self) -> None:
        """
        Delete the interface, so that a stale version cannot be imported while the new
        one is generated.
        """
        self.path.unlink(missing_ok=True)

    def generate(self, progress: BuildProgress) -> None:
        """
        Run this package's generator in a subprocess.

        :param progress: What to report the classes the generator finishes to.
        :raises MissingOrmGeneratorError: If the package has no generator.
        :raises OrmGenerationFailedError: If the generator exits without having built
            the interface.
        """
        if not self.generator.exists():
            raise MissingOrmGeneratorError(self.package_name, self.generator)
        progress.start(self.package_name)
        if progress.show_generator_output:
            self.run_writing_to_the_terminal()
        else:
            self.run_reporting_to(progress)
        progress.finish()

    def run_writing_to_the_terminal(self) -> None:
        """
        Run the generator with the terminal, so its logging can be read as it happens.

        :raises OrmGenerationFailedError: If the generator exits without having built
            the interface.
        """
        result = subprocess.run(
            [sys.executable, str(self.generator)], cwd=self.generator.parent
        )
        if result.returncode != 0:
            raise OrmGenerationFailedError(self.package_name, "")

    def run_reporting_to(self, progress: BuildProgress) -> None:
        """
        Run the generator, counting the classes it reports and keeping the rest of what
        it writes for a failure to report.

        A generator logs its way through a whole class hierarchy, which would bury the
        bar, so its logging is held back rather than shown.

        :param progress: What to report the classes it finishes to.
        :raises OrmGenerationFailedError: If the generator exits without having built
            the interface.
        """
        generation = subprocess.Popen(
            [sys.executable, str(self.generator)],
            cwd=self.generator.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={
                **os.environ,
                ProgressEnvironmentVariable.REPORT_PROGRESS: PROGRESS_REQUESTED,
            },
        )
        written = []
        for line in generation.stdout:
            report = ClassDiagramProgress.from_line(line)
            if report is None:
                written.append(line)
                continue
            progress.advance(report)
        if generation.wait() != 0:
            raise OrmGenerationFailedError(self.package_name, "".join(written))


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

    def regenerate(self, show_generator_output: bool = False) -> None:
        """
        Build every interface anew, from an empty state and in dependency order.

        ..note:: This takes about a minute and a half, since every package's generator
            introspects its whole class hierarchy.

        :param show_generator_output: Whether to let the generators write to the
            terminal. Their logging and the progress bar cannot share it, so asking for
            one leaves out the other.
        """
        for interface in self.interfaces:
            interface.remove()

        with BuildProgress(len(self.interfaces), show_generator_output) as progress:
            for interface in self.interfaces:
                interface.generate(progress)


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
