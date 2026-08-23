"""
The contract :mod:`bastler` has to keep: everything importable from the repository root
with no install, every module importable on its own, every entry point reachable through
``python3 -m``, every module a caller runs without installing anything importing on the
standard library alone, and nothing left behind under ``.claude/``.

:mod:`bastler.package_layout` discovers the modules, the entry points and the requirements
from the package itself, so nothing here is a second list of them. The one thing it
declares - which callers install nothing - is checked here against those callers' own
files.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from .constants import ToolingDirectory
from .script_runner import ScriptRunner
from bastler.package_layout import (
    PACKAGE_DIRECTORY,
    REPOSITORY_ROOT,
    UNINSTALLED_INVOCATIONS,
    PackageModule,
    UninstalledInvocation,
    command_line_entry_points,
    modules_that_must_not_import_third_party,
    package_modules,
    third_party_import_names,
)

CLAUDE_DIRECTORY = REPOSITORY_ROOT / ".claude"
"""
The directory the migration emptied of Python.

Its SKILL.md files, settings.json and bash entry points stay; not one ``.py`` file does.
"""

IMPORT_WITH_MODULES_UNAVAILABLE_SCRIPT = (
    Path(__file__).parent / "dataset" / "import_with_modules_unavailable.py"
)
"""
The helper that imports one module with a named set of top-level modules unimportable.
"""


@dataclass(frozen=True, kw_only=True)
class InterpreterRunner(ScriptRunner):
    """
    Runs this interpreter itself, for the checks that are about the import rather than
    about any one entry point.
    """

    @property
    def command(self) -> tuple[str, ...]:
        """:return: This interpreter, with no module named yet."""
        return (sys.executable,)


def run_from_repository_root(*arguments: str) -> subprocess.CompletedProcess[str]:
    """
    Run this interpreter from the repository root with an environment that cannot help
    it find the package.

    ``PYTHONPATH`` is removed so a pass proves the zero-install import really comes from
    the repository root being the working directory, rather than from whatever the
    caller's shell happened to export.

    :param arguments: Arguments to the interpreter, e.g. ``("-c", "import bastler")``.
    :return: The completed process, with output captured as text.
    """
    return InterpreterRunner(
        project_root=REPOSITORY_ROOT,
        removed_variable_prefixes=("PYTHONPATH",),
    ).run(*arguments)


SHELL_CONFIGURATION = ToolingDirectory.HOOKS.path / "resolve-personal-notes-config.sh"
"""
The file the bash callers source, which is where a module gets a shell name.
"""

MODULE_VARIABLE = re.compile(r'^([A-Z_]+)="(bastler\.[a-z_]+)"', re.MULTILINE)
"""
One ``NAME="bastler.module"`` assignment in the shell configuration.
"""

REQUIREMENTS_INSTALL = re.compile(
    r"(pip install|uv pip install|uv sync)[^\n]*"
    r"(BASTLER_REQUIREMENTS_FILE|bastler/requirements\.txt)"
)
"""
A step that installs this package's requirements, however the caller spells the file.
"""


def names_of(module: PackageModule) -> frozenset[str]:
    """
    Every spelling a caller can invoke a module by.

    Bash callers go through a shell variable rather than the dotted path, so the variable
    names are read from the configuration that assigns them instead of written out here.

    :param module: The module to name.
    :return: Its import path, plus any shell variable holding that path.
    """
    assignments = MODULE_VARIABLE.findall(SHELL_CONFIGURATION.read_text())
    return frozenset({module.import_path}) | {
        variable for variable, path in assignments if path == module.import_path
    }


def installs_the_requirements(caller_source: str) -> bool:
    """
    :param caller_source: A caller's own file.
    :return: Whether it installs this package's requirements before running anything.
    """
    return REQUIREMENTS_INSTALL.search(caller_source) is not None


# %% the package exists and is reachable with no install


def test_the_package_imports_from_the_repository_root_with_no_install():
    """
    The zero-install contract: a fresh clone with no pip step can import the package,
    and what it imports is this repository's copy rather than an installed one.
    """
    result = run_from_repository_root("-c", "import bastler; print(bastler.__file__)")

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == PACKAGE_DIRECTORY / "__init__.py"


# %% each module stands on its own


@pytest.mark.parametrize("module", package_modules(), ids=lambda module: module.name)
def test_every_module_imports_on_its_own(module: PackageModule):
    """
    Each module imports in an interpreter that has imported nothing else.

    One subprocess per module rather than one for all of them: an import cycle only bites
    whichever module a caller reaches first, so a suite that imports them together can
    stay green while a single-module entry point is broken.
    """
    result = run_from_repository_root("-c", f"import {module.import_path}")

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "module", command_line_entry_points(), ids=lambda module: module.name
)
def test_every_entry_point_answers_help_through_the_module_runner(
    module: PackageModule,
):
    """
    Each entry point is reachable as ``python -m bastler.<name>``.

    That form rather than a path to the file: a module run by path puts its own directory
    on ``sys.path`` instead of the repository root, so its absolute imports of its
    siblings would not resolve. Every bash caller invokes them this way.
    """
    result = run_from_repository_root("-m", module.import_path, "--help")

    assert result.returncode == 0, result.stderr


# %% what a caller runs before anything is installed


@pytest.mark.parametrize(
    "module",
    modules_that_must_not_import_third_party(),
    ids=lambda module: module.name,
)
def test_every_module_a_caller_reaches_uninstalled_imports_on_the_standard_library(
    module: PackageModule,
):
    """
    A module some caller reaches before installing anything imports with this package's
    requirements made unimportable.

    Which modules those are is computed from the callers rather than named, so a module
    that becomes reachable from one is checked without anyone declaring it. The
    requirements stay installed - what is under test is what the module reaches, not what
    the machine running the suite happens to hold.
    """
    result = run_from_repository_root(
        str(IMPORT_WITH_MODULES_UNAVAILABLE_SCRIPT),
        "--unavailable",
        ",".join(sorted(third_party_import_names())),
        module.import_path,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "invocation", UNINSTALLED_INVOCATIONS, ids=lambda invocation: invocation.module_name
)
def test_every_module_a_caller_runs_uninstalled_is_reached_by_the_closure(
    invocation: UninstalledInvocation,
):
    """
    Every declared caller's own module is inside the set derived from those callers.

    Cheap, and it catches the closure being computed from something other than the
    declarations - which would leave entries here silently unchecked.
    """
    assert invocation.module in modules_that_must_not_import_third_party()


@pytest.mark.parametrize(
    "invocation", UNINSTALLED_INVOCATIONS, ids=lambda invocation: invocation.caller
)
def test_every_uninstalled_caller_still_invokes_its_module_and_still_installs_nothing(
    invocation: UninstalledInvocation,
):
    """
    Each declaration is held to its caller's own file, from both sides.

    Without this an entry outlives what it describes: a caller that gains an install step
    keeps a constraint it no longer needs, and one that stops invoking the module keeps a
    constraint about nothing - and since the closure is computed from these entries, a
    stale one quietly widens or narrows what gets checked at all.
    """
    caller_source = invocation.caller_path.read_text()

    assert any(name in caller_source for name in names_of(invocation.module))
    assert not installs_the_requirements(caller_source)


# %% nothing is left behind


def test_no_python_module_remains_under_the_claude_directory():
    """
    The migration's own completeness assertion from the other side.

    ``.claude/`` keeps its SKILL.md files, settings.json and bash entry points - Claude
    Code discovers those by path - and not one Python file.
    """
    remaining_module_paths = sorted(
        str(path.relative_to(REPOSITORY_ROOT))
        for path in CLAUDE_DIRECTORY.rglob("*.py")
    )

    assert remaining_module_paths == []
