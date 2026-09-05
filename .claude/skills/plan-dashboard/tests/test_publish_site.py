"""
Tests for publishing a built site directory as the whole content of a branch.

Everything runs against scratch git repositories, so no remote and no network access is
involved. What is under test is the branch's resulting content: that a first publish
starts it, that a later one replaces rather than merges, and that an unchanged rebuild
adds no commit.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from build_site import SitePath
from git_commands import GitCommandRunner
from publish_site import (
    DEFAULT_SITE_BRANCH,
    SiteFile,
    SitePublisher,
    SiteSourceMissingError,
)
from scratch_repositories import CLONE_DIRECTORY, SCRATCH_REMOTE_DIRECTORY

REPOSITORY_FILE = "placeholder"
"""
A file the publishing clone's own history carries, which the site branch must not.
"""

COMMIT_MESSAGE = "Publish the plan dashboards"

FIRST_PAGE = "<html>first</html>"
SECOND_PAGE = "<html>second</html>"
PLAN_PAGE_PATH = f"{SitePath.PLANS_DIRECTORY}/a-plan/{SitePath.INDEX_PAGE}"


@dataclass
class PublishingClone:
    """
    A scratch clone, the bare remote it publishes to, and the publisher between them.
    """

    clone: Path
    """
    The checkout the publisher adds its scratch worktree to.
    """

    remote: Path
    """
    The bare repository the site branch is pushed to.
    """

    publisher: SitePublisher
    """
    The publisher under test.
    """

    site_directory: Path
    """
    Where each call stages the site to publish.
    """

    remote_git: GitCommandRunner = field(init=False)
    """
    Reads the published branch back out of the remote.
    """

    def __post_init__(self) -> None:
        """
        Point a runner at the bare remote, to read what was published.
        """
        self.remote_git = GitCommandRunner(self.remote)

    def publish(self, pages: dict[str, str]) -> bool:
        """
        Stage a site and publish it.

        :param pages: The site's files, as ``{path: content}``.
        :return: Whether anything was pushed.
        """
        if self.site_directory.exists():
            for existing in sorted(
                self.site_directory.rglob("*"), key=lambda path: -len(path.parts)
            ):
                existing.unlink() if existing.is_file() else existing.rmdir()
        for relative_path, content in pages.items():
            page = self.site_directory / relative_path
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(content)
        return self.publisher.publish(self.site_directory, COMMIT_MESSAGE)

    @property
    def published_files(self) -> set[str]:
        """:return: Every path the site branch carries."""
        listing = self.remote_git.run(
            "ls-tree", "-r", "--name-only", self.publisher.branch
        )
        return set(listing.split())

    @property
    def commit_count(self) -> int:
        """:return: How many commits the site branch carries."""
        return int(self.remote_git.run("rev-list", "--count", self.publisher.branch))

    @property
    def checked_out_commit(self) -> str:
        """:return: The commit the publishing checkout itself is on."""
        return self.publisher.git.run("rev-parse", "HEAD")


@pytest.fixture
def publishing_clone(tmp_path: Path, scratch_git) -> PublishingClone:
    """
    A scratch clone with a bare remote to publish into, and the publisher between them.

    :param tmp_path: pytest's per-test temporary directory.
    :param scratch_git: The scratch git runner.
    :return: The clone, ready to publish.
    """
    remote = tmp_path / SCRATCH_REMOTE_DIRECTORY
    scratch_git.in_directory(tmp_path).run("init", "--quiet", "--bare", str(remote))

    clone = tmp_path / CLONE_DIRECTORY
    clone.mkdir()
    clone_git = scratch_git.in_directory(clone)
    clone_git.run("init", "--quiet")
    (clone / REPOSITORY_FILE).write_text("")
    clone_git.run("add", ".")
    clone_git.run("commit", "--quiet", "--message", "the clone's own history")

    return PublishingClone(
        clone=clone,
        remote=remote,
        publisher=SitePublisher(
            git=clone_git, remote=str(remote), branch=DEFAULT_SITE_BRANCH
        ),
        site_directory=tmp_path / "site",
    )


def test_a_first_publish_starts_the_branch(publishing_clone: PublishingClone):
    """The branch need not exist yet - the first run is what creates it."""
    published = publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})

    assert published is True
    assert publishing_clone.published_files == {
        str(SitePath.INDEX_PAGE),
        str(SiteFile.JEKYLL_OPT_OUT),
    }


def test_the_branch_carries_the_site_and_not_the_repository(
    publishing_clone: PublishingClone,
):
    """The clone's own history is not the site's - a repository file appearing on the
    branch would be served alongside the pages."""
    publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})

    assert REPOSITORY_FILE not in publishing_clone.published_files


def test_a_page_no_longer_built_stops_being_served(publishing_clone: PublishingClone):
    """
    Each publish replaces the branch's content rather than merging into it: a plan
    deleted from the notes branch must not go on being served from an old build.
    """
    publishing_clone.publish(
        {SitePath.INDEX_PAGE: FIRST_PAGE, PLAN_PAGE_PATH: SECOND_PAGE}
    )

    publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})

    assert publishing_clone.published_files == {
        str(SitePath.INDEX_PAGE),
        str(SiteFile.JEKYLL_OPT_OUT),
    }


def test_each_publish_keeps_the_previous_one(publishing_clone: PublishingClone):
    """
    The branch is the site's history, so a publish is a commit on top of the last rather
    than a replacement of it.
    """
    publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})
    publishing_clone.publish({SitePath.INDEX_PAGE: SECOND_PAGE})

    assert publishing_clone.commit_count == 2


def test_an_unchanged_rebuild_publishes_nothing(publishing_clone: PublishingClone):
    """A rebuild that renders the same site adds no empty commit - most runs change
    nothing, and each would otherwise leave one behind."""
    publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})

    republished = publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})

    assert republished is False
    assert publishing_clone.commit_count == 1


def test_the_branch_opts_out_of_the_jekyll_build(publishing_clone: PublishingClone):
    """
    Pages would otherwise run Jekyll over the branch, which drops every path beginning
    with an underscore and rewrites the rest of already-rendered HTML.
    """
    publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})

    assert str(SiteFile.JEKYLL_OPT_OUT) in publishing_clone.published_files


def test_the_callers_own_branch_is_untouched(publishing_clone: PublishingClone):
    """
    It works in a scratch worktree: a run must not move the checkout it was started
    from, which in a workflow is the branch the site was built out of.
    """
    before = publishing_clone.checked_out_commit

    publishing_clone.publish({SitePath.INDEX_PAGE: FIRST_PAGE})

    assert publishing_clone.checked_out_commit == before


def test_a_missing_site_directory_is_an_error(publishing_clone: PublishingClone):
    """
    Publishing a site that was never built would empty the branch, taking the whole
    published site down rather than leaving the last good one served.
    """
    never_built = publishing_clone.site_directory / "never-built"

    with pytest.raises(SiteSourceMissingError) as raised:
        publishing_clone.publisher.publish(never_built, COMMIT_MESSAGE)

    assert raised.value.source_directory == never_built
