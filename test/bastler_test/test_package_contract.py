"""
The contract :mod:`bastler` has to keep: everything importable from the repository root
with no install, every module importable on its own, every entry point reachable through
``python3 -m``, each module reaching no further than the tier it declares, and nothing
left behind under ``.claude/``.

What each module declares is :mod:`bastler.package_layout`, next to the code it
describes. This file only checks it, which is why the declaration is not repeated here.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from bastler.package_layout import (
    PACKAGE_DIRECTORY,
    PACKAGE_MODULES,
    REPOSITORY_ROOT,
    PackageModule,
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


def run_from_repository_root(*arguments: str) -> subprocess.CompletedProcess[str]:
    """
    Run this interpreter from the repository root with an environment that cannot help
    it find the package.

    ``PYTHONPATH`` is stripped so a pass proves the zero-install import really comes
    from the repository root being the working directory, rather than from whatever the
    caller's shell happened to export.

    :param arguments: Arguments to the interpreter, e.g. ``("-c", "import bastler")``.
    :return: The completed process, with output captured as text.
    """
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


# %% the package exists and is reachable with no install


def test_the_package_imports_from_the_repository_root_with_no_install():
    """
    The zero-install contract: a fresh clone with no pip step can import the package,
    and what it imports is this repository's copy rather than an installed one.
    """
    result = run_from_repository_root("-c", "import bastler; print(bastler.__file__)")

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == PACKAGE_DIRECTORY / "__init__.py"


def test_every_declared_module_is_present_and_every_present_module_is_declared():
    """
    The declaration and the directory say the same thing.

    One assertion rather than two, because both directions fail the same way in
    practice: a module named but absent was left behind by the move, and a module
    present but unnamed has no stated tier and no stated entry-point status, so nothing
    else in this file would check it at all.
    """
    declared_module_names = {module.name for module in PACKAGE_MODULES}
    present_module_names = {
        path.stem for path in PACKAGE_DIRECTORY.glob("*.py") if path.stem != "__init__"
    }

    assert declared_module_names == present_module_names


# %% each module stands on its own


@pytest.mark.parametrize("module", PACKAGE_MODULES, ids=lambda module: module.name)
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
    "module",
    [module for module in PACKAGE_MODULES if module.is_command_line_entry_point],
    ids=lambda module: module.name,
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


# %% the dependency tiers reach no further than they claim


@pytest.mark.parametrize(
    "module",
    [module for module in PACKAGE_MODULES if module.unreachable_third_party_modules],
    ids=lambda module: module.name,
)
def test_every_module_imports_within_its_own_dependency_tier(module: PackageModule):
    """
    A module imports with everything above its tier made unimportable.

    See :class:`bastler.package_layout.DependencyTier` for what the boundary answers. The
    unavailable modules stay installed - what is under test is what this module reaches,
    not what the machine running the suite happens to hold.
    """
    result = run_from_repository_root(
        str(IMPORT_WITH_MODULES_UNAVAILABLE_SCRIPT),
        "--unavailable",
        ",".join(sorted(module.unreachable_third_party_modules)),
        module.import_path,
    )

    assert result.returncode == 0, result.stderr


def test_some_module_is_actually_checked_against_an_unavailable_import():
    """
    The parametrization above filters, so this asserts it filtered to something.

    Without it, a tier table that accidentally allowed every module everything would
    make every case above vanish and the suite would still pass.
    """
    checked_module_names = [
        module.name
        for module in PACKAGE_MODULES
        if module.unreachable_third_party_modules
    ]

    assert checked_module_names != []


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
