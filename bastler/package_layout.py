"""
What this package contains, discovered rather than listed.

Which modules exist, which of them answer as a command line, and which third-party modules
the package may reach are all read from the package itself - the directory, each module's
own source, and ``requirements.txt``. So is which modules must import on the standard
library alone: that is the import closure of what the callers below reach, computed rather
than listed.

The one thing no file states about itself is which callers run a module *without*
installing the requirements first, so that is declared, and
:mod:`test.bastler_test.test_package_contract` holds each entry to its caller's own file.
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
    UninstalledInvocation(
        caller=".claude/skills/stacked-pr-maintenance/SKILL.md",
        module_name="maintenance",
        reason=(
            "A scheduled pass runs in a fresh container, where check-setup.sh reports the "
            "requirements as missing - the pass has to work before anyone closes that gap."
        ),
    ),
    UninstalledInvocation(
        caller=".claude/skills/upstream-reviews/SKILL.md",
        module_name="stack",
        reason="Resolves the upstream before anything else, so it runs first of all.",
    ),
    UninstalledInvocation(
        caller=".claude/skills/add-plan-item/SKILL.md",
        module_name="check_scope_overlap",
        reason="Answers a scope question from git alone, in whatever session asks it.",
    ),
    UninstalledInvocation(
        caller=".claude/hooks/plan-updates-since.sh",
        module_name="plan_updates_since_support",
        reason="A hook script, so it runs wherever the session does and installs nothing.",
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


def _sibling_imports_of(module: PackageModule) -> frozenset[str]:
    """
    :param module: The module to read.
    :return: The names of this package's other modules it imports directly.
    """
    source = ast.parse((PACKAGE_DIRECTORY / f"{module.name}.py").read_text())
    imported: set[str] = set()
    for node in ast.walk(source):
        if isinstance(node, ast.ImportFrom):
            if node.module == "bastler":
                # ``from bastler import stack`` names the module in the alias, not the
                # module path, so both forms have to be read or the closure misses it.
                imported.update(alias.name for alias in node.names)
            elif (node.module or "").startswith("bastler."):
                imported.add(node.module.removeprefix("bastler.").split(".", 1)[0])
        elif isinstance(node, ast.Import):
            imported.update(
                alias.name.removeprefix("bastler.").split(".", 1)[0]
                for alias in node.names
                if alias.name.startswith("bastler.")
            )
    return frozenset(imported & {other.name for other in package_modules()})


def modules_that_must_not_import_third_party() -> tuple[PackageModule, ...]:
    """
    :return: Every module that has to import on the standard library alone.

    Derived rather than declared: importing a module imports everything it imports, so
    this is the closure of what :data:`UNINSTALLED_INVOCATIONS`' callers reach. A module
    outside it is under no such constraint, because nothing runs it before an install.
    """
    by_name = {module.name: module for module in package_modules()}
    reached: set[str] = set()
    pending = [invocation.module_name for invocation in UNINSTALLED_INVOCATIONS]
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        pending.extend(_sibling_imports_of(by_name[name]) - reached)
    return tuple(module for module in package_modules() if module.name in reached)
