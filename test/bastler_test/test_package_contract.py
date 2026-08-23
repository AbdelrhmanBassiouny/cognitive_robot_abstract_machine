"""
The contract :mod:`bastler` has to keep for the migration that created it to have
succeeded: everything importable from the repository root with no install, every module
importable on its own, every entry point reachable through ``python -m``, each dependency
tier reaching no further than it claims, and nothing left behind under ``.claude/``.

These are properties of the *package*, not of any one module's behaviour, which is why
they live together rather than beside the code they cover.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).parent.parent.parent
"""
The repository root, which is also the directory ``bastler`` must be importable from.
"""

PACKAGE_DIRECTORY = REPOSITORY_ROOT / "bastler"
"""
The package itself. It *is* this directory rather than living under one - see its
``pyproject.toml``'s package-dir mapping.
"""

CLAUDE_DIRECTORY = REPOSITORY_ROOT / ".claude"
"""
The directory the migration empties of Python. Its SKILL.md files, settings.json and bash
entry points stay; not one ``.py`` file does.
"""

IMPORT_WITH_MODULES_BLOCKED_SCRIPT = (
    Path(__file__).parent / "dataset" / "import_with_modules_blocked.py"
)
"""
The helper that imports one module with a named set of top-level modules unimportable.
"""


class DependencyTier(StrEnum):
    """
    How far up the dependency stack a module is allowed to reach.

    The boundary is load-bearing rather than descriptive: a hook runs on a machine where
    nothing has been installed, so a module it reaches may import only the standard
    library, while the dashboard build imports jinja2, markdown and nh3 of its own. A
    module that quietly gains an import from a tier above its own breaks the caller that
    could previously reach it, and nothing else would notice.
    """

    STANDARD_LIBRARY = "standard-library"
    """
    Imports nothing outside the standard library, so any caller can reach it.
    """

    PLAN_MANIFEST = "plan-manifest"
    """
    Reads or writes a plan manifest, so it needs PyYAML - but never the render layer.
    """

    PAGE_RENDERING = "page-rendering"
    """
    Renders a dashboard page, so it needs jinja2, markdown and nh3. The top tier: nothing
    is out of bounds for it, so nothing is blocked when its imports are checked.
    """


THIRD_PARTY_MODULES_BY_TIER: dict[DependencyTier, frozenset[str]] = {
    DependencyTier.STANDARD_LIBRARY: frozenset(),
    DependencyTier.PLAN_MANIFEST: frozenset({"yaml"}),
    DependencyTier.PAGE_RENDERING: frozenset({"yaml", "jinja2", "markdown", "nh3"}),
}
"""
The third-party modules each tier is allowed to import. Everything a tier is *not*
allowed is what gets blocked when its modules' imports are checked, so adding a
dependency to the package means saying which tier may have it.
"""


@dataclass(frozen=True)
class PackageModule:
    """
    One module the migration is required to produce, and what is expected of it.
    """

    name: str
    """
    The module's name within the package, e.g. ``"stack"``.
    """

    tier: DependencyTier
    """
    The furthest this module is allowed to reach. See :class:`DependencyTier`.
    """

    is_command_line_entry_point: bool = False
    """
    Whether ``python -m bastler.<name> --help`` must answer. True for a module a script or
    a session invokes directly, false for one only its siblings import.
    """

    @property
    def import_path(self) -> str:
        """The dotted path this module is imported by."""
        return f"bastler.{self.name}"

    @property
    def blocked_third_party_modules(self) -> frozenset[str]:
        """The third-party modules that must stay unimportable for this module's own
        import to be considered within its tier."""
        every_third_party_module = THIRD_PARTY_MODULES_BY_TIER[
            DependencyTier.PAGE_RENDERING
        ]
        return every_third_party_module - THIRD_PARTY_MODULES_BY_TIER[self.tier]


PACKAGE_MODULES: tuple[PackageModule, ...] = (
    # .claude/stack/ - the stacked-pull-request tooling.
    PackageModule("stack", DependencyTier.STANDARD_LIBRARY, True),
    PackageModule("class_property", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance", DependencyTier.STANDARD_LIBRARY, True),
    PackageModule("maintenance_board", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_commands", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_constants", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_errors", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_fast_forward", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_git_commands", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_github", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_promotion", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_report", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_restack_procedure", DependencyTier.STANDARD_LIBRARY),
    PackageModule("maintenance_restack_steps", DependencyTier.STANDARD_LIBRARY),
    # .claude/hooks/ - the personal-notes and plan-manifest scripts.
    PackageModule("plan_model", DependencyTier.STANDARD_LIBRARY),
    PackageModule("plan_updates_since_support", DependencyTier.STANDARD_LIBRARY, True),
    PackageModule("plan_item_bootstrap", DependencyTier.PLAN_MANIFEST, True),
    PackageModule("plan_manifest_tools", DependencyTier.PLAN_MANIFEST, True),
    # .claude/skills/plan-dashboard/ - the dashboard build.
    PackageModule("refresh_dashboard_support", DependencyTier.STANDARD_LIBRARY, True),
    PackageModule("render_common", DependencyTier.PAGE_RENDERING),
    PackageModule("build_dashboard", DependencyTier.PAGE_RENDERING, True),
    PackageModule("build_index", DependencyTier.PAGE_RENDERING, True),
    PackageModule("check_dependency_readiness", DependencyTier.PAGE_RENDERING, True),
    PackageModule("sync_manifest_status", DependencyTier.PAGE_RENDERING, True),
    PackageModule("record_dashboard_url", DependencyTier.PLAN_MANIFEST, True),
    # .claude/skills/add-plan-item/ - the scope decision's mechanical half.
    PackageModule("check_scope_overlap", DependencyTier.STANDARD_LIBRARY, True),
    # .claude/upstream_reviews/ - the upstream review reader the Action runs.
    PackageModule("upstream_reviews", DependencyTier.STANDARD_LIBRARY, True),
)
"""
Every module the package is required to hold, listed rather than discovered.

