"""
What this package contains, discovered rather than listed.

Which modules exist, which of them answer as a command line, and which third-party modules
the package may reach are all read from the package itself - the directory, each module's
own source, and ``requirements.txt``. Two things cannot be derived and are declared: which
modules are allowed to need those requirements, and which callers run a module without
installing them. :mod:`test.bastler_test.test_package_contract` holds both to what the
modules and the callers actually do.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import packages_distributions
from pathlib import Path

PACKAGE_DIRECTORY = Path(__file__).parent
"""
This package's own directory, which is also the directory it *is* rather than lives under.
"""

REPOSITORY_ROOT = PACKAGE_DIRECTORY.parent
"""
The repository root, which is the directory ``bastler`` imports from with no install.
"""

REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")
"""
A requirement line's distribution name, up to the first version or marker character.
"""


@dataclass(frozen=True)
class PackageModule:
    """
    One module of this package.
    """

    name: str
    """
    The module's name within the package, e.g. ``"stack"``.
    """

    is_command_line_entry_point: bool
    """
    Whether the module guards a block on being run as ``__main__``, which is what makes
    ``python3 -m bastler.<name> --help`` answer rather than do nothing.
    """

    @property
    def import_path(self) -> str:
        """:return: The dotted path this module is imported by."""
        return f"bastler.{self.name}"


def _has_a_main_block(source: Path) -> bool:
    """
    :param source: A module's file.
    :return: Whether it guards a top-level block on being run as ``__main__``.
    """
    return any(
        isinstance(node, ast.If) and "__main__" in ast.dump(node.test)
        for node in ast.parse(source.read_text()).body
    )


@lru_cache(maxsize=1)
def package_modules() -> tuple[PackageModule, ...]:
    """
    :return: Every module in this package, in name order.
    """
    return tuple(
        PackageModule(path.stem, _has_a_main_block(path))
        for path in sorted(PACKAGE_DIRECTORY.glob("*.py"))
        if path.stem != "__init__"
    )


def command_line_entry_points() -> tuple[PackageModule, ...]:
    """
    :return: The modules a script or a session invokes directly.
    """
    return tuple(
        module for module in package_modules() if module.is_command_line_entry_point
    )


@lru_cache(maxsize=1)
def third_party_import_names() -> frozenset[str]:
    """
    :return: The names ``import`` reaches this package's requirements by.

    Read from ``requirements.txt`` through the installed metadata, because a distribution
    is not always imported by its own name - PyYAML is ``yaml``.
    """
    requirements = {
        match.group().lower()
        for line in (PACKAGE_DIRECTORY / "requirements.txt").read_text().splitlines()
        if (match := REQUIREMENT_NAME.match(line.split("#", 1)[0].strip()))
    }
    return frozenset(
        import_name
        for import_name, distributions in packages_distributions().items()
        if any(distribution.lower() in requirements for distribution in distributions)
    )


MODULES_THAT_MAY_NEED_THE_REQUIREMENTS = frozenset(
    {
        "plan_item_bootstrap",
        "plan_manifest_tools",
        "render_common",
        "build_dashboard",
        "build_index",
        "check_dependency_readiness",
        "sync_manifest_status",
    }
)
"""
The modules allowed to import something from ``requirements.txt``.

The default runs the other way - a module imports on the standard library alone - so this
names the exceptions rather than classifying every module, and a module added later is
held to the default without anyone writing anything down. Each of these reads a plan
manifest or renders a page, which is what ``check-setup.sh``'s dependency row exists to
report as a gap a caller closes first.

Held in both directions: a module that starts needing a requirement fails until it is
named here, and one named here that no longer needs one fails until it is removed. So the
failure lands where the decision is made, rather than in whichever caller next runs it on
a checkout that installed nothing.
"""


def modules_held_to_the_standard_library() -> tuple[PackageModule, ...]:
    """
    :return: Every module expected to import with the requirements unavailable.
    """
    return tuple(
        module
        for module in package_modules()
        if module.name not in MODULES_THAT_MAY_NEED_THE_REQUIREMENTS
    )


def modules_allowed_the_requirements() -> tuple[PackageModule, ...]:
    """
    :return: The declared exceptions, as modules.
    """
    return tuple(
        module
        for module in package_modules()
        if module.name in MODULES_THAT_MAY_NEED_THE_REQUIREMENTS
    )


@dataclass(frozen=True)
class UninstalledInvocation:
    """
    A caller that invokes one of this package's modules without installing its
    requirements first.

    The named evidence behind the default above: it is not a rule kept for its own sake,
    it is what this caller needs in order to work at all.
    """

    caller: str
    """
    The caller's path from the repository root.
    """

    module_name: str
    """
    The module it invokes, by its name within this package.
    """

    reason: str
    """
    Why the caller installs nothing, so a reader can judge whether that is still true.
    """

    @property
    def caller_path(self) -> Path:
        """:return: Where the caller lives."""
        return REPOSITORY_ROOT / self.caller

    @property
    def module(self) -> PackageModule:
        """:return: The module this caller invokes."""
        return next(
            module for module in package_modules() if module.name == self.module_name
        )


UNINSTALLED_INVOCATIONS: tuple[UninstalledInvocation, ...] = (
    UninstalledInvocation(
        caller=".github/workflows/upstream-reviews.yml",
        module_name="upstream_reviews",
        reason=(
            "The job checks out, sets up Python and runs the module - there is no pip "
            "step, because it needs none and gh supplies the credential."
        ),
    ),
)
"""
Every caller that runs a module of this package on a checkout where nothing is installed.

What no file states about itself: a caller's own source says what it invokes and whether
it installs anything, but nothing says the pairing is deliberate. A test reads each
caller's file back, so an entry that stops being true - the caller gains an install step,
or stops invoking the module - fails rather than lingering.

Importing a module imports everything it imports, so an entry reaches the module's whole
import graph rather than only its own file.
"""
