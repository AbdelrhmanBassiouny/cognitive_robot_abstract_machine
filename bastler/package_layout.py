"""
What this package contains, and how much of the dependency stack each module reaches.

Declared here rather than in the test that checks it, so the answer to "which entry
points work on a checkout where nothing has been installed?" is readable next to the code
it describes. :mod:`test.bastler_test.test_package_contract` holds every declaration below
to what the modules actually do.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

PACKAGE_DIRECTORY = Path(__file__).parent
"""
This package's own directory, which is also the directory it *is* rather than lives under.
"""

REPOSITORY_ROOT = PACKAGE_DIRECTORY.parent
"""
The repository root, which is the directory ``bastler`` imports from with no install.
"""

REQUIREMENTS_FILE = PACKAGE_DIRECTORY / "requirements.txt"
"""
The dependencies the top tier needs, and the single list the ``rendering`` extra is read
from.
"""


class DependencyTier(StrEnum):
    """
    How much of the dependency stack a module reaches.

    Not a prohibition on installing anything: ``check-setup.sh`` reports a missing
    requirement and ``/setup-personal-notes`` installs it. What the tier answers is
    whether a caller has to do that first - a module in the standard-library tier runs on
    a fresh clone as it stands, and one above it does not.
    """

    STANDARD_LIBRARY = "standard-library"
    """
    Imports nothing outside the standard library, so it runs on a checkout where nothing
    has been installed.
    """

    PLAN_MANIFEST = "plan-manifest"
    """
    Reads or writes a plan manifest, so it needs PyYAML - but never the render layer.
    """

    PAGE_RENDERING = "page-rendering"
    """
    Renders a dashboard page, so it needs Jinja2, markdown and nh3 as well. The top tier:
    everything in ``requirements.txt`` is available to it.
    """


THIRD_PARTY_MODULES_BY_TIER: dict[DependencyTier, frozenset[str]] = {
    DependencyTier.STANDARD_LIBRARY: frozenset(),
    DependencyTier.PLAN_MANIFEST: frozenset({"yaml"}),
    DependencyTier.PAGE_RENDERING: frozenset({"yaml", "jinja2", "markdown", "nh3"}),
}
"""
The third-party modules each tier reaches, named as they are imported.

Everything a tier does *not* reach is what gets blocked when its modules' imports are
checked, so adding a dependency to this package means saying which tier may have it.
"""


@dataclass(frozen=True)
class PackageModule:
    """
    One module of this package, and what is expected of it.
    """

    name: str
    """
    The module's name within the package, e.g. ``"stack"``.
    """

    tier: DependencyTier
    """
    How much of the dependency stack it reaches. See :class:`DependencyTier`.
    """

    is_command_line_entry_point: bool = False
    """
    Whether ``python3 -m bastler.<name> --help`` answers. True for a module a script or a
    session invokes directly, false for one only its siblings import.
    """

    @property
    def import_path(self) -> str:
        """:return: The dotted path this module is imported by."""
        return f"bastler.{self.name}"

    @property
    def path(self) -> Path:
        """:return: Where this module's file lives."""
        return PACKAGE_DIRECTORY / f"{self.name}.py"

    @property
    def unreachable_third_party_modules(self) -> frozenset[str]:
        """
        :return: The third-party modules that must stay unimportable for this module's own
            import to be within its tier.
        """
        everything_declared = THIRD_PARTY_MODULES_BY_TIER[DependencyTier.PAGE_RENDERING]
        return everything_declared - THIRD_PARTY_MODULES_BY_TIER[self.tier]


PACKAGE_MODULES: tuple[PackageModule, ...] = (
    # The stacked-pull-request tooling.
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
    PackageModule("upstream_reviews", DependencyTier.STANDARD_LIBRARY, True),
    # The personal-notes and plan-manifest scripts.
    PackageModule("plan_model", DependencyTier.STANDARD_LIBRARY),
    PackageModule("plan_updates_since_support", DependencyTier.STANDARD_LIBRARY, True),
    PackageModule("plan_item_bootstrap", DependencyTier.PLAN_MANIFEST, True),
    PackageModule("plan_manifest_tools", DependencyTier.PLAN_MANIFEST, True),
    PackageModule("check_scope_overlap", DependencyTier.STANDARD_LIBRARY, True),
    # The dashboard build.
    PackageModule("refresh_dashboard_support", DependencyTier.STANDARD_LIBRARY, True),
    PackageModule("record_dashboard_url", DependencyTier.PLAN_MANIFEST, True),
    PackageModule("render_common", DependencyTier.PAGE_RENDERING),
    PackageModule("build_dashboard", DependencyTier.PAGE_RENDERING, True),
    PackageModule("build_index", DependencyTier.PAGE_RENDERING, True),
    PackageModule("check_dependency_readiness", DependencyTier.PAGE_RENDERING, True),
    PackageModule("sync_manifest_status", DependencyTier.PAGE_RENDERING, True),
    # This declaration, and the version the repository's own VERSION file writes here.
    PackageModule("package_layout", DependencyTier.STANDARD_LIBRARY),
    PackageModule("_version", DependencyTier.STANDARD_LIBRARY),
)
"""
Every module this package holds.

Written out rather than discovered, because each entry says something a directory listing
cannot: which tier the module reaches, and whether it answers as a command line. A test
holds the *set* of names equal to what the directory actually contains, so a module added
without an entry here fails rather than going quietly uncovered.
"""

MODULES_BY_NAME: dict[str, PackageModule] = {
    module.name: module for module in PACKAGE_MODULES
}
"""
Every module above, by its name within the package.
"""