Listed because this list *is* the migration's specification - a module that failed to
move would simply be absent from a discovered set, which is the one thing these tests
exist to catch. Discovery is right where a list carries no meaning of its own; here it
carries all of it.
"""


def run_from_repository_root(*arguments: str) -> subprocess.CompletedProcess[str]:
    """
    Run this interpreter from the repository root with an environment that cannot help it
    find the package.

    ``PYTHONPATH`` is stripped so a pass proves the zero-install import really comes from
    the repository root being the working directory, rather than from whatever the
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
    """The zero-install contract: a fresh clone with no pip step can import the package,
    and what it imports is this repository's copy rather than an installed one."""
    result = run_from_repository_root("-c", "import bastler; print(bastler.__file__)")

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == PACKAGE_DIRECTORY / "__init__.py"


def test_the_package_holds_every_module_the_migration_moves():
    """Every module named in :data:`PACKAGE_MODULES` is present as a file. This is the
    migration's completeness assertion - a module left behind fails here by name."""
    missing_module_names = [
        module.name
        for module in PACKAGE_MODULES
        if not (PACKAGE_DIRECTORY / f"{module.name}.py").is_file()
    ]

    assert missing_module_names == []


def test_the_package_holds_no_module_the_contract_does_not_name():
    """The reverse: a module present but unnamed above has no stated tier and no stated
    entry-point status, so nothing here would check it."""
    named_module_names = {module.name for module in PACKAGE_MODULES}
    present_module_names = {
        path.stem for path in PACKAGE_DIRECTORY.glob("*.py") if path.stem != "__init__"
    }

    assert present_module_names - named_module_names == set()


# %% each module stands on its own


@pytest.mark.parametrize("module", PACKAGE_MODULES, ids=lambda module: module.name)
def test_every_module_imports_on_its_own(module: PackageModule):
    """Each module imports in an interpreter that has imported nothing else.

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
    """Each entry point is reachable as ``python -m bastler.<name>``.

    That form rather than a path to the file: a module run by path puts its own directory
    on ``sys.path`` instead of the repository root, so its absolute imports of its
    siblings would not resolve. Every bash caller invokes them this way.
    """
    result = run_from_repository_root("-m", module.import_path, "--help")

    assert result.returncode == 0, result.stderr


# %% the dependency tiers reach no further than they claim


@pytest.mark.parametrize(
    "module",
    [module for module in PACKAGE_MODULES if module.blocked_third_party_modules],
    ids=lambda module: module.name,
)
def test_every_module_imports_within_its_own_dependency_tier(module: PackageModule):
    """A module imports with everything above its tier made unimportable.

    See :class:`DependencyTier` for why the boundary matters. The blocked modules stay
    installed - what is under test is what this module reaches, not what the machine
    running the suite happens to hold.
    """
    result = run_from_repository_root(
        str(IMPORT_WITH_MODULES_BLOCKED_SCRIPT),
        "--blocked",
        ",".join(sorted(module.blocked_third_party_modules)),
        module.import_path,
    )

    assert result.returncode == 0, result.stderr


def test_some_module_is_actually_checked_against_a_blocked_import():
    """The parametrization above filters, so this asserts it filtered to something.

    Without it, a tier table that accidentally allowed every module everything would make
    every case above vanish and the suite would still pass.
    """
    checked_module_names = [
        module.name for module in PACKAGE_MODULES if module.blocked_third_party_modules
    ]

    assert checked_module_names != []


# %% nothing is left behind


def test_no_python_module_remains_under_the_claude_directory():
    """The migration's own completeness assertion from the other side.

    ``.claude/`` keeps its SKILL.md files, settings.json and bash entry points - Claude
    Code discovers those by path - and not one Python file.
    """
    remaining_module_paths = sorted(
        str(path.relative_to(REPOSITORY_ROOT))
        for path in CLAUDE_DIRECTORY.rglob("*.py")
    )

    assert remaining_module_paths == []
