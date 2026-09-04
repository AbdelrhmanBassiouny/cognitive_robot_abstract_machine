"""
The plans the site-build tests seed a scratch notes branch from.

The manifests and roadmaps are real files under ``fixtures/site/``, read verbatim rather
than templated in code, so what the tests publish is a plan somebody could put on the
notes branch. Everything a test asserts about them - a title, a repository, a tracking
issue, a pull request number - is read back out of the manifest that declares it, so
nothing here is a second copy that keeps passing once the fixture changes. Only the ids
are named, since they are how a test points at one plan or item at all.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml

from build_dashboard import Item, Plan
from personal_notes import PlanDocument

SITE_FIXTURES_DIRECTORY = Path(__file__).parent / "fixtures" / "site"
"""
Holds one directory per fixture plan, laid out as the notes branch lays them out.
"""

STUBS_DIRECTORY = Path(__file__).parent / "fixtures" / "stubs"
"""
Holds the stand-ins a test drives instead of the real script.
"""


class SitePlanId(StrEnum):
    """
    The plans the site build is exercised over.

    Two of them, both referencing the same repository, because sharing one listing
    across plans is a behaviour the build has and one plan could not show.
    """

    FIRST = "first-plan"
    """
    The plan every per-plan assertion is made against.
    """

    SECOND = "second-plan"
    """
    Its sibling, which exists to be the second plan.
    """

    @property
    def directory(self) -> Path:
        """:return: Where this plan's documents are read from."""
        return SITE_FIXTURES_DIRECTORY / self

    def document(self, document: PlanDocument) -> str:
        """
        :param document: The document to read.
        :return: Its content, exactly as the branch will carry it.
        """
        return (self.directory / document).read_text()

    @property
    def plan(self) -> Plan:
        """:return: The parsed manifest, to read expected values back out of."""
        return Plan.from_mapping(yaml.safe_load(self.document(PlanDocument.MANIFEST)))

    @property
    def referenced_item(self) -> Item:
        """:return: The one item of this plan that names a pull request."""
        return next(
            item for item in self.plan.items if item.pull_request_number is not None
        )


UNREFERENCED_PULL_REQUEST = 2
"""
A pull request the repository has and no fixture plan mentions.

Named here rather than read from a manifest because its whole point is that no manifest
carries it: the build must leave it out of what it hands the refresh.
"""


class SiteStub(StrEnum):
    """
    The stand-ins the site-build tests drive instead of ``refresh_dashboard.sh``.
    """

    REFRESH_DASHBOARD = "refresh_dashboard_stub.sh"
    """
    Records the arguments and the file contents it was handed, then reports a summary.
    """

    FAILING_REFRESH_DASHBOARD = "refresh_dashboard_failure_stub.sh"
    """
    Fails, so the build's own handling of a failed plan can be exercised.
    """

    @property
    def path(self) -> Path:
        """:return: Where the stub is on disk."""
        return STUBS_DIRECTORY / self


RECORDED_ARGUMENTS_FILENAME = "arguments.json"
"""
What :attr:`SiteStub.REFRESH_DASHBOARD` writes what it was handed into, beside the
dashboard page it was asked to render.
"""


class RecordedArgumentKey(StrEnum):
    """
    The keys :attr:`SiteStub.REFRESH_DASHBOARD` records under, beyond the option flags
    it echoes verbatim.

    The file contents are recorded under the document they carry, so a test asks for
    what was handed over rather than for where it was staged.
    """

    PLAN = "plan"
    """
    The manifest's content, as the refresh would have read it.
    """

    ROADMAP = "roadmap"
    """
    The roadmap's content.
    """

    PULL_REQUEST_DATA = "pr-data"
    """
    The pull request data document, still as JSON text.
    """
