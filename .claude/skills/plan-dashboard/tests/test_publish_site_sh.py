"""
Tests for publishing a built site directory as the whole content of a branch.

Everything runs against scratch git repositories, so no remote and no network access is
involved. What is under test is the branch's resulting content: that a first publish
starts it, that a later one replaces rather than merges, and that an unchanged rebuild
adds no commit.
"""

import subprocess
from pathlib import Path

import pytest

PLAN_DASHBOARD_DIRECTORY = Path(__file__).parent.parent
PUBLISH_SITE_SCRIPT = PLAN_DASHBOARD_DIRECTORY / "publish_site.sh"

SITE_BRANCH = "plan-dashboards-site"
JEKYLL_OPT_OUT_FILE = ".nojekyll"


@pytest.fixture
def publishing_clone(tmp_path: Path, run_git):
    """
    A scratch clone with a bare remote to publish into, and a helper that publishes a
    given site layout to it.

    :param tmp_path: pytest's per-test temporary directory.
    :param run_git: The scratch git runner.
    :return: The publisher, called with the site's files as ``{path: content}``.
    """
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--quiet", "--bare", str(remote)],
        check=True,
        capture_output=True,
    )
    clone = tmp_path / "clone"
    clone.mkdir()
    run_git(clone, "init", "--quiet")
    (clone / "placeholder").write_text("")
    run_git(clone, "add", ".")
    run_git(clone, "commit", "--quiet", "--message", "the clone's own history")

    site_directory = tmp_path / "site"

    def publish(files: dict[str, str]) -> subprocess.CompletedProcess:
        subprocess.run(["rm", "-rf", str(site_directory)], check=True)
        for relative_path, content in files.items():
            page = site_directory / relative_path
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(content)
        return subprocess.run(
            [
                "bash",
                str(PUBLISH_SITE_SCRIPT),
                "--source",
                str(site_directory),
                "--branch",
                SITE_BRANCH,
                "--remote",
                str(remote),
                "--message",
                "Publish the plan dashboards",
            ],
            cwd=clone,
            check=True,
            capture_output=True,
            text=True,
            env={
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": str(tmp_path),
            },
        )

    publish.clone = clone
    publish.remote = remote
    return publish


def published_files(remote: Path) -> set[str]:
    """
    Every path the site branch carries.

    :param remote: The bare remote the site was published to.
    :return: The paths.
    """
    listing = subprocess.run(
        ["git", "-C", str(remote), "ls-tree", "-r", "--name-only", SITE_BRANCH],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return set(listing.split())


def commit_count(remote: Path) -> int:
    """
    How many commits the site branch carries.

    :param remote: The bare remote the site was published to.
    :return: The count.
    """
    return int(
        subprocess.run(
            ["git", "-C", str(remote), "rev-list", "--count", SITE_BRANCH],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


def test_a_first_publish_starts_the_branch(publishing_clone):
    """The branch need not exist yet - the first run is what creates it."""
    publishing_clone({"index.html": "<html>index</html>"})

    assert published_files(publishing_clone.remote) == {
        "index.html",
        JEKYLL_OPT_OUT_FILE,
    }


def test_the_branch_carries_the_site_and_not_the_repository(publishing_clone):
    """The clone's own history is not the site's - a repository file appearing on the
    branch would be served alongside the pages."""
    publishing_clone({"index.html": "<html>index</html>"})

    assert "placeholder" not in published_files(publishing_clone.remote)


def test_a_page_no_longer_built_stops_being_served(publishing_clone):
    """
    Each publish replaces the branch's content rather than merging into it: a plan
    deleted from the notes branch must not go on being served from an old build.
    """
    publishing_clone(
        {
            "index.html": "<html>index</html>",
            "plans/a-plan/index.html": "<html>a plan</html>",
        }
    )

    publishing_clone({"index.html": "<html>index</html>"})

    assert published_files(publishing_clone.remote) == {
        "index.html",
        JEKYLL_OPT_OUT_FILE,
    }


def test_each_publish_keeps_the_previous_one(publishing_clone):
    """
    The branch is the site's history, so a publish is a commit on top of the last rather
    than a replacement of it.
    """
    publishing_clone({"index.html": "<html>first</html>"})
    publishing_clone({"index.html": "<html>second</html>"})

    assert commit_count(publishing_clone.remote) == 2


def test_an_unchanged_rebuild_publishes_nothing(publishing_clone):
    """A rebuild that renders the same site adds no empty commit - most runs change
    nothing, and each would otherwise leave one behind."""
    publishing_clone({"index.html": "<html>index</html>"})

    republished = publishing_clone({"index.html": "<html>index</html>"})

    assert commit_count(publishing_clone.remote) == 1
    assert "already up to date" in republished.stdout


def test_the_branch_opts_out_of_the_jekyll_build(publishing_clone):
    """
    Pages would otherwise run Jekyll over the branch, which drops every path beginning
    with an underscore and rewrites the rest of already-rendered HTML.
    """
    publishing_clone({"index.html": "<html>index</html>"})

    assert JEKYLL_OPT_OUT_FILE in published_files(publishing_clone.remote)


def test_the_caller_s_own_branch_is_untouched(publishing_clone):
    """
    It works in a scratch worktree: a run must not move the checkout it was started
    from, which in a workflow is the branch the site was built out of.
    """
    before = subprocess.run(
        ["git", "-C", str(publishing_clone.clone), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    publishing_clone({"index.html": "<html>index</html>"})

    after = subprocess.run(
        ["git", "-C", str(publishing_clone.clone), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert after == before
